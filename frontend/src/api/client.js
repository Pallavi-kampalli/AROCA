import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('traceiq_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401s
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('traceiq_token')
      localStorage.removeItem('traceiq_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ─── Auth ────────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  register: (data) => api.post('/auth/register', data),
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const dashboardAPI = {
  summary: () => api.get('/dashboard/summary'),
  trends: (days = 30) => api.get(`/dashboard/trends?days=${days}`),
  distributions: () => api.get('/dashboard/distributions'),
}

// ─── Incidents ───────────────────────────────────────────────────────────────
export const incidentsAPI = {
  list: (params) => api.get('/incidents', { params }),
  create: (data) => api.post('/incidents', data),
  get: (id) => api.get(`/incidents/${id}`),
  update: (id, data) => api.patch(`/incidents/${id}`, data),
  addComment: (id, data) => api.post(`/incidents/${id}/comments`, data),
  addRelationship: (id, data) => api.post(`/incidents/${id}/relationships`, data),
  resolve: (id, data) => api.post(`/incidents/${id}/resolve`, data),
  reopen: (id) => api.post(`/incidents/${id}/reopen`),
}

// ─── Logs ─────────────────────────────────────────────────────────────────────
export const logsAPI = {
  upload: (incidentId, file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/incidents/${incidentId}/logs`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (incidentId, params) => api.get(`/incidents/${incidentId}/logs`, { params }),
  get: (logEventId) => api.get(`/logs/${logEventId}`),
}

// ─── Analysis ─────────────────────────────────────────────────────────────────
export const analysisAPI = {
  trigger: (incidentId) => api.post(`/incidents/${incidentId}/analyze`),
  list: (incidentId) => api.get(`/incidents/${incidentId}/analyses`),
  get: (analysisId) => api.get(`/analyses/${analysisId}`),
}

// ─── Copilot ──────────────────────────────────────────────────────────────────
export const copilotAPI = {
  sendMessage: (incidentId, message) =>
    api.post(`/incidents/${incidentId}/copilot/messages`, { message }),
  history: (incidentId) => api.get(`/incidents/${incidentId}/copilot/history`),
}

// ─── Remediation ──────────────────────────────────────────────────────────────
export const remediationAPI = {
  registry: () => api.get('/remediation/registry'),
  propose: (analysisId, data) => api.post(`/analyses/${analysisId}/remediation-proposals`, data),
  requestApproval: (actionId, data) => api.post(`/remediation/${actionId}/request-approval`, data),
  approve: (approvalId, data) => api.post(`/approvals/${approvalId}/approve`, data),
  reject: (approvalId, data) => api.post(`/approvals/${approvalId}/reject`, data),
  execute: (actionId, data) => api.post(`/remediation/${actionId}/execute`, data),
  status: (executionId) => api.get(`/remediation/${executionId}/status`),
}

// ─── Knowledge ───────────────────────────────────────────────────────────────
export const knowledgeAPI = {
  search: (q, page = 1) => api.get('/knowledge/search', { params: { q, page } }),
  create: (data) => api.post('/knowledge/documents', data),
  get: (id) => api.get(`/knowledge/documents/${id}`),
}

// ─── Models & Audit ──────────────────────────────────────────────────────────
export const modelsAPI = {
  status: () => api.get('/models/status'),
  train: () => api.post('/models/train'),
  trainingRuns: () => api.get('/models/training-runs'),
}

export const auditAPI = {
  list: (page = 1, action = '') => api.get('/audit/events', { params: { page, action } }),
}
