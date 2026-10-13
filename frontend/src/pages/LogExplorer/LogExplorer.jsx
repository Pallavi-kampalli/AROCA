import { useState, useEffect, useCallback } from 'react'
import { Search, Filter, RefreshCw, FileText, ChevronLeft, ChevronRight } from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { Button } from '../../components/Button/Button'
import { logsAPI, incidentsAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './LogExplorer.css'

const LOG_LEVELS = ['ERROR', 'CRITICAL', 'WARNING', 'INFO', 'DEBUG', 'UNKNOWN']

const levelClass = (lvl) => {
  const map = { ERROR: 'error', CRITICAL: 'critical', WARNING: 'warning', INFO: 'info', DEBUG: 'debug', UNKNOWN: 'unknown' }
  return map[lvl] || 'unknown'
}

export function LogExplorer() {
  const [incidents, setIncidents] = useState([])
  const [selectedIncident, setSelectedIncident] = useState('')
  const [logs, setLogs] = useState({ items: [], total: 0, jobs: [] })
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [levelFilter, setLevelFilter] = useState('')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState(null)
  const toast = useToast()
  const PAGE_SIZE = 100

  useEffect(() => {
    incidentsAPI.list({ page_size: 100 })
      .then(res => setIncidents(res.data.items))
      .catch(() => {})
  }, [])

  const loadLogs = useCallback(async () => {
    if (!selectedIncident) return
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (levelFilter) params.level = levelFilter
      if (search) params.search = search
      const res = await logsAPI.list(selectedIncident, params)
      setLogs(res.data)
    } catch {
      toast.error('Failed to load logs')
    } finally {
      setLoading(false)
    }
  }, [selectedIncident, page, levelFilter, search])

  useEffect(() => { loadLogs() }, [loadLogs])

  const totalPages = Math.ceil(logs.total / PAGE_SIZE)
  const levelCounts = logs.items.reduce((acc, e) => {
    acc[e.level] = (acc[e.level] || 0) + 1
    return acc
  }, {})

  return (
    <Layout title="Log Explorer">
      <div className="log-explorer fade-in">
        <div className="page-header">
          <div>
            <h2 className="page-title">Log Explorer</h2>
            <p className="page-sub">Browse and search parsed log events across incidents</p>
          </div>
        </div>

        {/* Controls */}
        <Card className="log-controls-card">
          <div className="log-controls">
            <div className="form-group" style={{ minWidth: 220 }}>
              <label className="form-label" htmlFor="log-incident-select">Incident</label>
              <select
                id="log-incident-select"
                className="form-select"
                value={selectedIncident}
                onChange={e => { setSelectedIncident(e.target.value); setPage(1) }}
              >
                <option value="">— Select incident —</option>
                {incidents.map(i => (
                  <option key={i.id} value={i.id}>{i.number}: {i.title.slice(0, 50)}</option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label" htmlFor="log-search">Search Messages</label>
              <div className="search-field">
                <Search size={14} className="search-icon" />
                <input
                  id="log-search"
                  className="form-input search-input"
                  placeholder="Search log messages…"
                  value={search}
                  onChange={e => { setSearch(e.target.value); setPage(1) }}
                  disabled={!selectedIncident}
                />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="log-level-filter">Level</label>
              <select
                id="log-level-filter"
                className="form-select"
                value={levelFilter}
                onChange={e => { setLevelFilter(e.target.value); setPage(1) }}
                disabled={!selectedIncident}
                style={{ width: 130 }}
              >
                <option value="">All Levels</option>
                {LOG_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div className="form-group" style={{ justifyContent: 'flex-end', marginTop: 20 }}>
              <Button variant="ghost" size="sm" onClick={loadLogs} disabled={!selectedIncident} id="btn-refresh-logs">
                <RefreshCw size={14} className={loading ? 'spin' : ''} />
              </Button>
            </div>
          </div>

          {/* Level distribution pills */}
          {logs.items.length > 0 && (
            <div className="level-dist">
              {LOG_LEVELS.filter(l => levelCounts[l]).map(l => (
                <button
                  key={l}
                  className={`level-pill level-pill-${levelClass(l)} ${levelFilter === l ? 'active' : ''}`}
                  onClick={() => { setLevelFilter(levelFilter === l ? '' : l); setPage(1) }}
                >
                  {l} <strong>{levelCounts[l]}</strong>
                </button>
              ))}
            </div>
          )}
        </Card>

        {/* Job status */}
        {logs.jobs?.length > 0 && (
          <div className="jobs-bar">
            {logs.jobs.map(j => (
              <div key={j.id} className={`job-chip job-chip-${j.status}`}>
                <span className={`job-status-dot ${j.status}`} />
                {j.status} · {j.parsed_events || 0} events parsed
              </div>
            ))}
          </div>
        )}

        {/* Log table */}
        {!selectedIncident ? (
          <Card className="log-empty-card">
            <FileText size={36} color="var(--color-gray-300)" />
            <p>Select an incident to explore its logs.</p>
          </Card>
        ) : loading ? (
          <Card className="log-empty-card">
            <div className="loading-spinner" />
            <p>Loading logs…</p>
          </Card>
        ) : logs.items.length === 0 ? (
          <Card className="log-empty-card">
            <Filter size={32} color="var(--color-gray-300)" />
            <p>No log events found.</p>
            <p className="text-sm text-muted">Upload a log file from the Incident Detail page.</p>
          </Card>
        ) : (
          <Card padding={false}>
            <div className="log-table-stats">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, logs.total)} of <strong>{logs.total}</strong> events</span>
              {logs.total > PAGE_SIZE && (
                <div className="pagination-controls">
                  <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)} id="btn-logs-prev">
                    <ChevronLeft size={14} />
                  </Button>
                  <span style={{ fontSize: 12 }}>{page}/{totalPages}</span>
                  <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} id="btn-logs-next">
                    <ChevronRight size={14} />
                  </Button>
                </div>
              )}
            </div>

            <div className="log-scroll-wrap">
              <table className="log-explorer-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Timestamp</th>
                    <th>Level</th>
                    <th>Source</th>
                    <th>Service</th>
                    <th>Message</th>
                    <th>TraceID</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.items.map(e => (
                    <>
                      <tr
                        key={e.id}
                        className={`log-explorer-row log-row-${levelClass(e.level)} ${expanded === e.id ? 'expanded' : ''}`}
                        onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                      >
                        <td className="log-cell-num">{e.line_number || '—'}</td>
                        <td className="log-cell-ts">
                          {e.timestamp
                            ? new Date(e.timestamp).toISOString().replace('T', '\n').slice(0, 19)
                            : '—'}
                        </td>
                        <td>
                          <span className={`log-level-badge log-level-${levelClass(e.level)}`}>{e.level}</span>
                        </td>
                        <td className="log-cell-source">{e.source || '—'}</td>
                        <td className="log-cell-service">{e.service_name || '—'}</td>
                        <td className="log-cell-msg">{e.message}</td>
                        <td className="log-cell-trace">{e.correlation_id ? e.correlation_id.slice(0, 12) + '…' : '—'}</td>
                      </tr>
                      {expanded === e.id && (
                        <tr key={`${e.id}-exp`} className="log-expanded-row">
                          <td colSpan={7}>
                            <div className="log-expanded-content">
                              <div className="log-raw-line">
                                <span className="log-detail-label">Raw line:</span>
                                <pre>{e.message}</pre>
                              </div>
                              {e.correlation_id && (
                                <div><span className="log-detail-label">Trace/Correlation ID:</span> <code>{e.correlation_id}</code></div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </Layout>
  )
}
