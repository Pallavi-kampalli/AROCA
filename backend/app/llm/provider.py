"""
LLM provider adapter — supports Ollama and any OpenAI-compatible API.
Credentials are read from environment variables only.
"""
import time
import json
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError
from app.core.config import settings
import structlog

logger = structlog.get_logger()


class LLMError(Exception):
    pass


class LLMConfigError(LLMError):
    pass


class LLMProviderAdapter:
    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
                raise LLMConfigError(
                    "LLM not configured. Set LLM_BASE_URL and LLM_API_KEY in environment."
                )
            self._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        operation: str = "general",
        incident_id: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Call the LLM and return a structured result.
        Never fabricates results — raises LLMError on failure.
        """
        client = self._get_client()
        start = time.time()
        max_tok = max_tokens or settings.LLM_MAX_OUTPUT_TOKENS

        try:
            response = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tok,
            )
            latency_ms = int((time.time() - start) * 1000)
            content = response.choices[0].message.content or ""
            usage = response.usage

            return {
                "content": content,
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
                "operation": operation,
                "latency_ms": latency_ms,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "completion_tokens": usage.completion_tokens if usage else None,
                "success": True,
            }

        except APIConnectionError as e:
            raise LLMError(
                f"Cannot connect to LLM provider at {settings.LLM_BASE_URL}. "
                f"If using Ollama, ensure it is running: `ollama serve`. Error: {e}"
            )
        except APITimeoutError:
            raise LLMError(
                f"LLM request timed out after {settings.LLM_TIMEOUT_SECONDS}s. "
                "Try a smaller prompt or increase LLM_TIMEOUT_SECONDS."
            )
        except APIStatusError as e:
            if e.status_code == 401:
                raise LLMConfigError(f"LLM authentication failed. Check LLM_API_KEY. Status: {e.status_code}")
            raise LLMError(f"LLM API error {e.status_code}: {e.message}")

    async def check_availability(self) -> Dict[str, Any]:
        """Check if the LLM is reachable and the model exists."""
        try:
            client = self._get_client()
            models = await client.models.list()
            model_ids = [m.id for m in models.data]
            configured_available = settings.LLM_MODEL in model_ids or any(
                settings.LLM_MODEL in mid for mid in model_ids
            )
            return {
                "available": True,
                "provider": settings.LLM_PROVIDER,
                "base_url": settings.LLM_BASE_URL,
                "configured_model": settings.LLM_MODEL,
                "model_available": configured_available,
                "available_models": model_ids[:20],
            }
        except LLMConfigError as e:
            return {"available": False, "error": str(e), "type": "config_error"}
        except Exception as e:
            return {"available": False, "error": str(e), "type": "connection_error"}


_adapter: Optional[LLMProviderAdapter] = None


def get_llm() -> LLMProviderAdapter:
    global _adapter
    if _adapter is None:
        _adapter = LLMProviderAdapter()
    return _adapter
