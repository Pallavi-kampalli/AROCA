import { useState, useEffect } from 'react'
import { Brain, CheckCircle, XCircle, AlertTriangle, Play, RefreshCw } from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { Button } from '../../components/Button/Button'
import { StatusBadge } from '../../components/Badge/Badge'
import { modelsAPI, auditAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Models.css'

function StatusDot({ ok }) {
  return <span className={`status-indicator ${ok ? 'ok' : 'fail'}`} />
}

export function Models() {
  const [status, setStatus] = useState(null)
  const [trainingRuns, setTrainingRuns] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [training, setTraining] = useState(false)
  const [tab, setTab] = useState('models')
  const [auditAction, setAuditAction] = useState('')
  const [auditPage, setAuditPage] = useState(1)
  const [auditTotal, setAuditTotal] = useState(0)
  const toast = useToast()

  const load = async () => {
    setLoading(true)
    try {
      const [s, t] = await Promise.all([modelsAPI.status(), modelsAPI.trainingRuns()])
      setStatus(s.data)
      setTrainingRuns(t.data)
    } catch {
      toast.error('Failed to load model status')
    } finally {
      setLoading(false)
    }
  }

  const loadAudit = async () => {
    try {
      const res = await auditAPI.list(auditPage, auditAction)
      setAuditLogs(res.data.items)
      setAuditTotal(res.data.total)
    } catch {}
  }

  useEffect(() => { load() }, [])
  useEffect(() => { if (tab === 'audit') loadAudit() }, [tab, auditPage, auditAction])

  const handleTrain = async () => {
    setTraining(true)
    try {
      const res = await modelsAPI.train()
      if (res.data.status === 'insufficient_data') {
        toast.warning(res.data.message)
      } else {
        toast.success('Training started. Refresh in a moment to see results.')
      }
      setTimeout(load, 2000)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Training failed')
    } finally {
      setTraining(false)
    }
  }

  const fmt = (s) => s ? new Date(s).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'

  return (
    <Layout title="ML Models & Audit">
      <div className="models-page fade-in">
        <div className="page-header">
          <div>
            <h2 className="page-title">ML Models & Audit</h2>
            <p className="page-sub">Manage anomaly detection models and view the immutable audit trail</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="secondary" size="sm" onClick={load} id="btn-refresh-models">
              <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
            </Button>
            <Button size="sm" onClick={handleTrain} loading={training} id="btn-train-model">
              <Play size={14} /> Train Model
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs-bar" style={{ background: 'var(--color-white)', borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0', borderBottom: '1px solid var(--color-gray-200)' }}>
          <button className={`tab-btn ${tab === 'models' ? 'active' : ''}`} onClick={() => setTab('models')}>Models & Status</button>
          <button className={`tab-btn ${tab === 'training' ? 'active' : ''}`} onClick={() => setTab('training')}>Training Runs</button>
          <button className={`tab-btn ${tab === 'audit' ? 'active' : ''}`} onClick={() => setTab('audit')}>Audit Log</button>
        </div>

        {/* ─── Models tab ─── */}
        {tab === 'models' && (
          <div className="models-grid">
            {/* Isolation Forest card */}
            <Card>
              <div className="model-card-header">
                <Brain size={18} color="var(--color-accent)" />
                <h3>Isolation Forest</h3>
                <StatusDot ok={status?.isolation_forest?.trained} />
              </div>
              {loading ? (
                <div className="loading-state"><div className="loading-spinner" /></div>
              ) : (
                <div className="model-details">
                  <div className="model-detail-row">
                    <span>Status</span>
                    <strong style={{ color: status?.isolation_forest?.trained ? 'var(--color-success)' : 'var(--color-gray-400)' }}>
                      {status?.isolation_forest?.trained ? 'Trained' : 'Not trained'}
                    </strong>
                  </div>
                  {status?.isolation_forest?.trained && (
                    <>
                      <div className="model-detail-row">
                        <span>Training Samples</span>
                        <strong>{status.isolation_forest.training_samples}</strong>
                      </div>
                      <div className="model-detail-row">
                        <span>Features</span>
                        <strong>{status.isolation_forest.features?.length || 0}</strong>
                      </div>
                      <div className="model-detail-row">
                        <span>Trained At</span>
                        <strong>{fmt(status.isolation_forest.trained_at)}</strong>
                      </div>
                      {status.isolation_forest.features?.length > 0 && (
                        <div className="feature-list">
                          <span className="feature-list-label">Features used:</span>
                          <div className="feature-tags">
                            {status.isolation_forest.features.slice(0, 12).map(f => (
                              <span key={f} className="feature-tag-sm">{f}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  {!status?.isolation_forest?.trained && (
                    <div className="model-hint">
                      <AlertTriangle size={14} />
                      <p>Upload logs to 2+ incidents and click "Train Model" to train the anomaly detector.</p>
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* LLM status card */}
            <Card>
              <div className="model-card-header">
                <Brain size={18} color="var(--color-info)" />
                <h3>LLM Provider</h3>
                <StatusDot ok={status?.llm?.available} />
              </div>
              {loading ? (
                <div className="loading-state"><div className="loading-spinner" /></div>
              ) : (
                <div className="model-details">
                  <div className="model-detail-row">
                    <span>Provider</span>
                    <strong>{status?.llm?.provider || '—'}</strong>
                  </div>
                  <div className="model-detail-row">
                    <span>Base URL</span>
                    <strong style={{ fontSize: 11, fontFamily: 'monospace' }}>{status?.llm?.base_url || '—'}</strong>
                  </div>
                  <div className="model-detail-row">
                    <span>Configured Model</span>
                    <strong>{status?.llm?.configured_model || '—'}</strong>
                  </div>
                  <div className="model-detail-row">
                    <span>Available</span>
                    {status?.llm?.available ? (
                      <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>
                        <CheckCircle size={13} style={{ display: 'inline', marginRight: 4 }} />Connected
                      </span>
                    ) : (
                      <span style={{ color: 'var(--color-critical)', fontWeight: 600 }}>
                        <XCircle size={13} style={{ display: 'inline', marginRight: 4 }} />
                        {status?.llm?.type === 'config_error' ? 'Not configured' : 'Unreachable'}
                      </span>
                    )}
                  </div>
                  {status?.llm?.available && status?.llm?.available_models?.length > 0 && (
                    <div className="feature-list">
                      <span className="feature-list-label">Available models:</span>
                      <div className="feature-tags">
                        {status.llm.available_models.slice(0, 6).map(m => (
                          <span key={m} className={`feature-tag-sm ${m === status.llm.configured_model ? 'tag-active' : ''}`}>{m}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {status?.llm?.error && (
                    <div className="model-hint model-hint-error">
                      <XCircle size={14} />
                      <p>{status.llm.error}</p>
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* Stats card */}
            <Card>
              <div className="model-card-header">
                <Brain size={18} color="var(--color-medium)" />
                <h3>Inference Stats</h3>
              </div>
              <div className="model-details">
                <div className="model-detail-row"><span>Total Inferences</span><strong>{status?.total_inferences ?? '—'}</strong></div>
                <div className="model-detail-row"><span>Anomalies Detected</span><strong style={{ color: 'var(--color-critical)' }}>{status?.anomaly_detections ?? '—'}</strong></div>
                <div className="model-detail-row"><span>Active Model Records</span><strong>{status?.model_records?.filter(m => m.is_active)?.length ?? 0}</strong></div>
              </div>
            </Card>
          </div>
        )}

        {/* ─── Training Runs tab ─── */}
        {tab === 'training' && (
          <Card padding={false}>
            {trainingRuns.length === 0 ? (
              <div className="empty-state" style={{ padding: 60 }}>
                No training runs yet. Click "Train Model" to start.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Status</th>
                    <th>Samples</th>
                    <th>Features</th>
                    <th>Started</th>
                    <th>Completed</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {trainingRuns.map(r => (
                    <tr key={r.id}>
                      <td className="text-sm" style={{ fontFamily: 'monospace', color: 'var(--color-gray-400)' }}>{r.id.slice(0, 8)}…</td>
                      <td><StatusBadge status={r.status} /></td>
                      <td>{r.samples_used ?? '—'}</td>
                      <td>{r.features_count ?? '—'}</td>
                      <td className="text-sm text-muted">{fmt(r.created_at)}</td>
                      <td className="text-sm text-muted">{fmt(r.completed_at)}</td>
                      <td className="text-sm text-muted">{r.error_message || (r.metrics ? `mean: ${r.metrics.mean_score?.toFixed(3)}` : '—')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}

        {/* ─── Audit tab ─── */}
        {tab === 'audit' && (
          <>
            <Card className="audit-controls">
              <div className="filters-row">
                <input
                  className="form-input"
                  style={{ maxWidth: 280 }}
                  placeholder="Filter by action (e.g. incident, auth, rca)…"
                  value={auditAction}
                  onChange={e => { setAuditAction(e.target.value); setAuditPage(1) }}
                  id="audit-filter"
                />
                <Button variant="secondary" size="sm" onClick={loadAudit} id="btn-refresh-audit">
                  <RefreshCw size={13} />
                </Button>
              </div>
            </Card>
            <Card padding={false}>
              {auditLogs.length === 0 ? (
                <div className="empty-state" style={{ padding: 60 }}>No audit events yet.</div>
              ) : (
                <>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Action</th>
                        <th>Resource</th>
                        <th>User</th>
                        <th>Details</th>
                        <th>Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.map(l => (
                        <tr key={l.id}>
                          <td>
                            <span className="audit-action">{l.action}</span>
                          </td>
                          <td className="text-sm">
                            {l.resource_type && <span className="text-muted">{l.resource_type}: </span>}
                            {l.resource_id ? <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{l.resource_id.slice(0, 8)}…</span> : '—'}
                          </td>
                          <td className="text-sm text-muted">{l.user_id ? l.user_id.slice(0, 8) + '…' : 'System'}</td>
                          <td className="text-sm text-muted">
                            {l.details && Object.keys(l.details).length > 0
                              ? JSON.stringify(l.details).slice(0, 60) + (JSON.stringify(l.details).length > 60 ? '…' : '')
                              : '—'}
                          </td>
                          <td className="text-sm text-muted">{fmt(l.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="pagination" style={{ padding: '8px 16px', borderTop: '1px solid var(--color-gray-200)' }}>
                    <span className="pagination-info">{auditTotal} total events</span>
                    <div className="pagination-controls">
                      <Button variant="secondary" size="sm" disabled={auditPage === 1}
                        onClick={() => setAuditPage(p => p - 1)} id="btn-audit-prev">Prev</Button>
                      <span className="pagination-page">{auditPage}</span>
                      <Button variant="secondary" size="sm" disabled={auditLogs.length < 50}
                        onClick={() => setAuditPage(p => p + 1)} id="btn-audit-next">Next</Button>
                    </div>
                  </div>
                </>
              )}
            </Card>
          </>
        )}
      </div>
    </Layout>
  )
}
