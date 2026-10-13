import { useState, useEffect, useCallback } from 'react'
import {
  Wrench, CheckCircle, XCircle, Clock, Play, Shield,
  ChevronDown, ChevronUp, AlertTriangle, CheckCheck
} from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { Button } from '../../components/Button/Button'
import { Badge } from '../../components/Badge/Badge'
import { Modal } from '../../components/Modal/Modal'
import { remediationAPI, incidentsAPI, analysisAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Remediation.css'

function ActionCard({ action, onRequestApproval, onApprove, onReject, onExecute }) {
  const [open, setOpen] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [execResult, setExecResult] = useState(null)

  const riskColour = {
    LOW: 'var(--color-low)', MEDIUM: 'var(--color-medium)',
    HIGH: 'var(--color-high)', CRITICAL: 'var(--color-critical)'
  }[action.risk_level] || 'var(--color-gray-500)'

  const handleExecute = async () => {
    setExecuting(true)
    try {
      const res = await onExecute(action.id)
      setExecResult(res)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className={`action-item risk-border-${action.risk_level?.toLowerCase()}`}>
      <div className="action-item-header" onClick={() => setOpen(o => !o)}>
        <Wrench size={14} color="var(--color-gray-500)" />
        <div className="action-item-info">
          <span className="action-item-title">{action.title}</span>
          <span className="action-item-key">{action.action_key}</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="risk-chip" style={{ color: riskColour, borderColor: riskColour }}>
            {action.risk_level}
          </span>
          {action.requires_approval && (
            <span className="approval-chip">Approval required</span>
          )}
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>

      {open && (
        <div className="action-item-body">
          <p className="action-item-desc">{action.description}</p>
          {action.expected_outcome && (
            <p className="action-item-outcome"><strong>Expected outcome:</strong> {action.expected_outcome}</p>
          )}
          {action.rollback_procedure && (
            <p className="action-item-rollback"><strong>Rollback:</strong> {action.rollback_procedure}</p>
          )}

          {execResult && (
            <div className={`exec-result ${execResult.success ? 'exec-success' : 'exec-fail'}`}>
              {execResult.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
              <span>{execResult.output || execResult.error}</span>
              {execResult.verified_resolved !== undefined && (
                <span className="exec-verified">
                  {execResult.verified_resolved ? '✓ Issue resolved' : '⚠ Not yet resolved'}
                </span>
              )}
            </div>
          )}

          <div className="action-item-buttons">
            {action.requires_approval && !action._approved && (
              <Button size="sm" variant="secondary" onClick={() => onRequestApproval(action.id)} id={`btn-req-approval-${action.id}`}>
                <Clock size={13} /> Request Approval
              </Button>
            )}
            {action._pending_approval_id && (
              <>
                <Button size="sm" variant="success" onClick={() => onApprove(action._pending_approval_id)} id={`btn-approve-${action.id}`}>
                  <CheckCheck size={13} /> Approve
                </Button>
                <Button size="sm" variant="danger" onClick={() => onReject(action._pending_approval_id)} id={`btn-reject-${action.id}`}>
                  <XCircle size={13} /> Reject
                </Button>
              </>
            )}
            {(!action.requires_approval || action._approved) && (
              <Button size="sm" onClick={handleExecute} loading={executing} id={`btn-execute-${action.id}`}>
                <Play size={13} /> Execute
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function Remediation() {
  const [registry, setRegistry] = useState([])
  const [incidents, setIncidents] = useState([])
  const [selectedIncident, setSelectedIncident] = useState('')
  const [analyses, setAnalyses] = useState([])
  const [selectedAnalysis, setSelectedAnalysis] = useState(null)
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(false)

  // Propose modal
  const [proposeOpen, setProposeOpen] = useState(false)
  const [proposeForm, setProposeForm] = useState({ action_key: '', title: '', description: '', risk_level: 'LOW', requires_approval: false })
  const [proposing, setProposing] = useState(false)

  const toast = useToast()

  useEffect(() => {
    remediationAPI.registry().then(r => setRegistry(r.data.actions)).catch(() => {})
    incidentsAPI.list({ page_size: 100 }).then(r => setIncidents(r.data.items)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedIncident) { setAnalyses([]); setActions([]); return }
    analysisAPI.list(selectedIncident).then(r => {
      setAnalyses(r.data)
      const completed = r.data.find(a => a.status === 'COMPLETED')
      if (completed) loadAnalysisActions(completed.id)
    }).catch(() => {})
  }, [selectedIncident])

  const loadAnalysisActions = async (analysisId) => {
    setLoading(true)
    try {
      const res = await analysisAPI.get(analysisId)
      setSelectedAnalysis(res.data)
      setActions(res.data.remediation_proposals || [])
    } catch {
      toast.error('Failed to load remediation actions')
    } finally {
      setLoading(false)
    }
  }

  const handleRequestApproval = async (actionId) => {
    try {
      await remediationAPI.requestApproval(actionId, { reason: 'Requested by engineer' })
      toast.success('Approval request submitted')
      setActions(prev => prev.map(a => a.id === actionId ? { ...a, _pending_approval_id: 'pending' } : a))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to request approval')
    }
  }

  const handleApprove = async (approvalId) => {
    try {
      await remediationAPI.approve(approvalId, { review_notes: 'Approved by engineer' })
      toast.success('Action approved')
      setActions(prev => prev.map(a => a._pending_approval_id === approvalId ? { ...a, _approved: true, _pending_approval_id: null } : a))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to approve')
    }
  }

  const handleReject = async (approvalId) => {
    try {
      await remediationAPI.reject(approvalId, { review_notes: 'Rejected' })
      toast.info('Action rejected')
      setActions(prev => prev.map(a => a._pending_approval_id === approvalId ? { ...a, _pending_approval_id: null } : a))
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to reject')
    }
  }

  const handleExecute = async (actionId) => {
    try {
      const res = await remediationAPI.execute(actionId)
      toast.success(`Execution ${res.data.status}`)
      return res.data
    } catch (err) {
      const msg = err.response?.data?.detail || 'Execution failed'
      toast.error(msg)
      return { success: false, error: msg }
    }
  }

  const handlePropose = async (e) => {
    e.preventDefault()
    if (!selectedAnalysis) { toast.error('Select an analysis first'); return }
    setProposing(true)
    try {
      await remediationAPI.propose(selectedAnalysis.id, proposeForm)
      toast.success('Remediation action proposed')
      setProposeOpen(false)
      loadAnalysisActions(selectedAnalysis.id)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to propose action')
    } finally {
      setProposing(false)
    }
  }

  return (
    <Layout title="Remediation">
      <div className="remediation-page fade-in">
        <div className="page-header">
          <div>
            <h2 className="page-title">Remediation Workflow</h2>
            <p className="page-sub">Review, approve and execute AI-recommended actions safely</p>
          </div>
          {selectedAnalysis && (
            <Button size="sm" onClick={() => setProposeOpen(true)} id="btn-propose-action">
              <Wrench size={14} /> Propose Action
            </Button>
          )}
        </div>

        <div className="remediation-layout">
          {/* Left: incident & analysis selector */}
          <div className="remediation-sidebar">
            <Card>
              <h3 className="card-section-title">Select Incident</h3>
              <select
                id="rem-incident"
                className="form-select"
                value={selectedIncident}
                onChange={e => { setSelectedIncident(e.target.value); setSelectedAnalysis(null); setActions([]) }}
              >
                <option value="">— Select incident —</option>
                {incidents.map(i => <option key={i.id} value={i.id}>{i.number}: {i.title.slice(0, 40)}</option>)}
              </select>

              {analyses.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h3 className="card-section-title">Analysis Runs</h3>
                  <div className="analysis-selector">
                    {analyses.map(a => (
                      <button
                        key={a.id}
                        className={`analysis-btn ${selectedAnalysis?.id === a.id ? 'active' : ''} ${a.status !== 'COMPLETED' ? 'disabled' : ''}`}
                        onClick={() => a.status === 'COMPLETED' && loadAnalysisActions(a.id)}
                        disabled={a.status !== 'COMPLETED'}
                      >
                        <span className={`status-dot status-dot-${a.status?.toLowerCase()}`} />
                        <span>{a.status} — {a.llm_model}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </Card>

            <Card style={{ marginTop: 12 }}>
              <h3 className="card-section-title">
                <Shield size={13} style={{ display: 'inline', marginRight: 4 }} />
                Action Registry
              </h3>
              <p className="text-sm text-muted" style={{ marginBottom: 10 }}>
                Only registered actions can be executed. No arbitrary commands.
              </p>
              <div className="registry-list">
                {registry.map(a => (
                  <div key={a.key} className="registry-item">
                    <strong className="registry-key">{a.key}</strong>
                    <span className={`risk-chip risk-chip-${a.risk_level?.toLowerCase()}`}>{a.risk_level}</span>
                    <p className="registry-desc">{a.description}</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Right: actions */}
          <div className="remediation-main">
            {!selectedAnalysis ? (
              <Card className="rem-empty">
                <Wrench size={36} color="var(--color-gray-300)" />
                <p>Select an incident and a completed analysis to view remediation actions.</p>
              </Card>
            ) : loading ? (
              <Card className="rem-empty"><div className="loading-spinner" /></Card>
            ) : actions.length === 0 ? (
              <Card className="rem-empty">
                <AlertTriangle size={28} color="var(--color-gray-300)" />
                <p>No remediation actions proposed yet.</p>
                <p className="text-sm text-muted">Run an analysis, or propose one manually.</p>
              </Card>
            ) : (
              <Card>
                <div className="card-section-title" style={{ marginBottom: 16 }}>
                  Proposed Actions ({actions.length})
                </div>
                <div className="actions-list">
                  {actions.map(action => (
                    <ActionCard
                      key={action.id}
                      action={action}
                      onRequestApproval={handleRequestApproval}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      onExecute={handleExecute}
                    />
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Propose Action Modal */}
      <Modal
        isOpen={proposeOpen}
        onClose={() => setProposeOpen(false)}
        title="Propose Remediation Action"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setProposeOpen(false)}>Cancel</Button>
            <Button onClick={handlePropose} loading={proposing} id="btn-submit-propose">Propose</Button>
          </>
        }
      >
        <form className="create-form" onSubmit={handlePropose}>
          <div className="form-group">
            <label className="form-label" htmlFor="prop-action-key">Action Type</label>
            <select
              id="prop-action-key"
              className="form-select"
              value={proposeForm.action_key}
              onChange={e => setProposeForm(f => ({
                ...f,
                action_key: e.target.value,
                title: registry.find(r => r.key === e.target.value)?.name || f.title,
                risk_level: registry.find(r => r.key === e.target.value)?.risk_level || f.risk_level,
                requires_approval: registry.find(r => r.key === e.target.value)?.requires_approval || false,
              }))}
              required
            >
              <option value="">— Select action type —</option>
              {registry.map(r => <option key={r.key} value={r.key}>{r.name} ({r.risk_level})</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="prop-title">Title</label>
            <input id="prop-title" className="form-input" value={proposeForm.title}
              onChange={e => setProposeForm(f => ({ ...f, title: e.target.value }))} required />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="prop-desc">Description</label>
            <textarea id="prop-desc" className="form-textarea" value={proposeForm.description}
              onChange={e => setProposeForm(f => ({ ...f, description: e.target.value }))} required rows={3} />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="prop-risk">Risk Level</label>
              <select id="prop-risk" className="form-select" value={proposeForm.risk_level}
                onChange={e => setProposeForm(f => ({ ...f, risk_level: e.target.value }))}>
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ justifyContent: 'flex-end' }}>
              <label className="form-label" htmlFor="prop-approval">
                <input
                  id="prop-approval"
                  type="checkbox"
                  checked={proposeForm.requires_approval}
                  onChange={e => setProposeForm(f => ({ ...f, requires_approval: e.target.checked }))}
                  style={{ marginRight: 6 }}
                />
                Requires Approval
              </label>
            </div>
          </div>
        </form>
      </Modal>
    </Layout>
  )
}
