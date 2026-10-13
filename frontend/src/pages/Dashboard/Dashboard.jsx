import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, TrendingUp, Clock, CheckCircle2, ShieldAlert,
  Activity, Users, BarChart2, RefreshCw
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts'
import { Layout } from '../../components/Layout/Layout'
import { MetricCard } from '../../components/Card/Card'
import { Card } from '../../components/Card/Card'
import { SeverityBadge, StatusBadge } from '../../components/Badge/Badge'
import { Button } from '../../components/Button/Button'
import { dashboardAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Dashboard.css'

const SEV_COLORS = {
  CRITICAL: '#dc2626',
  HIGH: '#ea580c',
  MEDIUM: '#ca8a04',
  LOW: '#16a34a',
  INFO: '#0284c7',
}

const STATUS_COLORS = {
  NEW: '#1d4ed8',
  TRIAGED: '#6d28d9',
  INVESTIGATING: '#c2410c',
  IN_PROGRESS: '#1e40af',
  RESOLVED: '#059669',
  CLOSED: '#6b7280',
  REOPENED: '#b45309',
}

function EmptyState({ message }) {
  return (
    <div className="empty-state">
      <BarChart2 size={32} color="var(--color-gray-300)" />
      <p>{message}</p>
    </div>
  )
}

export function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [trends, setTrends] = useState(null)
  const [dists, setDists] = useState(null)
  const [loading, setLoading] = useState(true)
  const [trendDays, setTrendDays] = useState(30)
  const toast = useToast()
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try {
      const [s, t, d] = await Promise.all([
        dashboardAPI.summary(),
        dashboardAPI.trends(trendDays),
        dashboardAPI.distributions(),
      ])
      setSummary(s.data)
      setTrends(t.data)
      setDists(d.data)
    } catch (e) {
      toast.error('Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [trendDays])

  const formatDuration = (minutes) => {
    if (!minutes) return '—'
    if (minutes < 60) return `${Math.round(minutes)}m`
    return `${Math.round(minutes / 60)}h ${Math.round(minutes % 60)}m`
  }

  return (
    <Layout title="Command Center">
      <div className="dashboard fade-in">
        <div className="dashboard-page-header">
          <div>
            <h2 className="page-title">Command Center</h2>
            <p className="page-sub">Live metrics computed from active PostgreSQL records</p>
          </div>
          <Button variant="secondary" size="sm" onClick={load} id="btn-refresh-dashboard">
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </Button>
        </div>

        {/* Metrics Grid */}
        <div className="metrics-grid">
          <MetricCard
            id="metric-total"
            label="Total Incidents"
            value={loading ? '…' : summary?.total_incidents ?? 0}
            icon={Activity}
            onClick={() => navigate('/incidents')}
            sub="All time"
          />
          <MetricCard
            id="metric-open"
            label="Open Incidents"
            value={loading ? '…' : summary?.open_incidents ?? 0}
            icon={AlertTriangle}
            accentColor={summary?.open_incidents > 0 ? 'var(--color-high)' : undefined}
            onClick={() => navigate('/incidents?status=open')}
            sub="Requiring attention"
          />
          <MetricCard
            id="metric-critical"
            label="Critical"
            value={loading ? '…' : summary?.critical_incidents ?? 0}
            icon={ShieldAlert}
            accentColor={summary?.critical_incidents > 0 ? 'var(--color-critical)' : undefined}
            onClick={() => navigate('/incidents?severity=CRITICAL')}
            sub="Open critical incidents"
          />
          <MetricCard
            id="metric-approval"
            label="Awaiting Approval"
            value={loading ? '…' : summary?.awaiting_approval ?? 0}
            icon={Clock}
            accentColor={summary?.awaiting_approval > 0 ? 'var(--color-warning)' : undefined}
            onClick={() => navigate('/remediation')}
            sub="Remediation pending review"
          />
          <MetricCard
            id="metric-resolved"
            label="Resolved"
            value={loading ? '…' : summary?.resolved_incidents ?? 0}
            icon={CheckCircle2}
            accentColor="var(--color-success)"
            sub="Closed & resolved"
          />
          <MetricCard
            id="metric-mttr"
            label="Mean Time to Resolve"
            value={loading ? '…' : formatDuration(summary?.mttr_minutes)}
            icon={TrendingUp}
            sub={summary?.mttr_minutes ? 'Average resolution time' : 'No resolved incidents yet'}
          />
          <MetricCard
            id="metric-sla"
            label="SLA Breaches"
            value={loading ? '…' : summary?.sla_breaches ?? 0}
            icon={AlertTriangle}
            accentColor={summary?.sla_breaches > 0 ? 'var(--color-critical)' : undefined}
            sub="Incidents past SLA"
          />
          <MetricCard
            id="metric-rca"
            label="RCA Completion"
            value={loading ? '…' : summary?.rca_completion_rate != null ? `${summary.rca_completion_rate}%` : '—'}
            icon={BarChart2}
            sub={summary?.rca_completion_rate != null ? 'Analysis completion rate' : 'Insufficient data'}
          />
        </div>

        {/* Charts Row */}
        <div className="charts-row">
          {/* Trend chart */}
          <Card className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Incident Trends</h3>
              <div className="chart-controls">
                {[7, 30, 90].map(d => (
                  <button
                    key={d}
                    className={`chart-period-btn ${trendDays === d ? 'active' : ''}`}
                    onClick={() => setTrendDays(d)}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
            {!trends?.data?.length ? (
              <EmptyState message="No incidents in this period" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={trends.data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="totalGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="critGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#dc2626" stopOpacity={0.12} />
                      <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6, border: '1px solid #e5e7eb' }} />
                  <Area type="monotone" dataKey="total" name="Total" stroke="#4f46e5" fill="url(#totalGrad)" strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="critical" name="Critical" stroke="#dc2626" fill="url(#critGrad)" strokeWidth={1.5} dot={false} />
                  <Area type="monotone" dataKey="resolved" name="Resolved" stroke="#059669" fill="none" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
                  <Legend iconSize={12} wrapperStyle={{ fontSize: 12 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* Severity distribution */}
          <Card className="chart-card chart-card-sm">
            <div className="chart-header">
              <h3 className="chart-title">Severity Distribution</h3>
            </div>
            {!dists?.severity?.length ? (
              <EmptyState message="No incident data" />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={dists.severity}
                    dataKey="count"
                    nameKey="severity"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    innerRadius={45}
                    paddingAngle={3}
                  >
                    {dists.severity.map((entry) => (
                      <Cell key={entry.severity} fill={SEV_COLORS[entry.severity] || '#9ca3af'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
                  <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>

        {/* Bottom row */}
        <div className="dashboard-bottom">
          {/* Recent Incidents */}
          <Card className="recent-card">
            <div className="chart-header">
              <h3 className="chart-title">Recent Incidents</h3>
              <button className="link-btn" onClick={() => navigate('/incidents')}>View all →</button>
            </div>
            {!summary?.recent_incidents?.length ? (
              <EmptyState message="No incidents yet. Create one to get started." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recent_incidents.map(i => (
                    <tr key={i.id} className="data-table-row" onClick={() => navigate(`/incidents/${i.id}`)}>
                      <td className="font-medium" style={{ color: 'var(--color-accent)', fontSize: 12 }}>{i.number}</td>
                      <td className="truncate" style={{ maxWidth: 200 }}>{i.title}</td>
                      <td><SeverityBadge severity={i.severity} /></td>
                      <td><StatusBadge status={i.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>

          {/* Status chart */}
          <Card className="chart-card-sm">
            <div className="chart-header">
              <h3 className="chart-title">By Status</h3>
            </div>
            {!dists?.status?.length ? (
              <EmptyState message="No data" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={dists.status} layout="vertical" margin={{ left: 20, right: 10 }}>
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} />
                  <YAxis type="category" dataKey="status" tick={{ fontSize: 11, fill: '#6b7280' }} tickLine={false} width={110} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 6 }} />
                  <Bar dataKey="count" name="Count" radius={[0, 4, 4, 0]}>
                    {dists.status.map((entry) => (
                      <Cell key={entry.status} fill={STATUS_COLORS[entry.status] || '#9ca3af'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      </div>
    </Layout>
  )
}
