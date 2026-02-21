'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { admin, auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { PlatformKey } from '@/types'

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'openai_compatible'] as const

const DEFAULT_MODELS: Record<string, string> = {
  gemini: 'gemini-2.5-flash',
  openai: 'gpt-4o',
  anthropic: 'claude-sonnet-4-20250514',
  openai_compatible: 'qwen2.5:7b',
}

export default function AdminPlatformKeysPage() {
  const [keys, setKeys] = useState<PlatformKey[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    provider: 'gemini',
    label: '',
    api_key: '',
    model_name: DEFAULT_MODELS['gemini'],
    base_url: '',
  })
  const [isCreating, setIsCreating] = useState(false)

  // Edit form
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({
    label: '',
    api_key: '',
    model_name: '',
    base_url: '',
  })
  const [isSaving, setIsSaving] = useState(false)

  // Validation
  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [validationResults, setValidationResults] = useState<Record<string, { valid: boolean; error?: string }>>({})

  // Action loading
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

  const router = useRouter()
  const { user, setUser } = useAuthStore()
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  // Fetch user on mount if not in store (handles page refresh)
  useEffect(() => {
    const init = async () => {
      if (!user) {
        const token = localStorage.getItem('access_token')
        if (!token) {
          router.push('/auth/login')
          return
        }
        try {
          const userData = await auth.getMe()
          setUser(userData)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          router.push('/auth/login')
          return
        }
      }
      setAuthChecked(true)
    }
    init()
  }, [user, setUser, router])

  useEffect(() => {
    if (authChecked && user && !user.is_admin) {
      router.push('/dashboard')
    }
  }, [user, authChecked, router])

  const fetchKeys = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await admin.platformKeys.list()
      setKeys(data)
    } catch {
      setError('Failed to load platform keys')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchKeys()
    }
  }, [user, fetchKeys])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      setIsCreating(true)
      await admin.platformKeys.create({
        provider: createForm.provider,
        label: createForm.label,
        api_key: createForm.api_key,
        model_name: createForm.model_name,
        base_url: createForm.base_url || undefined,
      })
      setCreateForm({ provider: 'gemini', label: '', api_key: '', model_name: DEFAULT_MODELS['gemini'], base_url: '' })
      setShowCreate(false)
      setSuccessMsg('Platform key created')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to create platform key')
    } finally {
      setIsCreating(false)
    }
  }

  const startEditing = (key: PlatformKey) => {
    setEditingId(key.id)
    setEditForm({
      label: key.label,
      api_key: '',
      model_name: key.model_name || '',
      base_url: key.base_url || '',
    })
  }

  const handleSave = async (keyId: string) => {
    try {
      setIsSaving(true)
      const updateData: { label?: string; api_key?: string; model_name?: string; base_url?: string } = {}
      if (editForm.label) updateData.label = editForm.label
      if (editForm.api_key) updateData.api_key = editForm.api_key
      if (editForm.model_name !== undefined) updateData.model_name = editForm.model_name
      if (editForm.base_url !== undefined) updateData.base_url = editForm.base_url
      await admin.platformKeys.update(keyId, updateData)
      setEditingId(null)
      setSuccessMsg('Key updated')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to update key')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (keyId: string) => {
    if (!confirm('Delete this platform key?')) return
    try {
      setActionLoadingId(keyId)
      await admin.platformKeys.delete(keyId)
      setSuccessMsg('Key deleted')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to delete key')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleActivate = async (keyId: string) => {
    try {
      setActionLoadingId(keyId)
      await admin.platformKeys.activate(keyId)
      setSuccessMsg('Key activated')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to activate key')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleDeactivate = async (keyId: string) => {
    try {
      setActionLoadingId(keyId)
      await admin.platformKeys.deactivate(keyId)
      setSuccessMsg('Key deactivated')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to deactivate key')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleSetDefault = async (keyId: string) => {
    try {
      setActionLoadingId(keyId)
      await admin.platformKeys.setDefault(keyId)
      setSuccessMsg('Default provider set')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch {
      setError('Failed to set default')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleValidate = async (keyId: string) => {
    try {
      setValidatingId(keyId)
      const result = await admin.platformKeys.validate(keyId)
      setValidationResults(prev => ({ ...prev, [keyId]: result }))
      setTimeout(() => {
        setValidationResults(prev => {
          const next = { ...prev }
          delete next[keyId]
          return next
        })
      }, 5000)
    } catch {
      setValidationResults(prev => ({ ...prev, [keyId]: { valid: false, error: 'Validation request failed' } }))
    } finally {
      setValidatingId(null)
    }
  }

  // Group keys by provider
  const keysByProvider = PROVIDERS.map(provider => ({
    provider,
    keys: keys.filter(k => k.provider === provider),
  })).filter(group => group.keys.length > 0)

  if (!authChecked || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
        <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  if (!user.is_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
        <p style={{ color: 'var(--app-text-muted)' }}>Access denied</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text-primary)' }}>
              Platform API Keys
            </h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Manage encrypted LLM provider keys. One active key per provider at a time.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
              style={{ background: 'var(--app-gradient-primary)' }}
            >
              {showCreate ? 'Cancel' : 'Add Key'}
            </button>
            <button
              onClick={() => router.push('/dashboard')}
              className="px-4 py-2 rounded-lg text-sm transition-colors"
              style={{
                backgroundColor: 'var(--app-bg-tertiary)',
                color: 'var(--app-text-secondary)',
                border: '1px solid var(--app-border-default)',
              }}
            >
              Back to Dashboard
            </button>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
          </div>
        )}
        {successMsg && (
          <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            {successMsg}
          </div>
        )}

        {/* Create Form */}
        {showCreate && (
          <div className="mb-8 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            <h2 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>
              Add Platform Key
            </h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Provider</label>
                  <select
                    value={createForm.provider}
                    onChange={(e) => {
                      const provider = e.target.value
                      setCreateForm({ ...createForm, provider, model_name: DEFAULT_MODELS[provider] || '', base_url: '' })
                    }}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  >
                    {PROVIDERS.map(p => (
                      <option key={p} value={p}>{p === 'openai_compatible' ? 'OpenAI Compatible' : p.charAt(0).toUpperCase() + p.slice(1)}</option>
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
                    placeholder="e.g., Production Gemini Key"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>
                    API Key{createForm.provider === 'openai_compatible' ? ' (optional)' : ''}
                  </label>
                  <input
                    type="password"
                    value={createForm.api_key}
                    onChange={(e) => setCreateForm({ ...createForm, api_key: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                    placeholder={createForm.provider === 'openai_compatible' ? 'Optional for local servers' : 'sk-... or AIza...'}
                    required={createForm.provider !== 'openai_compatible'}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Model Name</label>
                  <input
                    type="text"
                    value={createForm.model_name}
                    onChange={(e) => setCreateForm({ ...createForm, model_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                    placeholder="e.g., gemini-2.5-flash"
                    required
                  />
                </div>
              </div>
              {createForm.provider === 'openai_compatible' && (
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Base URL</label>
                  <input
                    type="text"
                    value={createForm.base_url}
                    onChange={(e) => setCreateForm({ ...createForm, base_url: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                    placeholder="e.g., http://localhost:11434/v1 or https://openrouter.ai/api/v1"
                    required
                  />
                </div>
              )}
              <button
                type="submit"
                disabled={isCreating}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isCreating ? 'Creating...' : 'Create Key'}
              </button>
            </form>
          </div>
        )}

        {/* Keys List */}
        {isLoading ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
        ) : keys.length === 0 ? (
          <div className="p-8 text-center rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
            No platform keys configured. Click &quot;Add Key&quot; to get started.
          </div>
        ) : (
          <div className="space-y-6">
            {keysByProvider.map(({ provider, keys: providerKeys }) => (
              <div key={provider} className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-medium" style={{ color: 'var(--app-text-primary)' }}>
                      {provider === 'openai_compatible' ? 'OpenAI Compatible' : provider.charAt(0).toUpperCase() + provider.slice(1)}
                    </h2>
                    {providerKeys.some(k => k.is_default) && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
                        Default Provider
                      </span>
                    )}
                  </div>
                  <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                    {providerKeys.length} key{providerKeys.length !== 1 ? 's' : ''}
                  </span>
                </div>

                <div className="divide-y" style={{ borderColor: 'var(--app-border-default)' }}>
                  {providerKeys.map(key => (
                    <div key={key.id} className="px-6 py-4">
                      {editingId === key.id ? (
                        /* Edit mode */
                        <div className="space-y-3">
                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Label</label>
                              <input
                                type="text"
                                value={editForm.label}
                                onChange={(e) => setEditForm({ ...editForm, label: e.target.value })}
                                className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                              />
                            </div>
                            <div>
                              <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>New API Key (leave empty to keep)</label>
                              <input
                                type="password"
                                value={editForm.api_key}
                                onChange={(e) => setEditForm({ ...editForm, api_key: e.target.value })}
                                className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                                placeholder={key.api_key_hint}
                              />
                            </div>
                            <div>
                              <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Model Override</label>
                              <input
                                type="text"
                                value={editForm.model_name}
                                onChange={(e) => setEditForm({ ...editForm, model_name: e.target.value })}
                                className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                              />
                            </div>
                          </div>
                          {key.provider === 'openai_compatible' && (
                            <div>
                              <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Base URL</label>
                              <input
                                type="text"
                                value={editForm.base_url}
                                onChange={(e) => setEditForm({ ...editForm, base_url: e.target.value })}
                                className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                                placeholder="e.g., http://localhost:11434/v1"
                              />
                            </div>
                          )}
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleSave(key.id)}
                              disabled={isSaving}
                              className="px-3 py-1.5 rounded-lg text-xs text-white disabled:opacity-50"
                              style={{ background: 'var(--app-gradient-primary)' }}
                            >
                              {isSaving ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              onClick={() => setEditingId(null)}
                              className="px-3 py-1.5 rounded-lg text-xs"
                              style={{
                                backgroundColor: 'var(--app-bg-tertiary)',
                                color: 'var(--app-text-secondary)',
                                border: '1px solid var(--app-border-default)',
                              }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* View mode */
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            {/* Status dot */}
                            <div
                              className="w-2.5 h-2.5 rounded-full"
                              style={{ backgroundColor: key.is_active ? '#10b981' : '#6b7280' }}
                              title={key.is_active ? 'Active' : 'Inactive'}
                            />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-sm" style={{ color: 'var(--app-text-primary)' }}>
                                  {key.label}
                                </span>
                                {key.is_default && (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ backgroundColor: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
                                    DEFAULT
                                  </span>
                                )}
                                {validationResults[key.id] && (
                                  <span
                                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                                    style={{
                                      backgroundColor: validationResults[key.id].valid ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                      color: validationResults[key.id].valid ? '#10b981' : '#ef4444',
                                    }}
                                  >
                                    {validationResults[key.id].valid ? 'VALID' : 'INVALID'}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-3 mt-0.5">
                                <span className="font-mono text-xs" style={{ color: 'var(--app-text-muted)' }}>
                                  {key.api_key_hint}
                                </span>
                                <span className="text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                                  Model: {key.model_name || '(not set)'}
                                </span>
                                {key.base_url && (
                                  <span className="text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                                    URL: {key.base_url}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleValidate(key.id)}
                              disabled={validatingId === key.id}
                              className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                              style={{
                                backgroundColor: 'var(--app-bg-tertiary)',
                                color: 'var(--app-text-secondary)',
                                border: '1px solid var(--app-border-default)',
                              }}
                            >
                              {validatingId === key.id ? 'Testing...' : 'Test (beta)'}
                            </button>

                            {key.is_active ? (
                              <button
                                onClick={() => handleDeactivate(key.id)}
                                disabled={actionLoadingId === key.id}
                                className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                                style={{
                                  backgroundColor: 'rgba(245, 158, 11, 0.1)',
                                  color: '#f59e0b',
                                  border: '1px solid rgba(245, 158, 11, 0.3)',
                                }}
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                onClick={() => handleActivate(key.id)}
                                disabled={actionLoadingId === key.id}
                                className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                                style={{
                                  backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                  color: '#10b981',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                }}
                              >
                                Activate
                              </button>
                            )}

                            {!key.is_default && (
                              <button
                                onClick={() => handleSetDefault(key.id)}
                                disabled={actionLoadingId === key.id}
                                className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                                style={{
                                  backgroundColor: 'rgba(99, 102, 241, 0.1)',
                                  color: '#818cf8',
                                  border: '1px solid rgba(99, 102, 241, 0.3)',
                                }}
                              >
                                Set Default
                              </button>
                            )}

                            <button
                              onClick={() => startEditing(key)}
                              className="px-3 py-1.5 rounded-lg text-xs transition-colors"
                              style={{
                                backgroundColor: 'var(--app-bg-tertiary)',
                                color: 'var(--app-text-secondary)',
                                border: '1px solid var(--app-border-default)',
                              }}
                            >
                              Edit
                            </button>

                            <button
                              onClick={() => handleDelete(key.id)}
                              disabled={actionLoadingId === key.id}
                              className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                              style={{ color: 'var(--app-accent-error)' }}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Providers with no keys */}
            {PROVIDERS.filter(p => !keysByProvider.some(g => g.provider === p)).length > 0 && (
              <div className="p-4 rounded-xl text-sm" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
                No keys configured for: {PROVIDERS.filter(p => !keysByProvider.some(g => g.provider === p)).join(', ')}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
