"""
Isolation Forest anomaly detector.
Trains on actual log feature vectors and produces anomaly scores.
"""
import os
import joblib
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from app.core.config import settings


MIN_TRAINING_SAMPLES = 10
ANOMALY_THRESHOLD = -0.1  # Score below this → anomalous


class AnomalyDetector:
    def __init__(self, model_name: str = "isolation_forest_v1"):
        self.model_name = model_name
        self.pipeline: Optional[Pipeline] = None
        self.feature_names: list = []
        self.trained_at: Optional[datetime] = None
        self.training_samples: int = 0

    @property
    def model_path(self) -> str:
        return os.path.join(settings.ML_MODELS_DIR, f"{self.model_name}.joblib")

    @property
    def meta_path(self) -> str:
        return os.path.join(settings.ML_MODELS_DIR, f"{self.model_name}_meta.joblib")

    def is_trained(self) -> bool:
        return self.pipeline is not None or os.path.exists(self.model_path)

    def load(self) -> bool:
        """Load persisted model. Returns True if successful."""
        try:
            if os.path.exists(self.model_path):
                self.pipeline = joblib.load(self.model_path)
                if os.path.exists(self.meta_path):
                    meta = joblib.load(self.meta_path)
                    self.feature_names = meta.get("feature_names", [])
                    self.trained_at = meta.get("trained_at")
                    self.training_samples = meta.get("training_samples", 0)
                return True
        except Exception as e:
            print(f"Failed to load model: {e}")
        return False

    def train(self, X: np.ndarray, feature_names: list) -> Dict[str, Any]:
        """
        Train the Isolation Forest on feature matrix X.
        Returns training metrics.
        """
        if len(X) < MIN_TRAINING_SAMPLES:
            return {
                "success": False,
                "error": f"Need at least {MIN_TRAINING_SAMPLES} samples, got {len(X)}",
                "samples": len(X),
            }

        try:
            self.pipeline = Pipeline([
                ("scaler", StandardScaler()),
                ("isoforest", IsolationForest(
                    n_estimators=100,
                    contamination=0.1,
                    random_state=42,
                    n_jobs=-1,
                )),
            ])
            self.pipeline.fit(X)
            self.feature_names = feature_names
            self.trained_at = datetime.now(timezone.utc)
            self.training_samples = len(X)

            # Compute training scores for reporting
            scores = self.pipeline.decision_function(X)
            anomaly_count = sum(1 for s in scores if s < ANOMALY_THRESHOLD)

            # Save
            os.makedirs(settings.ML_MODELS_DIR, exist_ok=True)
            joblib.dump(self.pipeline, self.model_path)
            joblib.dump({
                "feature_names": feature_names,
                "trained_at": self.trained_at,
                "training_samples": self.training_samples,
            }, self.meta_path)

            return {
                "success": True,
                "samples": len(X),
                "features": len(feature_names),
                "anomaly_rate_in_training": anomaly_count / len(X),
                "mean_score": float(np.mean(scores)),
                "std_score": float(np.std(scores)),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def predict(self, x: np.ndarray, feature_names: list) -> Dict[str, Any]:
        """
        Run inference on a single feature vector.
        Returns anomaly score, label, and contributing features.
        """
        if not self.is_trained():
            if not self.load():
                return {
                    "data_sufficient": False,
                    "explanation": "Model not yet trained. Upload more log data and trigger training.",
                }

        if self.pipeline is None:
            self.load()

        if self.pipeline is None:
            return {
                "data_sufficient": False,
                "explanation": "Model could not be loaded.",
            }

        try:
            x_reshaped = x.reshape(1, -1)
            score = float(self.pipeline.decision_function(x_reshaped)[0])
            prediction = int(self.pipeline.predict(x_reshaped)[0])
            is_anomalous = score < ANOMALY_THRESHOLD

            # Identify contributing features (highest absolute feature values after scaling)
            scaler = self.pipeline.named_steps["scaler"]
            x_scaled = scaler.transform(x_reshaped)[0]
            contributing = []
            for i, (fname, val) in enumerate(zip(feature_names, x_scaled)):
                if abs(val) > 1.0:  # More than 1 std from mean
                    contributing.append({
                        "feature": fname,
                        "scaled_value": round(float(val), 3),
                        "raw_value": round(float(x[i]), 3),
                    })
            contributing.sort(key=lambda c: abs(c["scaled_value"]), reverse=True)

            explanation = self._build_explanation(score, is_anomalous, contributing)

            return {
                "data_sufficient": True,
                "anomaly_score": round(score, 4),
                "is_anomalous": is_anomalous,
                "contributing_features": contributing[:5],
                "explanation": explanation,
            }
        except Exception as e:
            return {
                "data_sufficient": False,
                "explanation": f"Inference failed: {str(e)}",
            }

    def _build_explanation(self, score: float, is_anomalous: bool, contributing: list) -> str:
        if is_anomalous:
            parts = [f"Anomaly detected (score: {score:.3f}). "]
            if contributing:
                top = contributing[0]
                parts.append(f"Primary indicator: {top['feature']} = {top['raw_value']}.")
            parts.append("This log pattern deviates significantly from the trained baseline.")
        else:
            parts = [f"Log pattern within normal range (score: {score:.3f})."]
        return " ".join(parts)


# Singleton
_detector: Optional[AnomalyDetector] = None


def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
        _detector.load()
    return _detector
