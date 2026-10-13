import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Play, UploadCloud, CheckCircle, AlertTriangle,
  MessageSquare, Clock, Activity, ChevronDown, ChevronUp,
  Cpu, FileText, Wrench, Link2, CheckCheck, XCircle, Loader
} from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { SeverityBadge, StatusBadge, Badge } from '../../components/Badge/Badge'
import { Button } from '../../components/Button/Button'
import { Modal } from '../../components/Modal/Modal'
import { incidentsAPI, logsAPI, analysisAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './IncidentDetail.css'

/* ─── Inline log uploader ─────────────────────────────────────────────────── */
function LogUploader({ incidentId, onDone }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const toast = useToast()

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    try {
      await logsAPI.upload(incidentId, file)
      toast.success('Log file uploaded and parsing started')
      setFile(null)
      onDone()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="log-uploader">
      <input
        id="log-file-input"
        type="file"
        accept=".log,.txt,.json,.jsonl,.csv"
        onChange={e => setFile(e.target.files[0])}
        style={{ display: 'none' }}
      />
      <label htmlFor="log-file-input" className="upload-area">
        <UploadCloud size={18} color="var(--color-gray-400)" />
        <span>{file ? file.name : 'Click to select log file (.log, .txt, .json, .jsonl, .csv)'}</span>
      </label>
      {file && (
        <Button size="sm" onClick={handleUpload} loading={uploading} id="btn-upload-log">
          Upload & Parse
        </Button>
      )}
    </div>
  )
}

/* ─── RCA Result Panel ────────────────────────────────────────────────────── */
function RCAPanel({ analysis, onPropose }) {
  const [expanded, setExpanded] = useState({})
  const toggle = (id) => setExpanded(e => ({ ...e, [id]: !e[id] }))

  if (!analysis) return null

  const confidenceColor = (label) => ({
    HIGH: 'var(--color-success)',
    MEDIUM: 'var(--color-medium)',
    LOW: 'var(--color-high)',
    UNCERTAIN: 'var(--color-gray-400)',
  }[label] || 'var(--color-gray-400)')

  return (
    <div className="rca-panel">
      {/* Summary */}
      {analysis.summary && (
        <div className="rca-summary">
          <p>{analysis.summary}</p>
        </div>
      )}

      {/* ML Findings */}
      {analysis.ml_findings && (
        <div className="rca-section">
          <div className="rca-section-header">
            <Cpu size={14} />
            <span>ML Anomaly Detection</span>
          </div>
          <div className="rca-ml-box">
            <div className="rca-ml-row">
              <span>Data Sufficient:</span>
              <strong>{analysis.ml_findings.data_sufficient ? 'Yes' : 'No'}</strong>
            </div>
            {analysis.ml_findings.data_sufficient && (
              <>
                <div className="rca-ml-row">
                  <span>Anomaly Score:</span>
                  <strong>{analysis.ml_findings.anomaly_score?.toFixed(4)}</strong>
                </div>
                <div className="rca-ml-row">
                  <span>Anomalous:</span>
                  <strong style={{ color: analysis.ml_findings.is_anomalous ? 'var(--color-critical)' : 'var(--color-success)' }}>
                    {analysis.ml_findings.is_anomalous ? 'Yes' : 'No'}
                  </strong>
                </div>
                {analysis.ml_findings.contributing_features?.length > 0 && (
                  <div className="rca-ml-features">
                    <span style={{ fontSize: 11, color: 'var(--color-gray-500)' }}>Contributing features:</span>
                    {analysis.ml_findings.contributing_features.slice(0, 3).map((f, i) => (
                      <span key={i} className="feature-tag">{f.feature}: {f.raw_value}</span>
                    ))}
                  </div>
                )}
              </>
            )}
            <p className="rca-ml-explanation">{analysis.ml_findings.explanation}</p>
          </div>
        </div>
      )}

      {/* Candidate Causes */}
      {analysis.candidate_causes?.length > 0 && (
        <div className="rca-section">
          <div className="rca-section-header">
            <Activity size={14} />
            <span>Root Cause Candidates ({analysis.candidate_causes.length})</span>
          </div>
          <div className="causes-list">
            {analysis.candidate_causes.map((cause) => (
              <div key={cause.id} className={`cause-card ${cause.rank === 1 ? 'cause-primary' : ''}`}>
                <div className="cause-header" onClick={() => toggle(cause.id)}>
                  <div className="cause-rank">#{cause.rank}</div>
                  <div className="cause-title">{cause.description}</div>
                  <div className="cause-confidence" style={{ color: confidenceColor(cause.confidence_label) }}>
                    {cause.confidence_label}
                    {cause.confidence_score != null && ` (${(cause.confidence_score * 100).toFixed(0)}%)`}
                  </div>
                  {expanded[cause.id] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>

                {expanded[cause.id] && (
                  <div className="cause-body">
                    {cause.supporting_evidence?.length > 0 && (
                      <div className="evidence-group">
                        <div className="evidence-label supporting">Supporting Evidence</div>
                        <ul className="evidence-list">
                          {cause.supporting_evidence.map((e, i) => <li key={i}>{e}</li>)}
                        </ul>
                      </div>
                    )}
                    {cause.contradicting_evidence?.length > 0 && (
                      <div className="evidence-group">
                        <div className="evidence-label contradicting">Contradicting Evidence</div>
                        <ul className="evidence-list">
                          {cause.contradicting_evidence.map((e, i) => <li key={i}>{e}</li>)}
                        </ul>
                      </div>
                    )}
                    {cause.missing_evidence?.length > 0 && (
                      <div className="evidence-group">
                        <div className="evidence-label missing">Missing Evidence</div>
                        <ul className="evidence-list">
                          {cause.missing_evidence.map((e, i) => <li key={i}>{e}</li>)}
                        </ul>
                      </div>
                    )}
                    {cause.affected_components?.length > 0 && (
                      <div className="affected-components">
                        <span className="evidence-label supporting" style={{ marginBottom: 4 }}>Affected Components</span>
                        <div className="tags-row">
                          {cause.affected_components.map((c, i) => (
                            <span key={i} className="tag">{c}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Remediation Proposals */}
      {analysis.remediation_proposals?.length > 0 && (
        <div className="rca-section">
          <div className="rca-section-header">
            <Wrench size={14} />
            <span>Recommended Actions</span>
          </div>
          <div className="actions-list">
            {analysis.remediation_proposals.map((action) => (
              <div key={action.id} className="action-card">
                <div className="action-header">
                  <div>
                    <span className="action-title">{action.title}</span>
                    <span className={`risk-badge risk-${action.risk_level?.toLowerCase()}`}>
                      {action.risk_level}
                    </span>
                    {action.requires_approval && (
                      <span className="approval-required">Approval required</span>
                    )}
                  </div>
                </div>
                <p className="action-description">{action.description}</p>
                {action.expected_outcome && (
                  <p className="action-outcome"><strong>Expected:</strong> {action.expected_outcome}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historical */}
      {analysis.historical_incidents?.length > 0 && (
        <div className="rca-section">
          <div className="rca-section-header">
            <Link2 size={14} />
            <span>Similar Historical Incidents</span>
          </div>
          <div className="historical-list">
            {analysis.historical_incidents.map((h, i) => (
              <div key={i} className="historical-item">
                <span className="historical-id">{h.similar_incident_id.slice(0, 8)}…</span>
                <span className="historical-score">Similarity: {(h.similarity_score * 100).toFixed(0)}%</span>
                {h.resolution_applicable && <span className="historical-resolved">Resolution applicable</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rca-meta">
        <span>Provider: {analysis.llm_provider} / {analysis.llm_model}</span>
        {analysis.latency_ms && <span>Latency: {analysis.latency_ms}ms</span>}
        {analysis.prompt_tokens && <span>Tokens: {analysis.prompt_tokens + (analysis.completion_tokens || 0)}</span>}
      </div>
    </div>
  )
}

/* ─── Main ─────────────────────────────────────────────────────────────────── */
export function IncidentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()

  const [incident, setIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')

  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  const [logs, setLogs] = useState({ items: [], total: 0, jobs: [] })
  const [logsLoading, setLogsLoading] = useState(false)

  const [comment, setComment] = useState('')
  const [commentLoading, setCommentLoading] = useState(false)

  const [resolveOpen, setResolveOpen] = useState(false)
  const [resolutionNotes, setResolutionNotes] = useState('')

  const loadIncident = useCallback(async () => {
    try {
      const res = await incidentsAPI.get(id)
      setIncident(res.data)
    } catch {
      toast.error('Failed to load incident')
    } finally {
      setLoading(false)
    }
  }, [id])

  const loadAnalyses = useCallback(async () => {
    try {
      const res = await analysisAPI.list(id)
      setAnalyses(res.data)
    } catch {}
  }, [id])

  const loadLogs = useCallback(async () => {
    setLogsLoading(true)
    try {
      const res = await logsAPI.list(id, { page: 1, page_size: 100 })
      setLogs(res.data)
    } catch {}
    setLogsLoading(false)
  }, [id])

  useEffect(() => {
    loadIncident()
    loadAnalyses()
    loadLogs()
  }, [loadIncident, loadAnalyses, loadLogs])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    try {
      await analysisAPI.trigger(id)
      toast.success('Analysis started — this may take 30–120 seconds with Ollama')
      // Poll for completion
      const poll = setInterval(async () => {
        const res = await analysisAPI.list(id)
        const running = res.data.find(r => r.status === 'RUNNING')
        const completed = res.data.find(r => r.status === 'COMPLETED')
        if (!running) {
          clearInterval(poll)
          setAnalyzing(false)
          setAnalyses(res.data)
          if (completed) {
            toast.success('Analysis completed')
            const details = await analysisAPI.get(completed.id)
            setSelectedAnalysis(details.data)
            setActiveTab('analysis')
          } else {
            const failed = res.data[0]
            if (failed?.error_message) toast.error(`Analysis failed: ${failed.error_message}`)
          }
        }
      }, 5000)
    } catch (err) {
      setAnalyzing(false)
      toast.error(err.response?.data?.detail || 'Failed to start analysis')
    }
  }

  const loadAnalysisDetails = async (analysisId) => {
    setAnalysisLoading(true)
    try {
      const res = await analysisAPI.get(analysisId)
      setSelectedAnalysis(res.data)
      setActiveTab('analysis')
    } catch {
      toast.error('Failed to load analysis details')
    } finally {
      setAnalysisLoading(false)
    }
  }

  const handleComment = async (e) => {
    e.preventDefault()
    if (!comment.trim()) return
    setCommentLoading(true)
    try {
      await incidentsAPI.addComment(id, { content: comment, is_internal: true })
      setComment('')
      toast.success('Comment added')
      loadIncident()
    } catch {
      toast.error('Failed to add comment')
    } finally {
      setCommentLoading(false)
    }
  }

  const handleResolve = async () => {
    try {
      await incidentsAPI.resolve(id, { resolution_notes: resolutionNotes })
      toast.success('Incident resolved')
      setResolveOpen(false)
      loadIncident()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Cannot resolve')
    }
  }

  const handleReopen = async () => {
    try {
      await incidentsAPI.reopen(id)
      toast.success('Incident reopened')
      loadIncident()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Cannot reopen')
    }
  }

  const formatTs = (s) => {
    if (!s) return '—'
    return new Date(s).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
  }

  if (loading) {
    return (
      <Layout title="Incident Detail">
        <div className="loading-state" style={{ paddingTop: 100 }}>
          <div className="loading-spinner" />
          <span>Loading incident…</span>
        </div>
      </Layout>
    )
  }

  if (!incident) {
    return (
      <Layout title="Incident Not Found">
        <div className="empty-state">Incident not found.</div>
      </Layout>
    )
  }

  const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'logs', label: `Logs (${logs.total})` },
    { id: 'analysis', label: 'RCA Analysis' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'comments', label: `Comments (${incident.comments?.length || 0})` },
  ]

  const canResolve = ['INVESTIGATING', 'IN_PROGRESS'].includes(incident.status)
  const canReopen = ['RESOLVED', 'CLOSED'].includes(incident.status)

  return (
    <Layout title={incident.number}>
      <div className="incident-detail fade-in">
        {/* Back + Title */}
        <div className="detail-topbar">
          <button className="back-btn" onClick={() => navigate('/incidents')}>
            <ArrowLeft size={14} /> All Incidents
          </button>
          <div className="detail-header-info">
            <div className="detail-title-row">
              <span className="detail-number">{incident.number}</span>
              <SeverityBadge severity={incident.severity} />
              <StatusBadge status={incident.status} />
            </div>
            <h1 className="detail-title">{incident.title}</h1>
          </div>
          <div className="detail-actions">
            {canResolve && (
              <Button variant="success" size="sm" onClick={() => setResolveOpen(true)} id="btn-resolve">
                <CheckCheck size={14} /> Mark Resolved
              </Button>
            )}
            {canReopen && (
              <Button variant="secondary" size="sm" onClick={handleReopen} id="btn-reopen">
                Reopen
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleAnalyze}
              loading={analyzing}
              disabled={analyzing}
              id="btn-run-analysis"
            >
              <Play size={14} /> Run Analysis
            </Button>
          </div>
        </div>

        {/* Main layout */}
        <div className="detail-body">
          {/* Left: tabs */}
          <div className="detail-main">
            <div className="tabs-bar">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="tab-content">
              {/* ─── Overview ─── */}
              {activeTab === 'overview' && (
                <div className="overview-tab">
                  {incident.description && (
                    <Card className="desc-card">
                      <h3 className="card-section-title">Description</h3>
                      <p className="desc-text">{incident.description}</p>
                    </Card>
                  )}
                  {incident.business_impact && (
                    <Card className="desc-card">
                      <h3 className="card-section-title">Business Impact</h3>
                      <p className="desc-text">{incident.business_impact}</p>
                    </Card>
                  )}
                  {/* Upload logs */}
                  <Card className="desc-card">
                    <h3 className="card-section-title">Upload Logs</h3>
                    <p className="upload-hint">Upload application logs to enable AI root cause analysis.</p>
                    <LogUploader incidentId={id} onDone={() => { loadLogs(); loadAnalyses() }} />
                    {logs.jobs.length > 0 && (
                      <div className="jobs-status">
                        {logs.jobs.map(j => (
                          <div key={j.id} className="job-row">
                            <span className={`job-status-dot ${j.status}`} />
                            <span>{j.status} — {j.parsed_events} events parsed</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                  {/* Analyses list */}
                  {analyses.length > 0 && (
                    <Card className="desc-card">
                      <h3 className="card-section-title">Analysis Runs</h3>
                      <div className="analyses-list">
                        {analyses.map(a => (
                          <div key={a.id} className="analysis-row" onClick={() => loadAnalysisDetails(a.id)}>
                            <StatusBadge status={a.status} />
                            <span className="analysis-model">{a.llm_model}</span>
                            <span className="text-sm text-muted">{formatTs(a.created_at)}</span>
                            {a.status === 'FAILED' && a.error_message && (
                              <span className="analysis-error">{a.error_message.slice(0, 60)}…</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </Card>
                  )}
                </div>
              )}

              {/* ─── Logs ─── */}
              {activeTab === 'logs' && (
                <Card padding={false}>
                  {logsLoading ? (
                    <div className="loading-state"><div className="loading-spinner" /></div>
                  ) : logs.items.length === 0 ? (
                    <div className="empty-state" style={{ padding: 40 }}>
                      <FileText size={28} color="var(--color-gray-300)" />
                      <p>No log events. Upload a log file from the Overview tab.</p>
                    </div>
                  ) : (
                    <div className="log-table-wrap">
                      <table className="data-table log-table">
                        <thead>
                          <tr>
                            <th style={{ width: 40 }}>#</th>
                            <th style={{ width: 160 }}>Timestamp</th>
                            <th style={{ width: 80 }}>Level</th>
                            <th style={{ width: 120 }}>Source</th>
                            <th>Message</th>
                          </tr>
                        </thead>
                        <tbody>
                          {logs.items.map(e => (
                            <tr key={e.id} className={`log-row log-${e.level?.toLowerCase()}`}>
                              <td className="text-sm text-muted">{e.line_number || '—'}</td>
                              <td className="text-sm log-ts">{e.timestamp ? new Date(e.timestamp).toISOString().replace('T', ' ').slice(0, 19) : '—'}</td>
                              <td>
                                <span className={`log-level log-level-${e.level?.toLowerCase()}`}>
                                  {e.level}
                                </span>
                              </td>
                              <td className="text-sm truncate" style={{ maxWidth: 120 }}>{e.source || '—'}</td>
                              <td className="log-message">{e.message}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {logs.total > 100 && (
                        <div className="log-truncate-note">
                          Showing first 100 of {logs.total} events. Use Log Explorer for full view.
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )}

              {/* ─── Analysis ─── */}
              {activeTab === 'analysis' && (
                <div>
                  {analyzing && (
                    <Card className="desc-card">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Loader size={16} className="spin" />
                        <span>Analysis running… Ollama may take 30–120s. Polling every 5s.</span>
                      </div>
                    </Card>
                  )}
                  {analysisLoading ? (
                    <div className="loading-state"><div className="loading-spinner" /></div>
                  ) : selectedAnalysis ? (
                    <Card className="desc-card">
                      <h3 className="card-section-title">Analysis Results</h3>
                      {selectedAnalysis.status === 'FAILED' ? (
                        <div className="analysis-error-box">
                          <XCircle size={16} /> {selectedAnalysis.error_message}
                        </div>
                      ) : selectedAnalysis.status === 'INSUFFICIENT_DATA' ? (
                        <div className="analysis-warn-box">
                          <AlertTriangle size={16} /> Insufficient data: {selectedAnalysis.error_message}
                        </div>
                      ) : (
                        <RCAPanel analysis={selectedAnalysis} />
                      )}
                    </Card>
                  ) : analyses.length > 0 ? (
                    <Card className="desc-card">
                      <p className="text-muted">Select an analysis run from Overview to view details.</p>
                    </Card>
                  ) : (
                    <Card className="desc-card">
                      <div className="empty-analysis">
                        <Play size={28} color="var(--color-gray-300)" />
                        <p>No analysis yet.</p>
                        <p className="text-muted">Upload logs first, then click "Run Analysis".</p>
                        <Button size="sm" onClick={handleAnalyze} loading={analyzing} id="btn-start-analysis">
                          <Play size={14} /> Run Analysis
                        </Button>
                      </div>
                    </Card>
                  )}
                </div>
              )}

              {/* ─── Timeline ─── */}
              {activeTab === 'timeline' && (
                <Card padding={false}>
                  {incident.events?.length === 0 ? (
                    <div className="empty-state" style={{ padding: 40 }}>No timeline events yet.</div>
                  ) : (
                    <div className="timeline">
                      {[...incident.events].reverse().map((e, i) => (
                        <div key={e.id} className="timeline-item">
                          <div className="timeline-dot" />
                          <div className="timeline-content">
                            <div className="timeline-type">{e.event_type.replace('_', ' ')}</div>
                            <div className="timeline-desc">{e.description}</div>
                            <div className="timeline-ts text-sm text-muted">{formatTs(e.occurred_at)}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              )}

              {/* ─── Comments ─── */}
              {activeTab === 'comments' && (
                <div className="comments-tab">
                  {incident.comments?.map(c => (
                    <Card key={c.id} className="comment-card">
                      <div className="comment-header">
                        <div className="comment-avatar">{c.author_id?.slice(0, 2).toUpperCase() || 'SY'}</div>
                        <div>
                          <div className="comment-author">Engineer</div>
                          <div className="text-sm text-muted">{formatTs(c.created_at)}</div>
                        </div>
                        {c.is_internal && <span className="internal-tag">Internal</span>}
                      </div>
                      <p className="comment-body">{c.content}</p>
                    </Card>
                  ))}
                  <Card className="desc-card">
                    <form onSubmit={handleComment}>
                      <label className="form-label" htmlFor="comment-input">Add Comment</label>
                      <textarea
                        id="comment-input"
                        className="form-textarea"
                        value={comment}
                        onChange={e => setComment(e.target.value)}
                        placeholder="Add an internal note or update…"
                        rows={3}
                      />
                      <Button type="submit" size="sm" loading={commentLoading} style={{ marginTop: 8 }} id="btn-submit-comment">
                        <MessageSquare size={13} /> Add Comment
                      </Button>
                    </form>
                  </Card>
                </div>
              )}
            </div>
          </div>

          {/* Right: metadata */}
          <div className="detail-sidebar">
            <Card>
              <h3 className="card-section-title">Incident Details</h3>
              <div className="meta-list">
                <div className="meta-row"><span>Number</span><strong>{incident.number}</strong></div>
                <div className="meta-row"><span>Severity</span><SeverityBadge severity={incident.severity} /></div>
                <div className="meta-row"><span>Status</span><StatusBadge status={incident.status} /></div>
                <div className="meta-row"><span>Category</span><span>{incident.category || '—'}</span></div>
                <div className="meta-row"><span>Component</span><span>{incident.affected_component || '—'}</span></div>
                <div className="meta-row"><span>Environment</span><span>{incident.environment_name || '—'}</span></div>
                <div className="meta-row"><span>Reporter</span><span>{incident.reporter?.full_name || '—'}</span></div>
                <div className="meta-row"><span>Assignee</span><span>{incident.assignee?.full_name || 'Unassigned'}</span></div>
                <div className="meta-row"><span>Created</span><span>{formatTs(incident.created_at)}</span></div>
                {incident.resolved_at && <div className="meta-row"><span>Resolved</span><span>{formatTs(incident.resolved_at)}</span></div>}
                <div className="meta-row"><span>SLA</span><span>{incident.sla_breach ? '⚠ Breached' : '✓ OK'}</span></div>
              </div>
            </Card>

            <Card style={{ marginTop: 12 }}>
              <h3 className="card-section-title">Attachments ({incident.artifacts?.length || 0})</h3>
              {incident.artifacts?.length ? (
                <div className="artifacts-list">
                  {incident.artifacts.map(a => (
                    <div key={a.id} className="artifact-item">
                      <FileText size={13} />
                      <span>{a.filename}</span>
                      <span className="text-sm text-muted">{(a.file_size_bytes / 1024).toFixed(1)}KB</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted">No attachments yet.</p>
              )}
            </Card>
          </div>
        </div>
      </div>

      {/* Resolve modal */}
      <Modal isOpen={resolveOpen} onClose={() => setResolveOpen(false)} title="Resolve Incident" size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setResolveOpen(false)}>Cancel</Button>
            <Button variant="success" onClick={handleResolve} id="btn-confirm-resolve">Mark Resolved</Button>
          </>
        }
      >
        <div>
          <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
            Only mark as resolved when the issue is actually fixed and verified.
          </p>
          <label className="form-label" htmlFor="resolution-notes">Resolution Notes</label>
          <textarea
            id="resolution-notes"
            className="form-textarea"
            value={resolutionNotes}
            onChange={e => setResolutionNotes(e.target.value)}
            placeholder="What fixed the issue? What was the root cause?"
            rows={4}
          />
        </div>
      </Modal>
    </Layout>
  )
}
