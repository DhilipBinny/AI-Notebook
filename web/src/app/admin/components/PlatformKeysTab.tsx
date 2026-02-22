'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin, models as modelsApi } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
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
  const [customModelName, setCustomModelName] = useState('')
  const [showCustomModelInput, setShowCustomModelInput] = useState(false)
  const [isCreating, setIsCreating] = useState(false)

  // Edit form
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({
    label: '',
    api_key: '',
    auth_type: 'api_key' as 'api_key' | 'oauth_token',
    model_name: '',
    base_url: '',
  })
  const [editCustomModelName, setEditCustomModelName] = useState('')
  const [showEditCustomModelInput, setShowEditCustomModelInput] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Validation
  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [validationResults, setValidationResults] = useState<Record<string, { valid: boolean; error?: string }>>({})

  // Action loading
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

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
      // Pre-fetch models for all providers
      PROVIDERS.forEach(p => fetchModelsForProvider(p))
    }
  }, [user, fetchKeys, fetchModelsForProvider])

  // When provider changes in create form, update model selection
  useEffect(() => {
    const models = providerModels[createForm.provider]
    if (models && models.length > 0 && !showCustomModelInput) {
      setCreateForm(prev => ({ ...prev, model_name: models[0].model_id }))
    }
  }, [createForm.provider, providerModels, showCustomModelInput])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const modelName = showCustomModelInput ? customModelName : createForm.model_name

    if (!modelName) {
      setError('Model name is required')
      return
    }

    try {
      setIsCreating(true)
      const result = await admin.platformKeys.create({
        provider: createForm.provider,
        label: createForm.label,
        api_key: createForm.api_key,
        auth_type: createForm.provider === 'anthropic' ? createForm.auth_type : undefined,
        model_name: modelName,
        base_url: createForm.base_url || undefined,
      })
      setCreateForm({ provider: 'gemini', label: '', api_key: '', auth_type: 'api_key', model_name: '', base_url: '' })
      setCustomModelName('')
      setShowCustomModelInput(false)
      setShowCreate(false)

      if ((result as PlatformKey & { model_created?: boolean }).model_created) {
        setSuccessMsg('Platform key created. New model auto-registered with $0 pricing — set pricing in Model Registry.')
      } else {
        setSuccessMsg('Platform key created')
      }
      fetchKeys()
      // Refresh models in case a new custom model was auto-created
      fetchModelsForProvider(createForm.provider)
      setTimeout(() => setSuccessMsg(''), 5000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create platform key'
      setError(errorMsg)
    } finally {
      setIsCreating(false)
    }
  }

  const startEditing = (key: PlatformKey) => {
    setEditingId(key.id)
    setEditForm({
      label: key.label,
      api_key: '',
      auth_type: key.auth_type || 'api_key',
      model_name: key.model_name || '',
      base_url: key.base_url || '',
    })
    setEditCustomModelName('')
    setShowEditCustomModelInput(false)
    // Ensure models are loaded for this provider
    fetchModelsForProvider(key.provider)
  }

  const handleSave = async (keyId: string) => {
    try {
      setIsSaving(true)
      const updateData: { label?: string; api_key?: string; auth_type?: string; model_name?: string; base_url?: string } = {}
      if (editForm.label) updateData.label = editForm.label
      if (editForm.api_key) updateData.api_key = editForm.api_key
      // Find the key being edited to check if it's anthropic
      const editingKey = keys.find(k => k.id === keyId)
      if (editingKey?.provider === 'anthropic') updateData.auth_type = editForm.auth_type

      const modelName = showEditCustomModelInput ? editCustomModelName : editForm.model_name
      if (modelName !== undefined) updateData.model_name = modelName
      if (editForm.base_url !== undefined) updateData.base_url = editForm.base_url

      await admin.platformKeys.update(keyId, updateData)
      setEditingId(null)
      setSuccessMsg('Key updated')
      fetchKeys()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update key'
      setError(errorMsg)
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

  const isOpenAICompatible = (provider: string) => provider === 'openai_compatible'

  const renderModelSelect = (
    provider: string,
    value: string,
    onChange: (val: string) => void,
    showCustom: boolean,
    setShowCustom: (v: boolean) => void,
    customValue: string,
    onCustomChange: (v: string) => void,
  ) => {
    const availableModels = providerModels[provider] || []

    if (showCustom) {
      return (
        <div className="flex gap-2">
          <input
            type="text"
            value={customValue}
            onChange={(e) => onCustomChange(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg text-sm focus:outline-none"
            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
            placeholder="e.g., deepseek-r1:7b"
            required
          />
          <button
            type="button"
            onClick={() => { setShowCustom(false); onCustomChange('') }}
            className="px-2 py-1 rounded text-xs"
            style={{ color: 'var(--app-text-muted)' }}
          >
            Cancel
          </button>
        </div>
      )
    }

    return (
      <div className="flex gap-2">
        <select
          value={value}
          onChange={(e) => {
            if (e.target.value === '__custom__') {
              setShowCustom(true)
            } else {
              onChange(e.target.value)
            }
          }}
          className="flex-1 px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          required
        >
          {availableModels.map(m => (
            <option key={m.model_id} value={m.model_id}>{m.display_name} ({m.model_id})</option>
          ))}
          {isOpenAICompatible(provider) && (
            <option value="__custom__">+ Add Custom Model...</option>
          )}
        </select>
      </div>
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
                    setCreateForm({ ...createForm, provider, model_name: '', base_url: '', auth_type: 'api_key' })
                    setShowCustomModelInput(false)
                    setCustomModelName('')
                    fetchModelsForProvider(provider)
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
                  showCustomModelInput,
                  setShowCustomModelInput,
                  customModelName,
                  setCustomModelName,
                )}
              </div>
            </div>
            {createForm.provider === 'anthropic' && (
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Auth Type</label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="create_auth_type"
                      value="api_key"
                      checked={createForm.auth_type === 'api_key'}
                      onChange={() => setCreateForm({ ...createForm, auth_type: 'api_key' })}
                      className="accent-indigo-500"
                    />
                    <span className="text-sm" style={{ color: 'var(--app-text-primary)' }}>API Key</span>
                    <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>(sk-ant-api03-...)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="create_auth_type"
                      value="oauth_token"
                      checked={createForm.auth_type === 'oauth_token'}
                      onChange={() => setCreateForm({ ...createForm, auth_type: 'oauth_token' })}
                      className="accent-indigo-500"
                    />
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
                            <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>
                              New {key.provider === 'anthropic' && editForm.auth_type === 'oauth_token' ? 'OAuth Token' : 'API Key'} (leave empty to keep)
                            </label>
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
                            <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Model</label>
                            {renderModelSelect(
                              key.provider,
                              editForm.model_name,
                              (val) => setEditForm({ ...editForm, model_name: val }),
                              showEditCustomModelInput,
                              setShowEditCustomModelInput,
                              editCustomModelName,
                              setEditCustomModelName,
                            )}
                          </div>
                        </div>
                        {key.provider === 'anthropic' && (
                          <div>
                            <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Auth Type</label>
                            <div className="flex gap-3">
                              <label className="flex items-center gap-1.5 cursor-pointer">
                                <input
                                  type="radio"
                                  name={`edit_auth_type_${key.id}`}
                                  value="api_key"
                                  checked={editForm.auth_type === 'api_key'}
                                  onChange={() => setEditForm({ ...editForm, auth_type: 'api_key' })}
                                  className="accent-indigo-500"
                                />
                                <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>API Key</span>
                              </label>
                              <label className="flex items-center gap-1.5 cursor-pointer">
                                <input
                                  type="radio"
                                  name={`edit_auth_type_${key.id}`}
                                  value="oauth_token"
                                  checked={editForm.auth_type === 'oauth_token'}
                                  onChange={() => setEditForm({ ...editForm, auth_type: 'oauth_token' })}
                                  className="accent-indigo-500"
                                />
                                <span className="text-xs" style={{ color: 'var(--app-text-primary)' }}>OAuth Token</span>
                              </label>
                            </div>
                          </div>
                        )}
                        {isOpenAICompatible(key.provider) && (
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
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
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
                              {key.provider === 'anthropic' && key.auth_type === 'oauth_token' && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ backgroundColor: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b' }}>
                                  OAuth
                                </span>
                              )}
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
  )
}
