import './Badge.css'

const SEVERITY_MAP = {
  CRITICAL: 'critical',
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
  INFO: 'info',
}

const STATUS_MAP = {
  NEW: 'new',
  TRIAGED: 'triaged',
  INVESTIGATING: 'investigating',
  AWAITING_APPROVAL: 'pending',
  IN_PROGRESS: 'in-progress',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
  REOPENED: 'reopened',
  COMPLETED: 'resolved',
  FAILED: 'critical',
  RUNNING: 'in-progress',
  PENDING: 'new',
  INSUFFICIENT_DATA: 'triaged',
}

export function Badge({ children, variant = 'default', className = '' }) {
  return (
    <span className={`badge badge-${variant} ${className}`}>
      {children}
    </span>
  )
}

export function SeverityBadge({ severity }) {
  const variant = SEVERITY_MAP[severity?.toUpperCase()] || 'default'
  return <Badge variant={variant}>{severity}</Badge>
}

export function StatusBadge({ status }) {
  const variant = STATUS_MAP[status?.toUpperCase()] || 'default'
  const label = status?.replace('_', ' ')
  return <Badge variant={variant}>{label}</Badge>
}
