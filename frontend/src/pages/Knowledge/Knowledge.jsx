import { useState, useEffect } from 'react'
import { Search, Plus, BookOpen, CheckCircle, ExternalLink } from 'lucide-react'
import { Layout } from '../../components/Layout/Layout'
import { Card } from '../../components/Card/Card'
import { Button } from '../../components/Button/Button'
import { Modal } from '../../components/Modal/Modal'
import { knowledgeAPI } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'
import './Knowledge.css'

function DocModal({ doc, onClose }) {
  if (!doc) return null
  return (
    <Modal isOpen={!!doc} onClose={onClose} title={doc.title} size="lg">
      <div className="doc-view">
        {doc.tags?.length > 0 && (
          <div className="doc-tags">
            {doc.tags.map(t => <span key={t} className="doc-tag">{t}</span>)}
          </div>
        )}
        <div className="doc-meta">
          {doc.source_incident_id && (
            <span>Source incident: <strong>{doc.source_incident_id}</strong></span>
          )}
          {doc.is_verified && <span className="doc-verified"><CheckCircle size={12} /> Verified</span>}
          {doc.created_at && (
            <span>{new Date(doc.created_at).toLocaleDateString('en-GB', { dateStyle: 'medium' })}</span>
          )}
        </div>
        <div className="doc-content">{doc.content}</div>
      </div>
    </Modal>
  )
}

export function Knowledge() {
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [viewDoc, setViewDoc] = useState(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ title: '', content: '', tags: '' })
  const toast = useToast()

  const load = async (q = query) => {
    setLoading(true)
    try {
      const res = await knowledgeAPI.search(q)
      setDocs(res.data.items)
      setTotal(res.data.total)
    } catch {
      toast.error('Failed to load knowledge base')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    load(query)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!form.title.trim() || !form.content.trim()) {
      toast.error('Title and content are required')
      return
    }
    setCreating(true)
    try {
      const tags = form.tags.split(',').map(t => t.trim()).filter(Boolean)
      await knowledgeAPI.create({ title: form.title, content: form.content, tags })
      toast.success('Document created')
      setCreateOpen(false)
      setForm({ title: '', content: '', tags: '' })
      load()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create document')
    } finally {
      setCreating(false)
    }
  }

  const handleViewDoc = async (id) => {
    try {
      const res = await knowledgeAPI.get(id)
      setViewDoc(res.data)
    } catch {
      toast.error('Failed to load document')
    }
  }

  return (
    <Layout title="Knowledge Base">
      <div className="knowledge-page fade-in">
        <div className="page-header">
          <div>
            <h2 className="page-title">Knowledge Base</h2>
            <p className="page-sub">{total} documents — search and manage incident runbooks</p>
          </div>
          <Button onClick={() => setCreateOpen(true)} id="btn-create-doc">
            <Plus size={14} /> New Document
          </Button>
        </div>

        {/* Search */}
        <Card className="kb-search-card">
          <form onSubmit={handleSearch} className="kb-search-form">
            <div className="search-field" style={{ flex: 1 }}>
              <Search size={14} className="search-icon" />
              <input
                id="kb-search"
                className="form-input search-input"
                placeholder="Search knowledge base…"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            <Button type="submit" id="btn-kb-search">Search</Button>
            {query && (
              <Button variant="secondary" type="button" onClick={() => { setQuery(''); load('') }}>
                Clear
              </Button>
            )}
          </form>
        </Card>

        {/* Documents */}
        {loading ? (
          <div className="loading-state"><div className="loading-spinner" /> Loading…</div>
        ) : docs.length === 0 ? (
          <Card className="kb-empty">
            <BookOpen size={40} color="var(--color-gray-300)" />
            <h3>{query ? `No results for "${query}"` : 'Knowledge base is empty'}</h3>
            <p className="text-muted">
              {query ? 'Try different search terms.' : 'Create your first document to start building institutional knowledge.'}
            </p>
            {!query && (
              <Button size="sm" onClick={() => setCreateOpen(true)} id="btn-create-first-doc">
                <Plus size={14} /> Create Document
              </Button>
            )}
          </Card>
        ) : (
          <div className="docs-grid">
            {docs.map(doc => (
              <Card key={doc.id} className="doc-card" onClick={() => handleViewDoc(doc.id)}>
                <div className="doc-card-header">
                  <BookOpen size={14} color="var(--color-accent)" />
                  {doc.is_verified && <CheckCircle size={13} color="var(--color-success)" title="Verified" />}
                  <ExternalLink size={13} color="var(--color-gray-400)" style={{ marginLeft: 'auto' }} />
                </div>
                <h3 className="doc-card-title">{doc.title}</h3>
                <p className="doc-card-preview">{doc.content_preview}</p>
                {doc.tags?.length > 0 && (
                  <div className="doc-card-tags">
                    {doc.tags.slice(0, 3).map(t => <span key={t} className="doc-tag">{t}</span>)}
                    {doc.tags.length > 3 && <span className="doc-tag">+{doc.tags.length - 3}</span>}
                  </div>
                )}
                <div className="doc-card-footer">
                  {doc.source_incident_id && (
                    <span className="doc-source">Incident</span>
                  )}
                  <span className="doc-date">
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-GB', { dateStyle: 'short' }) : ''}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create modal */}
      <Modal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New Knowledge Document"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} loading={creating} id="btn-submit-doc">Create Document</Button>
          </>
        }
      >
        <form className="create-form" onSubmit={handleCreate}>
          <div className="form-group full">
            <label className="form-label" htmlFor="doc-title">Title *</label>
            <input id="doc-title" className="form-input" value={form.title}
              onChange={e => setForm(f => ({ ...f, title: e.target.value }))} required />
          </div>
          <div className="form-group full">
            <label className="form-label" htmlFor="doc-content">Content *</label>
            <textarea id="doc-content" className="form-textarea" value={form.content}
              onChange={e => setForm(f => ({ ...f, content: e.target.value }))} required rows={10}
              placeholder="Document content — runbook, post-mortem, known issue notes…" />
          </div>
          <div className="form-group full">
            <label className="form-label" htmlFor="doc-tags">Tags (comma-separated)</label>
            <input id="doc-tags" className="form-input" value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
              placeholder="e.g. database, outage, runbook" />
          </div>
        </form>
      </Modal>

      {/* View doc modal */}
      <DocModal doc={viewDoc} onClose={() => setViewDoc(null)} />
    </Layout>
  )
}
