'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin, templates } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Pencil, Trash2, FileCode, Plus, X, ChevronUp, ChevronDown } from 'lucide-react'
import type { NotebookTemplate } from '@/types'

const DIFFICULTY_OPTIONS = ['beginner', 'intermediate', 'advanced'] as const
const DIFFICULTY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  beginner: { bg: 'var(--app-alert-success-bg)', text: 'var(--app-accent-success)', border: 'var(--app-alert-success-border)' },
  intermediate: { bg: 'var(--app-alert-warning-bg)', text: 'var(--app-accent-warning)', border: 'var(--app-alert-warning-border)' },
  advanced: { bg: 'var(--app-alert-error-bg)', text: 'var(--app-accent-error)', border: 'var(--app-alert-error-border)' },
}

interface TemplateFormState {
  name: string
  description: string
  category: string
  difficulty_level: 'beginner' | 'intermediate' | 'advanced'
  tags: string
  is_public: boolean
}

const defaultFormState: TemplateFormState = {
  name: '',
  description: '',
  category: '',
  difficulty_level: 'beginner',
  tags: '',
  is_public: true,
}

export default function TemplatesTab() {
  const user = useAuthStore((state) => state.user)

  const [templateList, setTemplateList] = useState<NotebookTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [creating, setCreating] = useState(false)

  // Create from project form
  const [showCreateFromProject, setShowCreateFromProject] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [fromProjectForm, setFromProjectForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [creatingFromProject, setCreatingFromProject] = useState(false)

  // Edit state
  const [editingTemplate, setEditingTemplate] = useState<NotebookTemplate | null>(null)
  const [editForm, setEditForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [updating, setUpdating] = useState(false)

  // Delete state
  const [deleteConfirm, setDeleteConfirm] = useState<NotebookTemplate | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Notebook content editor state
  interface NotebookCell {
    cell_type: 'code' | 'markdown'
    source: string
    metadata?: Record<string, unknown>
    outputs?: Record<string, unknown>[]
    execution_count?: number | null
  }
  const [contentTemplate, setContentTemplate] = useState<NotebookTemplate | null>(null)
  const [cells, setCells] = useState<NotebookCell[]>([])
  const [loadingContent, setLoadingContent] = useState(false)
  const [savingContent, setSavingContent] = useState(false)

  const fetchTemplates = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await templates.list()
      setTemplateList(data)
    } catch {
      setError('Failed to load templates')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchTemplates()
    }
  }, [user, fetchTemplates])

  const showSuccess = (msg: string) => {
    setSuccessMessage(msg)
    setTimeout(() => setSuccessMessage(''), 4000)
  }

  const parseTags = (tagsStr: string): string[] => {
    return tagsStr
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.name.trim()) return

    try {
      setCreating(true)
      setError('')
      await admin.templates.create({
        name: createForm.name.trim(),
        description: createForm.description.trim() || undefined,
        category: createForm.category.trim() || undefined,
        difficulty_level: createForm.difficulty_level,
        tags: parseTags(createForm.tags).length > 0 ? parseTags(createForm.tags) : undefined,
        is_public: createForm.is_public,
      })
      setShowCreate(false)
      setCreateForm({ ...defaultFormState })
      showSuccess('Template created successfully')
      fetchTemplates()
    } catch {
      setError('Failed to create template')
    } finally {
      setCreating(false)
    }
  }

  const handleCreateFromProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!projectId.trim() || !fromProjectForm.name.trim()) return

    try {
      setCreatingFromProject(true)
      setError('')
      await admin.templates.createFromProject(projectId.trim(), {
        name: fromProjectForm.name.trim(),
        description: fromProjectForm.description.trim() || undefined,
        category: fromProjectForm.category.trim() || undefined,
        difficulty_level: fromProjectForm.difficulty_level,
        tags: parseTags(fromProjectForm.tags).length > 0 ? parseTags(fromProjectForm.tags) : undefined,
        is_public: fromProjectForm.is_public,
      })
      setShowCreateFromProject(false)
      setProjectId('')
      setFromProjectForm({ ...defaultFormState })
      showSuccess('Template created from project successfully')
      fetchTemplates()
    } catch {
      setError('Failed to create template from project. Check the project ID.')
    } finally {
      setCreatingFromProject(false)
    }
  }

  const handleEditClick = (template: NotebookTemplate) => {
    setEditingTemplate(template)
    setEditForm({
      name: template.name,
      description: template.description || '',
      category: template.category || '',
      difficulty_level: template.difficulty_level,
      tags: template.tags?.join(', ') || '',
      is_public: template.is_public,
    })
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingTemplate || !editForm.name.trim()) return

    try {
      setUpdating(true)
      setError('')
      await admin.templates.update(editingTemplate.id, {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
        category: editForm.category.trim() || undefined,
        difficulty_level: editForm.difficulty_level,
        tags: parseTags(editForm.tags).length > 0 ? parseTags(editForm.tags) : undefined,
        is_public: editForm.is_public,
      })
      setEditingTemplate(null)
      showSuccess('Template updated successfully')
      fetchTemplates()
    } catch {
      setError('Failed to update template')
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return

    try {
      setDeleting(true)
      setError('')
      await admin.templates.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      showSuccess('Template deleted successfully')
      fetchTemplates()
    } catch {
      setError('Failed to delete template')
    } finally {
      setDeleting(false)
    }
  }

  const handleEditContent = async (template: NotebookTemplate) => {
    setContentTemplate(template)
    setLoadingContent(true)
    setError('')
    try {
      const notebook = await admin.templates.getNotebook(template.id)
      setCells(
        (notebook.cells || []).map((c) => ({
          cell_type: (c.cell_type === 'markdown' ? 'markdown' : 'code') as 'code' | 'markdown',
          source: c.source || '',
          metadata: c.metadata || {},
          outputs: c.outputs || [],
          execution_count: c.execution_count ?? null,
        }))
      )
    } catch {
      setError('Failed to load notebook content')
      setContentTemplate(null)
    } finally {
      setLoadingContent(false)
    }
  }

  const handleSaveContent = async () => {
    if (!contentTemplate) return
    setSavingContent(true)
    setError('')
    try {
      await admin.templates.updateNotebook(
        contentTemplate.id,
        cells.map((c) => ({
          cell_type: c.cell_type,
          source: c.source,
          metadata: c.metadata || {},
          outputs: c.cell_type === 'code' ? (c.outputs || []) : undefined,
          execution_count: c.cell_type === 'code' ? (c.execution_count ?? null) : undefined,
        }))
      )
      showSuccess('Notebook content saved')
      setContentTemplate(null)
      setCells([])
    } catch {
      setError('Failed to save notebook content')
    } finally {
      setSavingContent(false)
    }
  }

  const addCell = (index: number, type: 'code' | 'markdown') => {
    const newCell: NotebookCell = {
      cell_type: type,
      source: '',
      metadata: {},
      outputs: type === 'code' ? [] : undefined,
      execution_count: null,
    }
    const updated = [...cells]
    updated.splice(index + 1, 0, newCell)
    setCells(updated)
  }

  const removeCell = (index: number) => {
    if (cells.length <= 1) return
    setCells(cells.filter((_, i) => i !== index))
  }

  const updateCellSource = (index: number, source: string) => {
    const updated = [...cells]
    updated[index] = { ...updated[index], source }
    setCells(updated)
  }

  const updateCellType = (index: number, cell_type: 'code' | 'markdown') => {
    const updated = [...cells]
    updated[index] = { ...updated[index], cell_type, outputs: cell_type === 'code' ? [] : undefined }
    setCells(updated)
  }

  const moveCell = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1
    if (newIndex < 0 || newIndex >= cells.length) return
    const updated = [...cells]
    ;[updated[index], updated[newIndex]] = [updated[newIndex], updated[index]]
    setCells(updated)
  }

  // Reusable form fields renderer
  const renderFormFields = (
    form: TemplateFormState,
    setForm: (updater: (prev: TemplateFormState) => TemplateFormState) => void
  ) => (
    <>
      <div>
        <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Name *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          placeholder="Template name"
          required
        />
      </div>
      <div>
        <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Description</label>
        <textarea
          value={form.description}
          onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none resize-y"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          placeholder="Brief description of the template"
          rows={2}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Category</label>
          <input
            type="text"
            value={form.category}
            onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
            placeholder="e.g., Data Science"
          />
        </div>
        <div>
          <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Difficulty</label>
          <select
            value={form.difficulty_level}
            onChange={(e) =>
              setForm((prev) => ({
                ...prev,
                difficulty_level: e.target.value as TemplateFormState['difficulty_level'],
              }))
            }
            className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none cursor-pointer"
            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Tags (comma-separated)</label>
        <input
          type="text"
          value={form.tags}
          onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          placeholder="python, pandas, visualization"
        />
      </div>
      <div className="flex items-center gap-3">
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => setForm((prev) => ({ ...prev, is_public: e.target.checked }))}
            className="sr-only peer"
          />
          <div className="w-9 h-5 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" style={{ backgroundColor: form.is_public ? undefined : 'var(--app-bg-tertiary)' }} />
        </label>
        <span className="text-sm" style={{ color: 'var(--app-text-secondary)' }}>Public</span>
      </div>
    </>
  )

  return (
    <div>
      {/* Action bar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
          Create, edit, and manage notebook templates
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setShowCreateFromProject(true)
              setShowCreate(false)
              setEditingTemplate(null)
            }}
            className="px-4 py-2 rounded-lg text-sm transition-colors"
            style={{
              backgroundColor: 'var(--app-bg-tertiary)',
              color: 'var(--app-text-primary)',
              border: '1px solid var(--app-border-default)',
            }}
          >
            Create from Project
          </button>
          <button
            onClick={() => {
              setShowCreate(true)
              setShowCreateFromProject(false)
              setEditingTemplate(null)
            }}
            className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
            style={{ background: 'var(--app-gradient-primary)' }}
          >
            Create Template
          </button>
        </div>
      </div>

      {/* Success Message */}
      {successMessage && (
        <div className="mb-4 p-3 rounded-lg text-sm flex items-center justify-between" style={{ backgroundColor: 'var(--app-alert-success-bg)', color: 'var(--app-accent-success)', border: '1px solid var(--app-alert-success-border)' }}>
          {successMessage}
          <button onClick={() => setSuccessMessage('')} className="ml-2" style={{ color: 'var(--app-accent-success)' }}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)', border: '1px solid var(--app-alert-error-border)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {/* Create Template Form */}
      {showCreate && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Create Template</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            {renderFormFields(createForm, setCreateForm)}
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50 flex items-center gap-2"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {creating && (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                Create
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreate(false)
                  setCreateForm({ ...defaultFormState })
                }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Create from Project Form */}
      {showCreateFromProject && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Create Template from Project</h3>
          <form onSubmit={handleCreateFromProject} className="space-y-4">
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Project ID *</label>
              <input
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none"
                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                placeholder="e.g., abc123-def456-..."
                required
              />
            </div>
            {renderFormFields(fromProjectForm, setFromProjectForm)}
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={creatingFromProject}
                className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50 flex items-center gap-2"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {creatingFromProject && (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                Create from Project
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateFromProject(false)
                  setProjectId('')
                  setFromProjectForm({ ...defaultFormState })
                }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Edit Template Modal */}
      {editingTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setEditingTemplate(null)}
          />
          <div className="relative w-full max-w-lg rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-lg font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Edit Template</h3>
            <form onSubmit={handleUpdate} className="space-y-4">
              {renderFormFields(editForm, setEditForm)}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingTemplate(null)}
                  className="flex-1 px-4 py-2.5 rounded-xl"
                  style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updating}
                  className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  style={{ background: 'var(--app-gradient-primary)' }}
                >
                  {updating && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => !deleting && setDeleteConfirm(null)}
          />
          <div className="relative w-full max-w-sm rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-alert-error-border)' }}>
            <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>Delete Template</h3>
            <p className="mb-4" style={{ color: 'var(--app-text-muted)' }}>
              Delete &quot;{deleteConfirm.name}&quot;? This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 rounded-xl disabled:opacity-50"
                style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {deleting && (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                )}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notebook Content Editor Modal */}
      {contentTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !savingContent && setContentTemplate(null)} />
          <div
            className="relative w-full max-w-4xl max-h-[90vh] rounded-2xl shadow-2xl flex flex-col"
            style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-5 border-b" style={{ borderColor: 'var(--app-border-default)' }}>
              <div>
                <h3 className="text-lg font-bold" style={{ color: 'var(--app-text-primary)' }}>
                  Edit Notebook Content
                </h3>
                <p className="text-sm mt-0.5" style={{ color: 'var(--app-text-muted)' }}>{contentTemplate.name}</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => addCell(cells.length - 1, 'code')}
                  className="px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5"
                  style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}
                >
                  <Plus size={12} /> Code
                </button>
                <button
                  onClick={() => addCell(cells.length - 1, 'markdown')}
                  className="px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5"
                  style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}
                >
                  <Plus size={12} /> Markdown
                </button>
              </div>
            </div>

            {/* Cells */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {loadingContent ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
                </div>
              ) : cells.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-sm mb-3" style={{ color: 'var(--app-text-muted)' }}>No cells yet</p>
                  <div className="flex gap-2 justify-center">
                    <button onClick={() => addCell(-1, 'code')} className="px-3 py-1.5 rounded-lg text-xs" style={{ background: 'var(--app-gradient-primary)', color: 'white' }}>
                      Add Code Cell
                    </button>
                    <button onClick={() => addCell(-1, 'markdown')} className="px-3 py-1.5 rounded-lg text-xs" style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}>
                      Add Markdown Cell
                    </button>
                  </div>
                </div>
              ) : (
                cells.map((cell, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl overflow-hidden"
                    style={{ border: '1px solid var(--app-border-default)', backgroundColor: 'var(--app-bg-card)' }}
                  >
                    {/* Cell toolbar */}
                    <div className="flex items-center justify-between px-3 py-1.5" style={{ backgroundColor: 'var(--app-bg-tertiary)', borderBottom: '1px solid var(--app-border-default)' }}>
                      <div className="flex items-center gap-2">
                        <select
                          value={cell.cell_type}
                          onChange={(e) => updateCellType(idx, e.target.value as 'code' | 'markdown')}
                          className="text-xs px-2 py-0.5 rounded cursor-pointer focus:outline-none"
                          style={{ backgroundColor: 'var(--app-bg-input)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}
                        >
                          <option value="code">Code</option>
                          <option value="markdown">Markdown</option>
                        </select>
                        <span className="text-[10px]" style={{ color: 'var(--app-text-muted)' }}>
                          Cell {idx + 1} of {cells.length}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => moveCell(idx, 'up')} disabled={idx === 0} className="p-1 rounded disabled:opacity-30" style={{ color: 'var(--app-text-muted)' }} title="Move up">
                          <ChevronUp size={14} />
                        </button>
                        <button onClick={() => moveCell(idx, 'down')} disabled={idx === cells.length - 1} className="p-1 rounded disabled:opacity-30" style={{ color: 'var(--app-text-muted)' }} title="Move down">
                          <ChevronDown size={14} />
                        </button>
                        <button onClick={() => addCell(idx, cell.cell_type)} className="p-1 rounded" style={{ color: 'var(--app-text-muted)' }} title="Add cell below">
                          <Plus size={14} />
                        </button>
                        <button onClick={() => removeCell(idx)} disabled={cells.length <= 1} className="p-1 rounded disabled:opacity-30" style={{ color: 'var(--app-text-muted)' }} title="Delete cell">
                          <X size={14} />
                        </button>
                      </div>
                    </div>
                    {/* Cell content */}
                    <textarea
                      value={cell.source}
                      onChange={(e) => updateCellSource(idx, e.target.value)}
                      className="w-full px-4 py-3 text-sm focus:outline-none resize-y font-mono"
                      style={{
                        backgroundColor: 'var(--app-bg-card)',
                        color: 'var(--app-text-primary)',
                        minHeight: '80px',
                        fontFamily: cell.cell_type === 'code' ? 'monospace' : 'inherit',
                      }}
                      placeholder={cell.cell_type === 'code' ? '# Write Python code here...' : '# Write Markdown here...'}
                      rows={Math.max(3, cell.source.split('\n').length)}
                    />
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between p-5 border-t" style={{ borderColor: 'var(--app-border-default)' }}>
              <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                {cells.length} cell{cells.length !== 1 ? 's' : ''}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => { setContentTemplate(null); setCells([]) }}
                  disabled={savingContent}
                  className="px-4 py-2 rounded-xl text-sm"
                  style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveContent}
                  disabled={savingContent}
                  className="px-4 py-2 rounded-xl text-sm text-white font-medium disabled:opacity-50 flex items-center gap-2"
                  style={{ background: 'var(--app-gradient-primary)' }}
                >
                  {savingContent && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Save Content
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Templates Table */}
      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
        {isLoading ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
        ) : templateList.length === 0 ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>
            No templates yet. Create one above.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Name</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Category</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Difficulty</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Tags</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Visibility</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Created</th>
                <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {templateList.map((template) => {
                const diffStyle =
                  DIFFICULTY_COLORS[template.difficulty_level] || DIFFICULTY_COLORS.beginner

                return (
                  <tr key={template.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium" style={{ color: 'var(--app-text-primary)' }}>{template.name}</p>
                        {template.description && (
                          <p className="text-xs truncate max-w-xs" style={{ color: 'var(--app-text-muted)' }}>
                            {template.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3" style={{ color: 'var(--app-text-secondary)' }}>
                      {template.category || '-'}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: diffStyle.bg,
                          color: diffStyle.text,
                          border: `1px solid ${diffStyle.border}`,
                        }}
                      >
                        {template.difficulty_level}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {template.tags && template.tags.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {template.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="px-1.5 py-0.5 rounded text-xs"
                              style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-muted)' }}
                            >
                              {tag}
                            </span>
                          ))}
                          {template.tags.length > 3 && (
                            <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                              +{template.tags.length - 3}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--app-text-muted)' }}>-</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: template.is_public ? 'var(--app-alert-success-bg)' : 'var(--app-bg-tertiary)',
                          color: template.is_public ? '#10b981' : 'var(--app-text-muted)',
                        }}
                      >
                        {template.is_public ? 'Public' : 'Private'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      {new Date(template.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => handleEditContent(template)}
                          className="p-1.5 rounded-md transition-colors hover-text-primary"
                          style={{ color: 'var(--app-text-muted)' }}
                          title="Edit notebook content"
                        >
                          <FileCode size={14} />
                        </button>
                        <button
                          onClick={() => handleEditClick(template)}
                          className="p-1.5 rounded-md transition-colors hover-text-primary"
                          style={{ color: 'var(--app-text-muted)' }}
                          title="Edit metadata"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(template)}
                          className="p-1.5 rounded-md transition-colors hover-text-error"
                          style={{ color: 'var(--app-text-muted)' }}
                          title="Delete template"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
