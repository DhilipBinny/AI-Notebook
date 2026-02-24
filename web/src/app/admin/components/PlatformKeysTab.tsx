'use client'

import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import { createPortal } from 'react-dom'
import { admin, models as modelsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { MoreHorizontal, FlaskConical, Star, Trash2 } from 'lucide-react'
import type { PlatformKey, LLMModelBrief } from '@/types'

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'openai_compatible'] as const

export default function PlatformKeysTab() {
  const [keys, setKeys] = useState<PlatformKey[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Provider models from registry
  const [providerModels, setProviderModels] = useState<Record<string, LLMModelBrief[]>>({})

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    provider: 'gemini',
    label: '',
    api_key: '',
    auth_type: 'api_key' as 'api_key' | 'oauth_token',
    model_name: '',
    base_url: '',
  })
  const [isCreating, setIsCreating] = useState(false)

  // Slide-out drawer
  const [drawerKey, setDrawerKey] = useState<PlatformKey | null>(null)
  const [drawerEditing, setDrawerEditing] = useState(false)
  const [drawerEditForm, setDrawerEditForm] = useState({
    label: '',
    api_key: '',
    auth_type: 'api_key' as 'api_key' | 'oauth_token',
    model_name: '',
    base_url: '',
  })
  const [isSavingDrawer, setIsSavingDrawer] = useState(false)

  // Validation
  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [validationResults, setValidationResults] = useState<Record<string, { valid: boolean; error?: string }>>({})

  // Action loading
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

  // Overflow menu
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const user = useAuthStore((state) => state.user)

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

  const fetchModelsForProvider = useCallback(async (provider: string) => {
    try {
      const data = await modelsApi.listByProvider(provider)
      setProviderModels(prev => ({ ...prev, [provider]: data }))
      return data
    } catch {
      return []
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchKeys()
      PROVIDERS.forEach(p => fetchModelsForProvider(p))
    }
  }, [user, fetchKeys, fetchModelsForProvider])

  // When provider changes in create form, update model selection
  useEffect(() => {
    const models = providerModels[createForm.provider]
    if (models && models.length > 0) {
      setCreateForm(prev => ({ ...prev, model_name: models[0].model_id }))
    }
  }, [createForm.provider, providerModels])

  // Click-outside to close overflow menu
  useEffect(() => {
    if (!openMenuId) return
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [openMenuId])

  // Keep drawer in sync with fetched keys
  useEffect(() => {
    if (drawerKey) {
      const updated = keys.find(k => k.id === drawerKey.id)
      if (updated) setDrawerKey(updated)
    }
  }, [keys]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Drawer helpers ---
  const openDrawer = (key: PlatformKey) => {
    setDrawerKey(key)
    setDrawerEditing(false)
    fetchModelsForProvider(key.provider)
  }

  const closeDrawer = () => {
    setDrawerKey(null)
    setDrawerEditing(false)
    setDrawerEditForm({ label: '', api_key: '', auth_type: 'api_key', model_name: '', base_url: '' })
  }

  const startDrawerEditing = () => {
    if (!drawerKey) return
    setDrawerEditing(true)
    setDrawerEditForm({
      label: drawerKey.label,
      api_key: '',
      auth_type: drawerKey.auth_type || 'api_key',
      model_name: drawerKey.model_name || '',
      base_url: drawerKey.base_url || '',
    })
  }

  const handleDrawerSave = async () => {
    if (!drawerKey) return
    try {
      setIsSavingDrawer(true)
      const updateData: { label?: string; api_key?: string; auth_type?: string; model_name?: string; base_url?: string } = {}
      if (drawerEditForm.label) updateData.label = drawerEditForm.label
      if (drawerEditForm.api_key) updateData.api_key = drawerEditForm.api_key
      if (drawerKey.provider === 'anthropic') updateData.auth_type = drawerEditForm.auth_type
      if (drawerEditForm.model_name !== undefined) updateData.model_name = drawerEditForm.model_name
      if (drawerEditForm.base_url !== undefined) updateData.base_url = drawerEditForm.base_url

      await admin.platformKeys.update(drawerKey.id, updateData)
      setDrawerEditing(false)
      setSuccessMsg('Key updated')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update key'
      setError(errorMsg)
    } finally {
      setIsSavingDrawer(false)
    }
  }

  // --- Handlers ---
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const modelName = createForm.model_name

    if (!modelName) {
      setError('Model name is required')
      return
    }

    try {
      setIsCreating(true)
      await admin.platformKeys.create({
        provider: createForm.provider,
        label: createForm.label,
        api_key: createForm.api_key,
        auth_type: createForm.provider === 'anthropic' ? createForm.auth_type : undefined,
        model_name: modelName,
        base_url: createForm.base_url || undefined,
      })
      setCreateForm({ provider: 'gemini', label: '', api_key: '', auth_type: 'api_key', model_name: '', base_url: '' })
      setShowCreate(false)
      setSuccessMsg('Platform key created')
      fetchKeys()
      fetchModelsForProvider(createForm.provider)
      setTimeout(() => setSuccessMsg(''), 5000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create platform key'
      setError(errorMsg)
    } finally {
      setIsCreating(false)
    }
  }

  const handleDelete = async (keyId: string) => {
    if (!confirm('Delete this platform key?')) return
    try {
      setActionLoadingId(keyId)
      await admin.platformKeys.delete(keyId)
      setSuccessMsg('Key deleted')
      if (drawerKey?.id === keyId) closeDrawer()
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

  const handleToggleVisibility = async (provider: string, currentVisible: boolean) => {
    try {
      await admin.platformKeys.toggleProviderVisibility(provider, !currentVisible)
      // Update local state — toggle user_visible on all keys of this provider
      setKeys(prev => prev.map(k =>
        k.provider === provider ? { ...k, user_visible: !currentVisible } : k
      ))
    } catch {
      setError('Failed to toggle provider visibility')
    }
  }

  // Group keys by provider
  const keysByProvider = PROVIDERS.map(provider => ({
    provider,
    keys: keys.filter(k => k.provider === provider),
  })).filter(group => group.keys.length > 0)

  const isOpenAICompatible = (provider: string) => provider === 'openai_compatible'

  const providerDisplayName = (provider: string) =>
    provider === 'openai_compatible' ? 'OpenAI Compatible' : provider.charAt(0).toUpperCase() + provider.slice(1)

  const renderModelSelect = (
    provider: string,
    value: string,
    onChange: (val: string) => void,
  ) => {
    const availableModels = providerModels[provider] || []

    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
        style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
        required
      >
        {availableModels.length === 0 && (
          <option value="">No models registered</option>
        )}
        {availableModels.map(m => (
          <option key={m.model_id} value={m.model_id}>{m.display_name} ({m.model_id})</option>
        ))}
      </select>
    )
  }

  return (
    <div>
      {/* Action bar */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
          Manage encrypted LLM provider keys. One active key per provider at a time.
        </p>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
          style={{ background: 'var(--app-gradient-primary)' }}
        >
          {showCreate ? 'Cancel' : 'Add Key'}
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
                    setCreateForm({ ...createForm, provider, model_name: '', base_url: '', auth_type: 'api_key' })
                    fetchModelsForProvider(provider)
                  }}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                >
                  {PROVIDERS.map(p => (
                    <option key={p} value={p}>{providerDisplayName(p)}</option>
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
                  {createForm.provider === 'anthropic' && createForm.auth_type === 'oauth_token' ? 'OAuth Token' : 'API Key'}
                  {isOpenAICompatible(createForm.provider) ? ' (optional)' : ''}
                </label>
                <input
                  type="password"
                  value={createForm.api_key}
                  onChange={(e) => setCreateForm({ ...createForm, api_key: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder={
                    isOpenAICompatible(createForm.provider) ? 'Optional for local servers' :
                    createForm.provider === 'anthropic' && createForm.auth_type === 'oauth_token' ? 'sk-ant-oat01-...' :
                    'sk-... or AIza...'
                  }
                  required={!isOpenAICompatible(createForm.provider)}
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Model</label>
                {renderModelSelect(
                  createForm.provider,
                  createForm.model_name,
                  (val) => setCreateForm({ ...createForm, model_name: val }),
                )}
              </div>
            </div>
            {createForm.provider === 'anthropic' && (
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Auth Type</label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="create_auth_type" value="api_key" checked={createForm.auth_type === 'api_key'} onChange={() => setCreateForm({ ...createForm, auth_type: 'api_key' })} style={{ accentColor: 'var(--app-accent-indigo)' }} />
                    <span className="text-sm" style={{ color: 'var(--app-text-primary)' }}>API Key</span>
                    <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>(sk-ant-api03-...)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="create_auth_type" value="oauth_token" checked={createForm.auth_type === 'oauth_token'} onChange={() => setCreateForm({ ...createForm, auth_type: 'oauth_token' })} style={{ accentColor: 'var(--app-accent-indigo)' }} />
                    <span className="text-sm" style={{ color: 'var(--app-text-primary)' }}>OAuth Token</span>
                    <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>(sk-ant-oat01-...)</span>
                  </label>
                </div>
              </div>
            )}
            {isOpenAICompatible(createForm.provider) && (
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

      {/* Slide-out Drawer (portal to body to avoid overflow clipping) */}
      {drawerKey && createPortal(
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeDrawer} />
          <div
            className="absolute right-0 top-0 h-full w-full max-w-lg overflow-y-auto shadow-2xl"
            style={{ backgroundColor: 'var(--app-bg-primary)', borderLeft: '1px solid var(--app-border-default)' }}
          >
            {/* Sticky Header */}
            <div className="sticky top-0 z-10 px-6 py-4 flex items-center justify-between" style={{ backgroundColor: 'var(--app-bg-primary)', borderBottom: '1px solid var(--app-border-default)' }}>
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text-primary)' }}>Key Details</h2>
              <button onClick={closeDrawer} className="p-1.5 rounded-lg transition-colors hover:opacity-80" style={{ color: 'var(--app-text-muted)' }}>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Key Identity */}
              <div className="flex items-start gap-4">
                <div
                  className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold flex-shrink-0"
                  style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}
                >
                  {drawerKey.provider === 'openai_compatible' ? 'OC' : drawerKey.provider.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="text-base font-semibold truncate" style={{ color: 'var(--app-text-primary)' }}>
                    {drawerKey.label}
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                    {providerDisplayName(drawerKey.provider)}
                  </p>
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-medium"
                      style={{
                        backgroundColor: drawerKey.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: drawerKey.is_active ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                      }}
                    >
                      {drawerKey.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {drawerKey.is_default && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: 'rgba(99, 102, 241, 0.15)', color: 'var(--app-accent-indigo)' }}>
                        DEFAULT
                      </span>
                    )}
                    {drawerKey.provider === 'anthropic' && drawerKey.auth_type === 'oauth_token' && (
                      <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'var(--app-accent-warning)' }}>
                        OAuth
                      </span>
                    )}
                    {validatingId === drawerKey.id && (
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium inline-flex items-center gap-1.5"
                        style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: 'var(--app-accent-primary)' }}
                      >
                        <span className="inline-block w-3 h-3 rounded-full animate-spin" style={{ borderWidth: '1.5px', borderColor: 'rgba(59, 130, 246, 0.3)', borderTopColor: 'var(--app-accent-primary)' }} />
                        Testing...
                      </span>
                    )}
                    {(!validatingId || validatingId !== drawerKey.id) && validationResults[drawerKey.id] && (
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: validationResults[drawerKey.id].valid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: validationResults[drawerKey.id].valid ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                        }}
                      >
                        {validationResults[drawerKey.id].valid ? 'VALID' : 'INVALID'}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Key Details Card */}
              <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>Key Details</span>
                  {!drawerEditing && (
                    <button
                      onClick={startDrawerEditing}
                      className="text-xs px-2 py-1 rounded-lg transition-colors hover:opacity-80"
                      style={{ color: 'var(--app-accent-primary)' }}
                    >
                      Edit
                    </button>
                  )}
                </div>

                {drawerEditing ? (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Label</label>
                      <input
                        type="text"
                        value={drawerEditForm.label}
                        onChange={(e) => setDrawerEditForm({ ...drawerEditForm, label: e.target.value })}
                        className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                        style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                      />
                    </div>
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>
                        New {drawerKey.provider === 'anthropic' && drawerEditForm.auth_type === 'oauth_token' ? 'OAuth Token' : 'API Key'} (leave empty to keep)
                      </label>
                      <input
                        type="password"
                        value={drawerEditForm.api_key}
                        onChange={(e) => setDrawerEditForm({ ...drawerEditForm, api_key: e.target.value })}
                        className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                        style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                        placeholder={drawerKey.api_key_hint}
                      />
                    </div>
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Model</label>
                      {renderModelSelect(
                        drawerKey.provider,
                        drawerEditForm.model_name,
                        (val) => setDrawerEditForm({ ...drawerEditForm, model_name: val }),
                      )}
                    </div>
                    {drawerKey.provider === 'anthropic' && (
                      <div>
                        <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Auth Type</label>
                        <div className="flex gap-3">
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="radio" name="drawer_auth_type" value="api_key" checked={drawerEditForm.auth_type === 'api_key'} onChange={() => setDrawerEditForm({ ...drawerEditForm, auth_type: 'api_key' })} style={{ accentColor: 'var(--app-accent-indigo)' }} />
                            <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>API Key</span>
                          </label>
                          <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="radio" name="drawer_auth_type" value="oauth_token" checked={drawerEditForm.auth_type === 'oauth_token'} onChange={() => setDrawerEditForm({ ...drawerEditForm, auth_type: 'oauth_token' })} style={{ accentColor: 'var(--app-accent-indigo)' }} />
                            <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>OAuth Token</span>
                          </label>
                        </div>
                      </div>
                    )}
                    {isOpenAICompatible(drawerKey.provider) && (
                      <div>
                        <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Base URL</label>
                        <input
                          type="text"
                          value={drawerEditForm.base_url}
                          onChange={(e) => setDrawerEditForm({ ...drawerEditForm, base_url: e.target.value })}
                          className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          placeholder="e.g., http://localhost:11434/v1"
                        />
                      </div>
                    )}
                    <div className="flex gap-2 justify-end pt-1">
                      <button
                        onClick={() => setDrawerEditing(false)}
                        className="px-3 py-1.5 rounded-lg text-xs"
                        style={{ color: 'var(--app-text-muted)' }}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleDrawerSave}
                        disabled={isSavingDrawer}
                        className="px-3 py-1.5 rounded-lg text-xs text-white font-medium disabled:opacity-50"
                        style={{ background: 'var(--app-gradient-primary)' }}
                      >
                        {isSavingDrawer ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Key Hint</span>
                      <span className="font-mono text-xs" style={{ color: 'var(--app-text-primary)' }}>{drawerKey.api_key_hint}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Model</span>
                      <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>{drawerKey.model_name || '(no model)'}</span>
                    </div>
                    {drawerKey.provider === 'anthropic' && (
                      <div className="flex justify-between">
                        <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Auth Type</span>
                        <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>{drawerKey.auth_type === 'oauth_token' ? 'OAuth Token' : 'API Key'}</span>
                      </div>
                    )}
                    {drawerKey.base_url && (
                      <div className="flex justify-between">
                        <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Base URL</span>
                        <span className="text-xs truncate max-w-[250px]" style={{ color: 'var(--app-text-primary)' }}>{drawerKey.base_url}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Created</span>
                      <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>{new Date(drawerKey.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Priority</span>
                      <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>{drawerKey.priority}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Quick Actions */}
              <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--app-border-default)' }}>
                <div className="px-4 py-2.5" style={{ backgroundColor: 'var(--app-bg-card)', borderBottom: '1px solid var(--app-border-default)' }}>
                  <span className="text-xs font-medium" style={{ color: 'var(--app-text-muted)' }}>Actions</span>
                </div>
                <button
                  onClick={() => handleValidate(drawerKey.id)}
                  disabled={validatingId === drawerKey.id}
                  className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors disabled:opacity-50"
                  style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-secondary)', borderBottom: '1px solid var(--app-border-default)' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                >
                  {validatingId === drawerKey.id ? (
                    <span className="w-4 h-4 rounded-full animate-spin flex-shrink-0" style={{ borderWidth: '2px', borderColor: 'rgba(59, 130, 246, 0.3)', borderTopColor: 'var(--app-accent-primary)' }} />
                  ) : (
                    <FlaskConical className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--app-accent-primary)' }} />
                  )}
                  {validatingId === drawerKey.id ? 'Testing key...' : 'Test Key'}
                </button>
                {!drawerKey.is_default && (
                  <button
                    onClick={() => handleSetDefault(drawerKey.id)}
                    disabled={actionLoadingId === drawerKey.id}
                    className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors disabled:opacity-50"
                    style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-accent-indigo)', borderBottom: '1px solid var(--app-border-default)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                  >
                    <Star className="w-4 h-4 flex-shrink-0" />
                    Set Default
                  </button>
                )}
                <button
                  onClick={() => handleDelete(drawerKey.id)}
                  disabled={actionLoadingId === drawerKey.id}
                  className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors disabled:opacity-50"
                  style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-accent-error)' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                >
                  <Trash2 className="w-4 h-4 flex-shrink-0" />
                  Delete Key
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Keys Table */}
      {isLoading ? (
        <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
      ) : keys.length === 0 ? (
        <div className="p-8 text-center rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
          No platform keys configured. Click &quot;Add Key&quot; to get started.
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Name</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Key Hint</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Model</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Status</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Base URL</th>
                  <th className="w-12 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {keysByProvider.map(({ provider, keys: providerKeys }) => (
                  <Fragment key={provider}>
                    {/* Provider Group Header */}
                    <tr style={{ backgroundColor: 'var(--app-bg-tertiary)' }}>
                      <td colSpan={6} className="px-4 py-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="font-medium text-sm" style={{ color: 'var(--app-text-primary)' }}>
                              {providerDisplayName(provider)}
                            </span>
                            {providerKeys.some(k => k.is_default) && (
                              <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: 'rgba(99, 102, 241, 0.2)', color: 'var(--app-accent-indigo)' }}>
                                Default Provider
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4">
                            <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                              {providerKeys.length} key{providerKeys.length !== 1 ? 's' : ''}
                            </span>
                            {/* User Visible toggle */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleToggleVisibility(provider, providerKeys[0]?.user_visible ?? true)
                              }}
                              className="flex items-center gap-2 text-xs"
                              title={providerKeys[0]?.user_visible !== false ? 'Visible to users — click to hide' : 'Hidden from users — click to show'}
                            >
                              <span style={{ color: 'var(--app-text-muted)' }}>Users</span>
                              <div
                                className="relative w-8 h-4 rounded-full transition-colors cursor-pointer"
                                style={{
                                  backgroundColor: providerKeys[0]?.user_visible !== false
                                    ? 'var(--app-accent-success)' : 'var(--app-bg-tertiary)',
                                  border: '1px solid var(--app-border-default)',
                                }}
                              >
                                <div
                                  className="absolute top-0.5 w-2.5 h-2.5 rounded-full transition-all"
                                  style={{
                                    backgroundColor: providerKeys[0]?.user_visible !== false
                                      ? '#fff' : 'var(--app-text-muted)',
                                    left: providerKeys[0]?.user_visible !== false ? '14px' : '2px',
                                  }}
                                />
                              </div>
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>

                    {/* Key Rows */}
                    {providerKeys.map((key, keyIdx) => {
                      // Check if this is one of the last 2 rows in the entire table
                      const isNearBottom = (() => {
                        const groupIdx = keysByProvider.findIndex(g => g.provider === provider)
                        const rowsBefore = keysByProvider.slice(0, groupIdx).reduce((sum, g) => sum + g.keys.length, 0)
                        const totalRows = keys.length
                        return (rowsBefore + keyIdx) >= totalRows - 2
                      })()
                      return (
                      <tr
                        key={key.id}
                        className="cursor-pointer transition-colors"
                        style={{ borderBottom: '1px solid var(--app-border-default)' }}
                        onClick={() => openDrawer(key)}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        {/* Name + Badges (indented under provider) */}
                        <td className="pl-8 pr-4 py-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm" style={{ color: 'var(--app-text-primary)' }}>
                              {key.label}
                            </span>
                            {key.is_default && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ backgroundColor: 'rgba(99, 102, 241, 0.2)', color: 'var(--app-accent-indigo)' }}>
                                DEFAULT
                              </span>
                            )}
                            {key.provider === 'anthropic' && key.auth_type === 'oauth_token' && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ backgroundColor: 'rgba(245, 158, 11, 0.2)', color: 'var(--app-accent-warning)' }}>
                                OAuth
                              </span>
                            )}
                            {validatingId === key.id && (
                              <span
                                className="px-1.5 py-0.5 rounded text-[10px] font-medium inline-flex items-center gap-1"
                                style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: 'var(--app-accent-primary)' }}
                              >
                                <span className="inline-block w-2.5 h-2.5 rounded-full animate-spin" style={{ borderWidth: '1.5px', borderColor: 'rgba(59, 130, 246, 0.3)', borderTopColor: 'var(--app-accent-primary)' }} />
                                Testing...
                              </span>
                            )}
                            {!validatingId || validatingId !== key.id ? validationResults[key.id] && (
                              <span
                                className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                                style={{
                                  backgroundColor: validationResults[key.id].valid ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                  color: validationResults[key.id].valid ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                                }}
                              >
                                {validationResults[key.id].valid ? 'VALID' : 'INVALID'}
                              </span>
                            ) : null}
                          </div>
                        </td>

                        {/* Key Hint */}
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs" style={{ color: 'var(--app-text-muted)' }}>
                            {key.api_key_hint}
                          </span>
                        </td>

                        {/* Model */}
                        <td className="px-4 py-3">
                          <span className="text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                            {key.model_name || '(no model)'}
                          </span>
                        </td>

                        {/* Status Toggle */}
                        <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                          <button
                            className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
                            style={{ backgroundColor: key.is_active ? 'var(--app-accent-success)' : 'var(--app-text-muted)', opacity: 0.85 }}
                            title={key.is_active ? 'Active \u2014 click to deactivate' : 'Inactive \u2014 click to activate'}
                            onClick={() => key.is_active ? handleDeactivate(key.id) : handleActivate(key.id)}
                          >
                            <span
                              className="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform"
                              style={{ transform: key.is_active ? 'translateX(18px)' : 'translateX(3px)' }}
                            />
                          </button>
                        </td>

                        {/* Base URL */}
                        <td className="px-4 py-3">
                          {key.base_url ? (
                            <span className="text-xs truncate block max-w-[200px]" style={{ color: 'var(--app-text-secondary)' }}>
                              {key.base_url}
                            </span>
                          ) : (
                            <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{'\u2014'}</span>
                          )}
                        </td>

                        {/* Kebab Menu */}
                        <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="relative inline-block" ref={openMenuId === key.id ? menuRef : undefined}>
                            <button
                              onClick={() => setOpenMenuId(openMenuId === key.id ? null : key.id)}
                              className="p-1.5 rounded-lg transition-colors hover:opacity-80"
                              style={{
                                backgroundColor: openMenuId === key.id ? 'var(--app-bg-tertiary)' : 'transparent',
                                color: 'var(--app-text-secondary)',
                              }}
                            >
                              <MoreHorizontal className="w-4 h-4" />
                            </button>

                            {openMenuId === key.id && (
                              <div
                                className={`absolute right-0 w-48 rounded-xl shadow-xl z-20 py-1 overflow-hidden ${isNearBottom ? 'bottom-full mb-1' : 'top-full mt-1'}`}
                                style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}
                              >
                                {/* Test Key */}
                                <button
                                  onClick={() => { setOpenMenuId(null); handleValidate(key.id) }}
                                  disabled={validatingId === key.id}
                                  className="w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors text-left disabled:opacity-50"
                                  style={{ color: 'var(--app-text-secondary)' }}
                                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                >
                                  <FlaskConical className="w-4 h-4" />
                                  {validatingId === key.id ? 'Testing...' : 'Test Key'}
                                </button>

                                {/* Set Default */}
                                {!key.is_default && (
                                  <button
                                    onClick={() => { setOpenMenuId(null); handleSetDefault(key.id) }}
                                    disabled={actionLoadingId === key.id}
                                    className="w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors text-left disabled:opacity-50"
                                    style={{ color: 'var(--app-accent-indigo)' }}
                                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                  >
                                    <Star className="w-4 h-4" />
                                    Set Default
                                  </button>
                                )}

                                {/* Divider */}
                                <div className="my-1" style={{ borderTop: '1px solid var(--app-border-default)' }} />

                                {/* Delete */}
                                <button
                                  onClick={() => { setOpenMenuId(null); handleDelete(key.id) }}
                                  disabled={actionLoadingId === key.id}
                                  className="w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors text-left disabled:opacity-50"
                                  style={{ color: 'var(--app-accent-error)' }}
                                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
                                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                >
                                  <Trash2 className="w-4 h-4" />
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                      )
                    })}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

          {/* Providers with no keys */}
          {PROVIDERS.filter(p => !keysByProvider.some(g => g.provider === p)).length > 0 && (
            <div className="px-4 py-3 text-sm" style={{ borderTop: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
              No keys configured for: {PROVIDERS.filter(p => !keysByProvider.some(g => g.provider === p)).map(p => providerDisplayName(p)).join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
