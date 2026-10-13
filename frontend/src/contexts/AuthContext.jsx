import { createContext, useContext, useState, useCallback } from 'react'
import { authAPI } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('traceiq_user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })

  const login = useCallback(async (username, password) => {
    const res = await authAPI.login(username, password)
    const data = res.data
    localStorage.setItem('traceiq_token', data.access_token)
    localStorage.setItem('traceiq_user', JSON.stringify(data))
    setUser(data)
    return data
  }, [])

  const logout = useCallback(async () => {
    try { await authAPI.logout() } catch {}
    localStorage.removeItem('traceiq_token')
    localStorage.removeItem('traceiq_user')
    setUser(null)
  }, [])

  const isAdmin = user?.roles?.includes('admin')
  const hasRole = (role) => user?.roles?.includes(role)

  return (
    <AuthContext.Provider value={{ user, login, logout, isAdmin, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
