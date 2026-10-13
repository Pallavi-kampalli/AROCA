import { useState, useEffect, useRef } from 'react'
import { Send, Bot, User, Loader, AlertCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { Button } from '../../components/Button/Button'
import { copilotAPI, incidentsAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Copilot.css'

function Message({ msg }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`message ${isUser ? 'message-user' : 'message-assistant'}`}>
      <div className="message-avatar">
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>
      <div className="message-bubble">
        <div className="message-content">{msg.content}</div>
        {msg.created_at && (
          <div className="message-ts">
            {new Date(msg.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </div>
  )
}

export function Copilot() {
  const [searchParams] = useSearchParams()
  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(searchParams.get('incident') || '')
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const bottomRef = useRef(null)
  const toast = useToast()

  useEffect(() => {
    incidentsAPI.list({ page_size: 50 }).then(res => {
      setIncidents(res.data.items.filter(i => !['RESOLVED', 'CLOSED'].includes(i.status)))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!selectedId) { setHistory([]); return }
    setLoadingHistory(true)
    copilotAPI.history(selectedId)
      .then(res => setHistory(res.data))
      .catch(() => {})
      .finally(() => setLoadingHistory(false))
  }, [selectedId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || !selectedId) return
    const text = input.trim()
    setInput('')

    const tempMsg = { id: 'temp', role: 'user', content: text, created_at: new Date().toISOString() }
    const thinkingMsg = { id: 'thinking', role: 'assistant', content: '…', created_at: null, loading: true }
    setHistory(h => [...h, tempMsg, thinkingMsg])
    setSending(true)

    try {
      const res = await copilotAPI.sendMessage(selectedId, text)
      setHistory(h => {
        const withoutThinking = h.filter(m => m.id !== 'thinking')
        return [...withoutThinking, {
          id: res.data.message_id,
          role: 'assistant',
          content: res.data.reply,
          created_at: new Date().toISOString(),
          error: res.data.error,
        }]
      })
    } catch (err) {
      setHistory(h => h.filter(m => m.id !== 'thinking' && m.id !== 'temp'))
      toast.error('Failed to send message')
    } finally {
      setSending(false)
    }
  }

  const selectedIncident = incidents.find(i => i.id === selectedId)

  return (
    <Layout title="AI Copilot">
      <div className="copilot-page fade-in">
        <div className="copilot-layout">
          {/* Incident selector */}
          <div className="copilot-sidebar">
            <Card>
              <h3 className="card-section-title">Select Incident</h3>
              <p className="text-sm text-muted" style={{ marginBottom: 12 }}>
                Copilot has context of logs and analysis for the selected incident.
              </p>
              {incidents.length === 0 ? (
                <p className="text-sm text-muted">No open incidents.</p>
              ) : (
                <div className="incident-selector-list">
                  {incidents.map(inc => (
                    <button
                      key={inc.id}
                      className={`inc-selector-btn ${selectedId === inc.id ? 'active' : ''}`}
                      onClick={() => setSelectedId(inc.id)}
                    >
                      <span className="inc-selector-num">{inc.number}</span>
                      <span className="inc-selector-title">{inc.title}</span>
                      <span className={`sev-dot sev-${inc.severity?.toLowerCase()}`} />
                    </button>
                  ))}
                </div>
              )}
            </Card>

            {selectedIncident && (
              <Card style={{ marginTop: 12 }}>
                <h3 className="card-section-title">Context</h3>
                <div className="copilot-context-info">
                  <div><strong>{selectedIncident.number}</strong></div>
                  <div className="text-sm">{selectedIncident.title}</div>
                  <div className="text-sm text-muted">Status: {selectedIncident.status}</div>
                  <div className="text-sm text-muted">Severity: {selectedIncident.severity}</div>
                </div>
              </Card>
            )}
          </div>

          {/* Chat area */}
          <div className="copilot-chat">
            {!selectedId ? (
              <Card className="copilot-empty">
                <Bot size={40} color="var(--color-gray-300)" />
                <h3>TraceIQ AI Copilot</h3>
                <p>Select an incident from the left to start an AI-assisted investigation.</p>
                <p className="text-sm text-muted">
                  The copilot has access to incident details, uploaded logs, and any RCA analysis results.
                </p>
              </Card>
            ) : (
              <Card className="chat-card">
                <div className="chat-header">
                  <Bot size={16} color="var(--color-accent)" />
                  <span className="chat-title">AI Copilot — {selectedIncident?.number || selectedId}</span>
                  <span className="chat-model-tag">Ollama / LLM</span>
                </div>

                <div className="chat-messages">
                  {loadingHistory ? (
                    <div className="chat-loading"><Loader size={16} className="spin" /> Loading history…</div>
                  ) : history.length === 0 ? (
                    <div className="chat-intro">
                      <Bot size={24} color="var(--color-gray-300)" />
                      <p>Start by asking about the incident. Try:</p>
                      <div className="chat-suggestions">
                        {[
                          'What are the most likely root causes?',
                          'Summarize the errors in the logs.',
                          'What remediation do you recommend?',
                          'Are there any unusual patterns in the logs?',
                        ].map(s => (
                          <button key={s} className="suggestion-btn" onClick={() => setInput(s)}>
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    history.map(msg => (
                      msg.loading ? (
                        <div key="thinking" className="message message-assistant">
                          <div className="message-avatar"><Bot size={14} /></div>
                          <div className="message-bubble thinking">
                            <span /><span /><span />
                          </div>
                        </div>
                      ) : (
                        <Message key={msg.id} msg={msg} />
                      )
                    ))
                  )}
                  <div ref={bottomRef} />
                </div>

                <form className="chat-input-form" onSubmit={handleSend}>
                  <textarea
                    id="copilot-input"
                    className="chat-textarea"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(e) }}}
                    placeholder="Ask about the incident… (Enter to send, Shift+Enter for newline)"
                    rows={2}
                    disabled={sending}
                  />
                  <Button type="submit" disabled={!input.trim() || sending} id="btn-send-chat">
                    {sending ? <Loader size={14} className="spin" /> : <Send size={14} />}
                  </Button>
                </form>

                <div className="chat-disclaimer">
                  <AlertCircle size={12} />
                  <span>AI analysis is based solely on provided evidence. Always verify before taking action.</span>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
