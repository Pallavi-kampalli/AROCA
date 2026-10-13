import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, AlertTriangle, FileText, Brain, MessageSquare,
  Wrench, BookOpen, BarChart2, ClipboardList, LogOut, Activity, ShieldCheck
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import './Layout.css'

const navItems = [
  { label: 'Command Center', icon: LayoutDashboard, path: '/' },
  { label: 'Incidents', icon: AlertTriangle, path: '/incidents' },
  { label: 'Log Explorer', icon: FileText, path: '/logs' },
  { label: 'AI Copilot', icon: MessageSquare, path: '/copilot' },
  { label: 'Remediation', icon: Wrench, path: '/remediation' },
  { label: 'Knowledge Base', icon: BookOpen, path: '/knowledge' },
  { label: 'ML & Models', icon: Brain, path: '/models' },
  { label: 'Audit Log', icon: ClipboardList, path: '/audit' },
]

export function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.username?.slice(0, 2).toUpperCase() || 'TQ'

  return (
    <aside className="sidebar" role="navigation" aria-label="Main navigation">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Activity size={16} color="white" />
        </div>
        <div className="sidebar-logo-text">Trace<span>IQ</span></div>
      </div>

      <nav className="sidebar-nav">
        <span className="sidebar-section-label">Navigation</span>
        {navItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
          >
            <item.icon className="icon" size={16} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <div className="header-avatar">{initials}</div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-gray-800)' }}>{user?.full_name || user?.username}</div>
            <div style={{ fontSize: 11, color: 'var(--color-gray-400)' }}>{user?.roles?.[0] || 'user'}</div>
          </div>
        </div>
        <button className="sidebar-link" onClick={handleLogout} id="btn-logout">
          <LogOut className="icon" size={16} />
          Sign out
        </button>
        <div className="sidebar-version">TraceIQ v1.0.0</div>
      </div>
    </aside>
  )
}

export function Header({ title }) {
  return (
    <header className="header">
      <div className="header-left">
        <ShieldCheck size={18} color="var(--color-accent)" />
        <span className="header-page-title">{title}</span>
      </div>
    </header>
  )
}

export function Layout({ title, children }) {
  return (
    <div className="layout">
      <Sidebar />
      <div className="layout-main">
        <Header title={title} />
        <main className="layout-content">
          {children}
        </main>
      </div>
    </div>
  )
}
