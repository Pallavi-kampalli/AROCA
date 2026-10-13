import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { Button } from '../../components/Button/Button'
import './Login.css'

export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showSetup, setShowSetup] = useState(false)

  // Setup form
  const [setup, setSetup] = useState({ username: '', password: '', email: '', full_name: '' })
  const [setupLoading, setSetupLoading] = useState(false)

  const { login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!username || !password) { toast.error('Enter username and password'); return }
    setLoading(true)
    try {
      await login(username, password)
      toast.success('Signed in successfully')
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Invalid credentials'
      if (err.response?.status === 404 || msg.includes('not found') || msg.includes('No users')) {
        setShowSetup(true)
      }
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleSetup = async (e) => {
    e.preventDefault()
    setSetupLoading(true)
    try {
      const { authAPI } = await import('../../api/client')
      await authAPI.register(setup)
      toast.success('Admin account created! You can now log in.')
      setShowSetup(false)
      setUsername(setup.username)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Setup failed')
    } finally {
      setSetupLoading(false)
    }
  }

  if (showSetup) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-brand">
            <div className="login-logo"><Activity size={22} color="white" /></div>
            <span className="login-brand-name">TraceIQ</span>
          </div>
          <h1 className="login-title">Initial Setup</h1>
          <p className="login-subtitle">Create the first administrator account.</p>
          <form onSubmit={handleSetup} className="login-form">
            <div className="login-field">
              <label className="form-label" htmlFor="setup-fullname">Full Name</label>
              <input id="setup-fullname" className="form-input" value={setup.full_name}
                onChange={e => setSetup(s => ({ ...s, full_name: e.target.value }))} required />
            </div>
            <div className="login-field">
              <label className="form-label" htmlFor="setup-email">Email</label>
              <input id="setup-email" type="email" className="form-input" value={setup.email}
                onChange={e => setSetup(s => ({ ...s, email: e.target.value }))} required />
            </div>
            <div className="login-field">
              <label className="form-label" htmlFor="setup-username">Username</label>
              <input id="setup-username" className="form-input" value={setup.username}
                onChange={e => setSetup(s => ({ ...s, username: e.target.value }))} required />
            </div>
            <div className="login-field">
              <label className="form-label" htmlFor="setup-password">Password (min 8 chars)</label>
              <input id="setup-password" type="password" className="form-input" value={setup.password}
                onChange={e => setSetup(s => ({ ...s, password: e.target.value }))} required minLength={8} />
            </div>
            <Button type="submit" loading={setupLoading} id="btn-setup-submit">
              Create Admin Account
            </Button>
            <button type="button" className="login-back" onClick={() => setShowSetup(false)}>
              Back to login
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="login-logo"><Activity size={22} color="white" /></div>
          <span className="login-brand-name">TraceIQ</span>
        </div>
        <h1 className="login-title">Sign in to TraceIQ</h1>
        <p className="login-subtitle">AI Root Cause Analysis &amp; Intelligent Ticket Resolution</p>

        <form onSubmit={handleLogin} className="login-form">
          <div className="login-field">
            <label className="form-label" htmlFor="login-username">Username</label>
            <input
              id="login-username"
              className="form-input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
              required
            />
          </div>
          <div className="login-field">
            <label className="form-label" htmlFor="login-password">Password</label>
            <div className="login-password-field">
              <input
                id="login-password"
                type={showPass ? 'text' : 'password'}
                className="form-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
              <button type="button" className="login-toggle-pass" onClick={() => setShowPass(v => !v)} aria-label="Toggle password visibility">
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <Button type="submit" loading={loading} id="btn-login" className="login-submit-btn">
            Sign in
          </Button>
        </form>

        <div className="login-setup-hint">
          <button className="login-setup-link" onClick={() => setShowSetup(true)}>
            First time? Create admin account
          </button>
        </div>
      </div>

      <div className="login-features">
        {[
          { label: 'AI Root Cause Analysis', sub: 'ML + LLM evidence-backed findings' },
          { label: 'Log Intelligence', sub: 'Parse and analyze any log format' },
          { label: 'Safe Remediation', sub: 'Approval gating for high-risk actions' },
          { label: 'Full Audit Trail', sub: 'Immutable event history' },
        ].map(f => (
          <div key={f.label} className="login-feature">
            <div className="login-feature-dot" />
            <div>
              <div className="login-feature-label">{f.label}</div>
              <div className="login-feature-sub">{f.sub}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
