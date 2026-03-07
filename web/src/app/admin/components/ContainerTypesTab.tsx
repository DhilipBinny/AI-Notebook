'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin } from '@/lib/api'
import { Pencil, Trash2, Plus, X, Server } from 'lucide-react'
import type { ContainerType } from '@/types'

interface FormState {
  name: string
  label: string
  description: string
  image: string
  network: string
  memory_limit: string
  cpu_limit: string
  idle_timeout: string
}

const EMPTY_FORM: FormState = {
  name: '',
  label: '',
  description: '',
  image: '',
  network: 'ainotebook-network',
  memory_limit: '4g',
  cpu_limit: '4.0',
  idle_timeout: '3600',
}

export default function ContainerTypesTab() {
  const [types, setTypes] = useState<ContainerType[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Create
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<FormState>({ ...EMPTY_FORM })
  const [isCreating, setIsCreating] = useState(false)

  // Edit
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<FormState>({ ...EMPTY_FORM })
  const [isSaving, setIsSaving] = useState(false)

  // Delete
  const [deleteConfirm, setDeleteConfirm] = useState<ContainerType | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const fetchTypes = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await admin.containerTypes.list()
      setTypes(data)
    } catch {
      setError('Failed to load container types')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTypes()
  }, [fetchTypes])

  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(''), 3000)
      return () => clearTimeout(t)
    }
  }, [successMsg])

  const handleCreate = async () => {
    if (!createForm.name || !createForm.label || !createForm.image) return
    try {
      setIsCreating(true)
      await admin.containerTypes.create({
        name: createForm.name,
        label: createForm.label,
        description: createForm.description || undefined,
        image: createForm.image,
        network: createForm.network,
        memory_limit: createForm.memory_limit,
        cpu_limit: parseFloat(createForm.cpu_limit),
        idle_timeout: parseInt(createForm.idle_timeout),
      })
      setSuccessMsg('Container type created')
      setShowCreate(false)
      setCreateForm({ ...EMPTY_FORM })
      await fetchTypes()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create'
      setError(msg)
    } finally {
      setIsCreating(false)
    }
  }

  const startEdit = (ct: ContainerType) => {
    setEditingId(ct.id)
    setEditForm({
      name: ct.name,
      label: ct.label,
      description: ct.description || '',
      image: ct.image,
      network: ct.network,
      memory_limit: ct.memory_limit,
      cpu_limit: String(ct.cpu_limit),
      idle_timeout: String(ct.idle_timeout),
    })
  }

  const handleSave = async () => {
    if (!editingId) return
    try {
      setIsSaving(true)
      await admin.containerTypes.update(editingId, {
        label: editForm.label,
        description: editForm.description || undefined,
        image: editForm.image,
        network: editForm.network,
        memory_limit: editForm.memory_limit,
        cpu_limit: parseFloat(editForm.cpu_limit),
        idle_timeout: parseInt(editForm.idle_timeout),
      })
      setSuccessMsg('Container type updated')
      setEditingId(null)
      await fetchTypes()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update'
      setError(msg)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return
    try {
      setIsDeleting(true)
      await admin.containerTypes.delete(deleteConfirm.id)
      setSuccessMsg('Container type deleted')
      setDeleteConfirm(null)
      await fetchTypes()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete'
      setError(msg)
    } finally {
      setIsDeleting(false)
    }
  }

  const handleToggleActive = async (ct: ContainerType) => {
    try {
      await admin.containerTypes.update(ct.id, { is_active: !ct.is_active })
      await fetchTypes()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update'
      setError(msg)
    }
  }

  const inputStyle = {
    backgroundColor: 'var(--app-bg-input)',
    border: '1px solid var(--app-border-default)',
    color: 'var(--app-text-primary)',
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  const renderForm = (form: FormState, setForm: (f: FormState) => void, isNew: boolean) => (
    <div className="grid grid-cols-2 gap-4">
      {isNew && (
        <div>
          <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Name (unique key)</label>
          <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. doc_analyzer" className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none" style={inputStyle} />
        </div>
      )}
      <div>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Label</label>
        <input value={form.label} onChange={e => setForm({ ...form, label: e.target.value })}
          placeholder="Display name" className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none" style={inputStyle} />
      </div>
      <div className={isNew ? '' : 'col-span-2'}>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Description</label>
        <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
          placeholder="Optional description" className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none" style={inputStyle} />
      </div>
      <div className="col-span-2">
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Docker Image</label>
        <input value={form.image} onChange={e => setForm({ ...form, image: e.target.value })}
          placeholder="e.g. ainotebook-playground:latest" className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none" style={inputStyle} />
      </div>
      <div>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Network</label>
        <input value={form.network} onChange={e => setForm({ ...form, network: e.target.value })}
          className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none" style={inputStyle} />
      </div>
      <div>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Memory Limit</label>
        <input value={form.memory_limit} onChange={e => setForm({ ...form, memory_limit: e.target.value })}
          placeholder="e.g. 4g, 2g, 512m" className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none" style={inputStyle} />
      </div>
      <div>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>CPU Limit (cores)</label>
        <input value={form.cpu_limit} onChange={e => setForm({ ...form, cpu_limit: e.target.value })}
          type="number" step="0.25" min="0.25" max="64"
          className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none" style={inputStyle} />
      </div>
      <div>
        <label className="text-sm mb-1 block" style={{ color: 'var(--app-text-secondary)' }}>Idle Timeout (seconds)</label>
        <input value={form.idle_timeout} onChange={e => setForm({ ...form, idle_timeout: e.target.value })}
          type="number" min="60" max="86400"
          className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none" style={inputStyle} />
      </div>
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text-primary)' }}>Container Types</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--app-text-muted)' }}>
            Configure Docker container types with resource limits. Used when spinning up new containers.
          </p>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--app-alert-info-bg)', color: 'var(--app-accent-info)' }}>
              {types.length} type{types.length !== 1 ? 's' : ''}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'var(--app-alert-success-bg)', color: 'var(--app-accent-success)' }}>
              {types.filter(t => t.is_active).length} active
            </span>
          </div>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          style={{ backgroundColor: 'var(--app-accent-primary)', color: '#fff' }}
        >
          {showCreate ? <X size={16} /> : <Plus size={16} />}
          {showCreate ? 'Cancel' : 'Add Type'}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-success-bg)', color: 'var(--app-accent-success)' }}>
          {successMsg}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="mb-6 p-5 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--app-text-primary)' }}>New Container Type</h3>
          {renderForm(createForm, setCreateForm, true)}
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => { setShowCreate(false); setCreateForm({ ...EMPTY_FORM }) }}
              className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
            <button onClick={handleCreate} disabled={isCreating || !createForm.name || !createForm.label || !createForm.image}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              style={{ backgroundColor: 'var(--app-accent-primary)', color: '#fff' }}>
              {isCreating ? 'Creating...' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {/* Container type list */}
      {types.length === 0 ? (
        <div className="py-6 text-center text-sm rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
          No container types configured. Click &quot;Add Type&quot; to create one.
        </div>
      ) : (
        <div className="space-y-3">
          {types.map(ct => (
            <div key={ct.id} className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
              {/* Header row */}
              <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: editingId === ct.id ? '1px solid var(--app-border-default)' : 'none' }}>
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--app-bg-tertiary)' }}>
                    <Server size={18} style={{ color: ct.is_active ? 'var(--app-accent-primary)' : 'var(--app-text-muted)' }} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold" style={{ color: 'var(--app-text-primary)' }}>{ct.label}</span>
                      <code className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-muted)' }}>{ct.name}</code>
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{
                        backgroundColor: ct.is_active ? 'var(--app-alert-success-bg)' : 'var(--app-alert-error-bg)',
                        color: ct.is_active ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                      }}>
                        {ct.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    {ct.description && (
                      <p className="text-xs mt-0.5" style={{ color: 'var(--app-text-muted)' }}>{ct.description}</p>
                    )}
                  </div>
                </div>

                {/* Resource badges + actions */}
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ backgroundColor: 'var(--app-alert-indigo-bg)', color: 'var(--app-accent-indigo)' }}>
                      {ct.memory_limit} RAM
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ backgroundColor: 'var(--app-alert-info-bg)', color: 'var(--app-accent-info)' }}>
                      {ct.cpu_limit} CPU
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded font-mono" style={{ backgroundColor: 'var(--app-alert-warning-bg)', color: 'var(--app-accent-warning)' }}>
                      {ct.idle_timeout}s idle
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button onClick={() => handleToggleActive(ct)}
                      className="p-1.5 rounded-md transition-colors text-xs px-2 font-medium"
                      style={{ color: ct.is_active ? 'var(--app-accent-error)' : 'var(--app-accent-success)' }}
                      title={ct.is_active ? 'Deactivate' : 'Activate'}>
                      {ct.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button onClick={() => editingId === ct.id ? setEditingId(null) : startEdit(ct)}
                      className="p-1.5 rounded-md transition-colors hover-text-primary"
                      style={{ color: 'var(--app-text-muted)' }} title="Edit">
                      <Pencil size={14} />
                    </button>
                    {ct.name !== 'playground' && (
                      <button onClick={() => setDeleteConfirm(ct)}
                        className="p-1.5 rounded-md transition-colors hover-text-error"
                        style={{ color: 'var(--app-text-muted)' }} title="Delete">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Edit form (inline) */}
              {editingId === ct.id && (
                <div className="px-5 py-4" style={{ backgroundColor: 'var(--app-bg-secondary)' }}>
                  {renderForm(editForm, setEditForm, false)}
                  <div className="flex justify-end gap-2 mt-4">
                    <button onClick={() => setEditingId(null)}
                      className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
                    <button onClick={handleSave} disabled={isSaving}
                      className="px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                      style={{ backgroundColor: 'var(--app-accent-primary)', color: '#fff' }}>
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </div>
              )}

              {/* Image row (collapsed view) */}
              {editingId !== ct.id && (
                <div className="px-5 py-2 flex items-center gap-4" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                  <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Image:</span>
                  <code className="text-xs font-mono" style={{ color: 'var(--app-text-secondary)' }}>{ct.image}</code>
                  <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Network:</span>
                  <code className="text-xs font-mono" style={{ color: 'var(--app-text-secondary)' }}>{ct.network}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Info banner */}
      <div className="mt-6 p-4 rounded-lg text-xs" style={{ backgroundColor: 'var(--app-alert-info-bg)', color: 'var(--app-accent-info)' }}>
        Changes take effect for <strong>newly created</strong> containers only. Running containers keep their original resource limits.
        Env var fallbacks (PLAYGROUND_MEMORY_LIMIT, PLAYGROUND_CPU_LIMIT) are used if no DB config is found.
      </div>

      {/* Delete confirmation modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !isDeleting && setDeleteConfirm(null)} />
          <div className="relative w-full max-w-sm rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-alert-error-border)' }}>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--app-alert-error-bg)' }}>
                <Trash2 className="w-5 h-5" style={{ color: 'var(--app-accent-error)' }} />
              </div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--app-text-primary)' }}>Delete Container Type</h3>
            </div>
            <p className="mb-5 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Delete &quot;{deleteConfirm.label}&quot; (<code className="font-mono">{deleteConfirm.name}</code>)? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteConfirm(null)} disabled={isDeleting}
                className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
              <button onClick={handleDelete} disabled={isDeleting}
                className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ backgroundColor: 'var(--app-accent-error)', color: '#fff' }}>
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
