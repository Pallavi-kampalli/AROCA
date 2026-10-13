import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider } from './contexts/ToastContext'
import { Login } from './pages/Login/Login'
import { Dashboard } from './pages/Dashboard/Dashboard'
import { Incidents } from './pages/Incidents/Incidents'
import { IncidentDetail } from './pages/IncidentDetail/IncidentDetail'
import { LogExplorer } from './pages/LogExplorer/LogExplorer'
import { Copilot } from './pages/Copilot/Copilot'
import { Remediation } from './pages/Remediation/Remediation'
import { Knowledge } from './pages/Knowledge/Knowledge'
import { Models } from './pages/Models/Models'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return children
}

function PublicRoute({ children }) {
  const { user } = useAuth()
  if (user) return <Navigate to="/" replace />
  return children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />

      <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/incidents" element={<PrivateRoute><Incidents /></PrivateRoute>} />
      <Route path="/incidents/:id" element={<PrivateRoute><IncidentDetail /></PrivateRoute>} />
      <Route path="/logs" element={<PrivateRoute><LogExplorer /></PrivateRoute>} />
      <Route path="/copilot" element={<PrivateRoute><Copilot /></PrivateRoute>} />
      <Route path="/remediation" element={<PrivateRoute><Remediation /></PrivateRoute>} />
      <Route path="/knowledge" element={<PrivateRoute><Knowledge /></PrivateRoute>} />
      <Route path="/models" element={<PrivateRoute><Models /></PrivateRoute>} />
      <Route path="/audit" element={<PrivateRoute><Models /></PrivateRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
