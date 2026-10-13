import './Card.css'

export function Card({ children, className = '', padding = true }) {
  return (
    <div className={`card ${padding ? 'card-padded' : ''} ${className}`}>
      {children}
    </div>
  )
}

export function MetricCard({ label, value, sub, icon: Icon, accentColor, onClick, id }) {
  return (
    <div className={`metric-card ${onClick ? 'metric-card-clickable' : ''}`} onClick={onClick} id={id}>
      <div className="metric-card-header">
        <span className="metric-card-label">{label}</span>
        {Icon && (
          <div className="metric-card-icon" style={{ color: accentColor || 'var(--color-accent)' }}>
            <Icon size={16} />
          </div>
        )}
      </div>
      <div className="metric-card-value" style={{ color: accentColor }}>
        {value ?? <span className="text-muted">—</span>}
      </div>
      {sub && <div className="metric-card-sub">{sub}</div>}
    </div>
  )
}
