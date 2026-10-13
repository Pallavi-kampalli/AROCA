import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Plus, Search, Filter, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { SeverityBadge, StatusBadge } from '../../components/Badge/Badge'
import { Button } from '../../components/Button/Button'
import { Modal } from '../../components/Modal/Modal'
import { incidentsAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Incidents.css'

const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
const STATUSES = ['NEW', 'TRIAGED', 'INVESTIGATING', 'AWAITING_APPROVAL', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', 'REOPENED']

function CreateIncidentModal({ isOpen, onClose, onCreated }) {
  const toast = useToast()
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    title: '', description: '', severity: 'MEDIUM',
    category: '', affected_component: '', business_impact: '', environment_name: ''
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) { toast.error('Title is required'); return }
    setLoading(true)
    try {
      const res = await incidentsAPI.create(form)
      toast.success(`Incident ${res.data.number} created`)
      onCreated(res.data)
      onClose()
      setForm({ title: '', description: '', severity: 'MEDIUM', category: '', affected_component: '', business_impact: '', environment_name: '' })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create incident')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Incident" size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} id="btn-cancel-incident">Cancel</Button>
          <Button onClick={handleSubmit} loading={loading} id="btn-submit-incident">Create Incident</Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="create-form">
        <div className="form-row">
          <div className="form-group full">
            <label className="form-label" htmlFor="inc-title">Title *</label>
            <input id="inc-title" className="form-input" value={form.title} onChange={e => set('title', e.target.value)} placeholder="Brief description of the incident" required />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label" htmlFor="inc-severity">Severity</label>
            <select id="inc-severity" className="form-select" value={form.severity} onChange={e => set('severity', e.target.value)}>
              {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="inc-category">Category</label>
            <input id="inc-category" className="form-input" value={form.category} onChange={e => set('category', e.target.value)} placeholder="e.g. Database, Network, Application" />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label" htmlFor="inc-component">Affected Component</label>
            <input id="inc-component" className="form-input" value={form.affected_component} onChange={e => set('affected_component', e.target.value)} placeholder="e.g. API Gateway, Auth Service" />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="inc-env">Environment</label>
            <input id="inc-env" className="form-input" value={form.environment_name} onChange={e => set('environment_name', e.target.value)} placeholder="e.g. production, staging" />
          </div>
        </div>
        <div className="form-group full">
          <label className="form-label" htmlFor="inc-description">Description</label>
          <textarea id="inc-description" className="form-textarea" value={form.description} onChange={e => set('description', e.target.value)} placeholder="Detailed description of what happened..." rows={4} />
        </div>
        <div className="form-group full">
          <label className="form-label" htmlFor="inc-impact">Business Impact</label>
          <textarea id="inc-impact" className="form-textarea" value={form.business_impact} onChange={e => set('business_impact', e.target.value)} placeholder="Who is affected? What business processes are impacted?" rows={2} />
        </div>
      </form>
    </Modal>
  )
}

export function Incidents() {
  const [incidents, setIncidents] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const toast = useToast()
  const navigate = useNavigate()
  const PAGE_SIZE = 20

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search) params.search = search
      if (severityFilter) params.severity = severityFilter
      if (statusFilter) params.status = statusFilter
      const res = await incidentsAPI.list(params)
      setIncidents(res.data.items)
      setTotal(res.data.total)
    } catch {
      toast.error('Failed to load incidents')
    } finally {
      setLoading(false)
    }
  }, [page, search, severityFilter, statusFilter])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const sev = searchParams.get('severity')
    const st = searchParams.get('status')
    if (sev) setSeverityFilter(sev)
    if (st) setStatusFilter(st === 'open' ? '' : st)
  }, [searchParams])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  }

  return (
    <Layout title="Incident Management">
      <div className="incidents-page fade-in">
        <div className="page-header">
          <div>
            <h2 className="page-title">Incidents</h2>
            <p className="page-sub">{total} total incidents</p>
          </div>
          <Button onClick={() => setCreateOpen(true)} id="btn-create-incident">
            <Plus size={14} /> New Incident
          </Button>
        </div>

        {/* Filters */}
        <Card className="filters-card">
          <div className="filters-row">
            <div className="search-field">
              <Search size={14} className="search-icon" />
              <input
                id="incident-search"
                className="form-input search-input"
                placeholder="Search incidents…"
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1) }}
              />
            </div>
            <select id="filter-severity" className="form-select filter-select" value={severityFilter}
              onChange={e => { setSeverityFilter(e.target.value); setPage(1) }}>
              <option value="">All Severities</option>
              {SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select id="filter-status" className="form-select filter-select" value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1) }}>
              <option value="">All Statuses</option>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
            <Button variant="secondary" size="sm" onClick={() => { setSearch(''); setSeverityFilter(''); setStatusFilter(''); setPage(1) }}>
              Clear
            </Button>
            <Button variant="ghost" size="sm" onClick={load} id="btn-refresh-incidents">
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
            </Button>
          </div>
        </Card>

        {/* Table */}
        <Card padding={false}>
          {loading ? (
            <div className="loading-state">
              <div className="loading-spinner" />
              <span>Loading incidents…</span>
            </div>
          ) : incidents.length === 0 ? (
            <div className="empty-state" style={{ padding: 60 }}>
              <Filter size={32} color="var(--color-gray-300)" />
              <p style={{ fontWeight: 600, color: 'var(--color-gray-600)' }}>No incidents found</p>
              <p>Create your first incident to get started with TraceIQ analysis.</p>
              <Button onClick={() => setCreateOpen(true)} size="sm" id="btn-create-first">
                <Plus size={14} /> Create Incident
              </Button>
            </div>
          ) : (
            <>
              <table className="data-table incidents-table">
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Category</th>
                    <th>Environment</th>
                    <th>Created</th>
                    <th>SLA</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.map(inc => (
                    <tr key={inc.id} className="data-table-row" onClick={() => navigate(`/incidents/${inc.id}`)}>
                      <td>
                        <span className="inc-number">{inc.number}</span>
                      </td>
                      <td className="inc-title">{inc.title}</td>
                      <td><SeverityBadge severity={inc.severity} /></td>
                      <td><StatusBadge status={inc.status} /></td>
                      <td className="text-muted">{inc.category || '—'}</td>
                      <td className="text-muted">{inc.environment_name || '—'}</td>
                      <td className="text-muted text-sm">{formatDate(inc.created_at)}</td>
                      <td>
                        {inc.sla_breach ? (
                          <span className="sla-breach">Breached</span>
                        ) : (
                          <span className="sla-ok">OK</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="pagination">
                  <span className="pagination-info">
                    Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
                  </span>
                  <div className="pagination-controls">
                    <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)} id="btn-prev-page">
                      <ChevronLeft size={14} /> Prev
                    </Button>
                    <span className="pagination-page">{page} / {totalPages}</span>
                    <Button variant="secondary" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)} id="btn-next-page">
                      Next <ChevronRight size={14} />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      <CreateIncidentModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(inc) => navigate(`/incidents/${inc.id}`)}
      />
    </Layout>
  )
}
