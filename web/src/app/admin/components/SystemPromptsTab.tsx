'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin } from '@/lib/api'
import { Pencil, Trash2 } from 'lucide-react'
import type { SystemPrompt } from '@/types'

const PROMPT_TYPES = [
  { key: 'chat_panel', label: 'Chat Panel' },
  { key: 'ai_cell', label: 'AI Cell' },
] as const

type PromptTypeKey = typeof PROMPT_TYPES[number]['key']

export default function SystemPromptsTab() {
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    prompt_type: 'chat_panel' as PromptTypeKey,
    label: '',
    content: '',
  })
  const [isCreating, setIsCreating] = useState(false)

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ label: '', content: '' })
  const [isSaving, setIsSaving] = useState(false)

  // Action loading
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

  const fetchPrompts = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await admin.systemPrompts.list()
      setPrompts(data)
    } catch {
      setError('Failed to load system prompts')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPrompts()
  }, [fetchPrompts])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      setIsCreating(true)
      await admin.systemPrompts.create(createForm)
      setCreateForm({ prompt_type: 'chat_panel', label: '', content: '' })
      setShowCreate(false)
      setSuccessMsg('Prompt created')
      fetchPrompts()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create prompt'
      setError(errorMsg)
    } finally {
      setIsCreating(false)
    }
  }

  const startEditing = (prompt: SystemPrompt) => {
    setEditingId(prompt.id)
    setEditForm({ label: prompt.label, content: prompt.content })
  }

  const cancelEditing = () => {
    setEditingId(null)
    setEditForm({ label: '', content: '' })
  }

  const handleSave = async (id: string) => {
    try {
      setIsSaving(true)
      await admin.systemPrompts.update(id, editForm)
      setEditingId(null)
      setSuccessMsg('Prompt updated')
      fetchPrompts()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update prompt'
      setError(errorMsg)
    } finally {
      setIsSaving(false)
    }
  }

  const handleActivate = async (id: string) => {
    try {
      setActionLoadingId(id)
      await admin.systemPrompts.activate(id)
      setSuccessMsg('Prompt activated')
      fetchPrompts()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to activate prompt'
      setError(errorMsg)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDeactivate = async (id: string) => {
    try {
      setActionLoadingId(id)
      await admin.systemPrompts.deactivate(id)
      setSuccessMsg('Prompt deactivated — hardcoded default will be used')
      fetchPrompts()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to deactivate prompt'
      setError(errorMsg)
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDelete = async (id: string, label: string) => {
    if (!confirm(`Delete prompt "${label}"? This cannot be undone.`)) return
    try {
      setActionLoadingId(id)
      await admin.systemPrompts.delete(id)
      setSuccessMsg('Prompt deleted')
      if (editingId === id) cancelEditing()
      fetchPrompts()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete prompt'
      setError(errorMsg)
    } finally {
      setActionLoadingId(null)
    }
  }

  const getPromptsForType = (type: PromptTypeKey) => prompts.filter(p => p.prompt_type === type)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  return (
    <div>
      {/* Action bar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
          Manage system prompts for Chat Panel and AI Cell. One active prompt per type — falls back to hardcoded default if none active.
        </p>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
          style={{ background: 'var(--app-gradient-primary)' }}
        >
          {showCreate ? 'Cancel' : 'Add Prompt'}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--app-accent-success)' }}>
          {successMsg}
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h2 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>
            Add System Prompt
          </h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Type</label>
                <select
                  value={createForm.prompt_type}
                  onChange={(e) => setCreateForm({ ...createForm, prompt_type: e.target.value as PromptTypeKey })}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                >
                  {PROMPT_TYPES.map(t => (
                    <option key={t.key} value={t.key}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Label</label>
                <input
                  type="text"
                  value={createForm.label}
                  onChange={(e) => setCreateForm({ ...createForm, label: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., Custom Chat Prompt v2"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Content</label>
              <textarea
                value={createForm.content}
                onChange={(e) => setCreateForm({ ...createForm, content: e.target.value })}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none font-mono"
                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)', resize: 'vertical' }}
                rows={12}
                placeholder="Enter system prompt content..."
                required
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 rounded-lg text-sm transition-colors"
                style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isCreating}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isCreating ? 'Creating...' : 'Create Prompt'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Prompt sections by type */}
      {PROMPT_TYPES.map(type => {
        const typePrompts = getPromptsForType(type.key)
        const activePrompt = typePrompts.find(p => p.is_active)

        return (
          <div key={type.key} className="mb-8">
            <div className="flex items-center gap-3 mb-3">
              <h2 className="text-base font-semibold" style={{ color: 'var(--app-text-primary)' }}>
                {type.label}
              </h2>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{
                backgroundColor: activePrompt ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: activePrompt ? 'var(--app-accent-success)' : 'var(--app-accent-warning)',
              }}>
                {activePrompt ? `Active: ${activePrompt.label}` : 'Using default'}
              </span>
            </div>

            {typePrompts.length === 0 ? (
              <div className="py-6 text-center text-sm rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
                No custom prompts. The hardcoded default is in use.
              </div>
            ) : (
              <div className="space-y-3">
                {typePrompts.map(prompt => (
                  <div
                    key={prompt.id}
                    className="rounded-xl overflow-hidden"
                    style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}
                  >
                    {/* Prompt header row */}
                    <div className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                          {prompt.label}
                        </span>
                        {prompt.is_active && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full font-medium" style={{
                            backgroundColor: 'rgba(16, 185, 129, 0.15)',
                            color: 'var(--app-accent-success)',
                          }}>
                            Active
                          </span>
                        )}
                        <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                          Updated {new Date(prompt.updated_at).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {editingId !== prompt.id && (
                          <button
                            onClick={() => startEditing(prompt)}
                            className="p-1.5 rounded-md transition-colors"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Edit prompt"
                            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--app-text-primary)')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--app-text-muted)')}
                          >
                            <Pencil size={14} />
                          </button>
                        )}
                        {/* Active toggle slider */}
                        <button
                          onClick={() => prompt.is_active ? handleDeactivate(prompt.id) : handleActivate(prompt.id)}
                          disabled={actionLoadingId === prompt.id}
                          className="flex items-center gap-2 text-xs disabled:opacity-50"
                          title={prompt.is_active ? 'Active — click to deactivate' : 'Inactive — click to activate'}
                        >
                          <span style={{ color: 'var(--app-text-muted)' }}>Active</span>
                          <div
                            className="relative w-8 h-4 rounded-full transition-colors cursor-pointer"
                            style={{
                              backgroundColor: prompt.is_active
                                ? 'var(--app-accent-success)' : 'var(--app-bg-tertiary)',
                              border: '1px solid var(--app-border-default)',
                            }}
                          >
                            <div
                              className="absolute top-0.5 w-2.5 h-2.5 rounded-full transition-all"
                              style={{
                                backgroundColor: prompt.is_active
                                  ? '#fff' : 'var(--app-text-muted)',
                                left: prompt.is_active ? '14px' : '2px',
                              }}
                            />
                          </div>
                        </button>
                        <button
                          onClick={() => handleDelete(prompt.id, prompt.label)}
                          disabled={actionLoadingId === prompt.id}
                          className="p-1.5 rounded-md transition-colors disabled:opacity-50"
                          style={{ color: 'var(--app-text-muted)' }}
                          title="Delete prompt"
                          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--app-accent-error)')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--app-text-muted)')}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {/* Edit mode */}
                    {editingId === prompt.id ? (
                      <div className="px-4 pb-4 space-y-3" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                        <div className="pt-3">
                          <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Label</label>
                          <input
                            type="text"
                            value={editForm.label}
                            onChange={(e) => setEditForm({ ...editForm, label: e.target.value })}
                            className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </div>
                        <div>
                          <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Content</label>
                          <textarea
                            value={editForm.content}
                            onChange={(e) => setEditForm({ ...editForm, content: e.target.value })}
                            className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none font-mono"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)', resize: 'vertical' }}
                            rows={16}
                          />
                        </div>
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={cancelEditing}
                            className="px-4 py-1.5 rounded-lg text-xs transition-colors"
                            style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)' }}
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => handleSave(prompt.id)}
                            disabled={isSaving}
                            className="px-4 py-1.5 rounded-lg text-xs text-white transition-colors disabled:opacity-50"
                            style={{ background: 'var(--app-gradient-primary)' }}
                          >
                            {isSaving ? 'Saving...' : 'Save'}
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* Preview (collapsed) */
                      <div className="px-4 pb-3">
                        <pre
                          className="text-xs whitespace-pre-wrap overflow-hidden font-mono leading-relaxed"
                          style={{
                            color: 'var(--app-text-muted)',
                            maxHeight: '4.5em',
                          }}
                        >
                          {prompt.content}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
