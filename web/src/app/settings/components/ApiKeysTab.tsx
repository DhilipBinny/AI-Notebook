'use client'

import { useState, useEffect, useCallback } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { apiKeys } from '@/lib/api'
import type { ApiKey, ProviderInfo } from '@/types'

const PROVIDER_ICONS: Record<string, string> = {
  openai: '>',
  anthropic: 'A',
  gemini: 'G',
  openai_compatible: 'O',
}

export default function ApiKeysTab() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  // Add key form
  const [showAddForm, setShowAddForm] = useState(false)
  const [addProvider, setAddProvider] = useState('')
  const [addLabel, setAddLabel] = useState('')
  const [addKeyValue, setAddKeyValue] = useState('')
  const [addBaseUrl, setAddBaseUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [validationResult, setValidationResult] = useState<{ id: string; valid: boolean; message: string } | null>(null)
  const [activatingId, setActivatingId] = useState<string | null>(null)

  // Edit key state
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editKeyValue, setEditKeyValue] = useState('')
  const [editBaseUrl, setEditBaseUrl] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      const [keysData, providersData] = await Promise.all([
        apiKeys.list(),
        apiKeys.getProviders(),
      ])
      setKeys(keysData)
      setProviders(providersData)
      // Default the add form provider to first available
      if (providersData.length > 0 && !addProvider) {
        setAddProvider(providersData[0].provider)
      }
    } catch {
      setError('Failed to load API keys')
    } finally {
      setIsLoading(false)
    }
  }, [addProvider])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const getKeysForProvider = (provider: string): ApiKey[] => {
    return keys.filter((k) => k.provider === provider)
  }

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addKeyValue.trim() && addProvider !== 'openai_compatible') return

    try {
      setIsSubmitting(true)
      await apiKeys.create({
        provider: addProvider,
        api_key: addKeyValue,
        label: addLabel || undefined,
        base_url: addBaseUrl || undefined,
      })
      setShowAddForm(false)
      setAddLabel('')
      setAddKeyValue('')
      setAddBaseUrl('')
      fetchData()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to add API key'
      setError(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteKey = async (keyId: string) => {
    try {
      await apiKeys.delete(keyId)
      fetchData()
    } catch {
      setError('Failed to remove API key')
    }
  }

  const handleValidateKey = async (keyId: string) => {
    try {
      setValidatingId(keyId)
      setValidationResult(null)
      const result = await apiKeys.validate(keyId)
      setValidationResult({ id: keyId, valid: result.valid, message: result.message })
      if (result.valid) {
        fetchData()
      }
    } catch {
      setValidationResult({ id: keyId, valid: false, message: 'Validation request failed' })
    } finally {
      setValidatingId(null)
    }
  }

  const handleToggleActive = async (key: ApiKey) => {
    try {
      setActivatingId(key.id)
      if (key.is_active) {
        await apiKeys.deactivate(key.id)
      } else {
        await apiKeys.activate(key.id)
      }
      fetchData()
    } catch {
      setError('Failed to update key status')
    } finally {
      setActivatingId(null)
    }
  }

  const startEditing = (key: ApiKey) => {
    setEditingId(key.id)
    setEditKeyValue('')
    setEditBaseUrl(key.base_url || '')
  }

  const handleUpdateKey = async (keyId: string) => {
    try {
      setIsUpdating(true)
      await apiKeys.update(keyId, {
        ...(editKeyValue ? { api_key: editKeyValue } : {}),
        base_url: editBaseUrl || undefined,
      })
      setEditingId(null)
      setEditKeyValue('')
      setEditBaseUrl('')
      fetchData()
    } catch {
      setError('Failed to update API key')
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <>
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text-primary)' }}>
          API Keys
        </h2>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
          style={{ background: 'var(--app-gradient-primary)' }}
        >
          {showAddForm ? 'Cancel' : 'Add Key'}
        </button>
      </div>

      {/* Add Key Form */}
      {showAddForm && (
        <div className="mb-4 p-5 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--app-text-primary)' }}>Add API Key</h3>
          <form onSubmit={handleAddKey} className="space-y-3">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Provider</label>
                <select
                  value={addProvider}
                  onChange={(e) => setAddProvider(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                >
                  {providers.map((p) => (
                    <option key={p.provider} value={p.provider}>{p.display_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Label (optional)</label>
                <input
                  type="text"
                  value={addLabel}
                  onChange={(e) => setAddLabel(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., Work, Personal"
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>
                  API Key{addProvider === 'openai_compatible' ? ' (optional)' : ''}
                </label>
                <input
                  type="password"
                  value={addKeyValue}
                  onChange={(e) => setAddKeyValue(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder={addProvider === 'openai_compatible' ? 'Optional for local servers' : 'sk-...'}
                  required={addProvider !== 'openai_compatible'}
                />
              </div>
            </div>
            {addProvider === 'openai_compatible' && (
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Base URL</label>
                <input
                  type="text"
                  value={addBaseUrl}
                  onChange={(e) => setAddBaseUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., http://localhost:11434/v1 or https://openrouter.ai/api/v1"
                  required
                />
              </div>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isSubmitting ? 'Saving...' : 'Save Key'}
              </button>
              <button
                type="button"
                onClick={() => { setShowAddForm(false); setAddLabel(''); setAddKeyValue(''); setAddBaseUrl('') }}
                className="px-4 py-2 rounded-lg text-sm"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Provider Sections */}
      {isLoading ? (
        <div className="p-8 text-center rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
          Loading...
        </div>
      ) : providers.length === 0 ? (
        <div className="p-8 text-center rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
          No providers available. Contact your administrator.
        </div>
      ) : (
        <div className="space-y-3">
          {providers.map((provider) => {
            const providerKeys = getKeysForProvider(provider.provider)

            return (
              <div
                key={provider.provider}
                className="rounded-xl overflow-hidden"
                style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}
              >
                {/* Provider Header */}
                <div className="flex items-center gap-3 px-5 py-3" style={{ borderBottom: providerKeys.length > 0 ? '1px solid var(--app-border-default)' : 'none' }}>
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold"
                    style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-primary)' }}
                  >
                    {PROVIDER_ICONS[provider.provider] || provider.provider[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                      {provider.display_name}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      {providerKeys.length === 0 ? 'No keys configured' : `${providerKeys.length} key${providerKeys.length !== 1 ? 's' : ''}`}
                    </p>
                  </div>
                </div>

                {/* Key List */}
                {providerKeys.length > 0 && (
                  <div className="divide-y" style={{ borderColor: 'var(--app-border-default)' }}>
                    {providerKeys.map((key) => {
                      const isValidating = validatingId === key.id
                      const isActivating = activatingId === key.id
                      const isEditing = editingId === key.id
                      const showResult = validationResult && validationResult.id === key.id

                      return (
                        <div
                          key={key.id}
                          className="px-5 py-3"
                          style={{ borderColor: 'var(--app-border-default)' }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-xs" style={{ color: 'var(--app-text-primary)' }}>
                                    {key.api_key_hint}
                                  </span>
                                  {key.label && (
                                    <span className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)' }}>
                                      {key.label}
                                    </span>
                                  )}
                                  {key.is_validated && (
                                    <span className="text-xs" style={{ color: 'var(--app-accent-success)' }}>
                                      Validated
                                    </span>
                                  )}
                                </div>
                                {key.base_url && (
                                  <p className="text-xs truncate" style={{ color: 'var(--app-text-muted)' }}>
                                    {key.base_url}
                                  </p>
                                )}
                                {showResult && (
                                  <p className="text-xs mt-0.5" style={{ color: validationResult.valid ? 'var(--app-accent-success)' : 'var(--app-accent-error)' }}>
                                    {validationResult.message}
                                  </p>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 flex-shrink-0">
                              {/* Active toggle switch */}
                              <button
                                onClick={() => handleToggleActive(key)}
                                disabled={isActivating}
                                className="flex-shrink-0 disabled:opacity-50"
                                title={key.is_active ? 'Active — click to deactivate' : 'Inactive — click to activate'}
                              >
                                <div
                                  className="relative w-8 h-4 rounded-full transition-colors cursor-pointer"
                                  style={{
                                    backgroundColor: key.is_active ? 'var(--app-accent-success)' : 'var(--app-bg-tertiary)',
                                    border: '1px solid var(--app-border-default)',
                                  }}
                                >
                                  <div
                                    className="absolute top-0.5 w-2.5 h-2.5 rounded-full transition-all"
                                    style={{
                                      backgroundColor: key.is_active ? '#fff' : 'var(--app-text-muted)',
                                      left: key.is_active ? '14px' : '2px',
                                    }}
                                  />
                                </div>
                              </button>
                              <button
                                onClick={() => handleValidateKey(key.id)}
                                disabled={isValidating}
                                className="px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-50"
                                style={{
                                  backgroundColor: 'var(--app-bg-tertiary)',
                                  color: 'var(--app-text-secondary)',
                                  border: '1px solid var(--app-border-default)',
                                }}
                              >
                                {isValidating ? 'Checking...' : 'Validate (beta)'}
                              </button>
                              <button
                                onClick={() => isEditing ? setEditingId(null) : startEditing(key)}
                                className="p-1.5 rounded-md transition-colors hover-text-primary"
                                style={{ color: isEditing ? 'var(--app-text-primary)' : 'var(--app-text-muted)' }}
                                title={isEditing ? 'Cancel editing' : 'Edit key'}
                              >
                                <Pencil size={14} />
                              </button>
                              <button
                                onClick={() => handleDeleteKey(key.id)}
                                className="p-1.5 rounded-md transition-colors hover-text-error"
                                style={{ color: 'var(--app-text-muted)' }}
                                title="Remove key"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>

                          {/* Inline Edit Form */}
                          {isEditing && (
                            <div className="mt-3 ml-7 p-3 rounded-lg space-y-2" style={{ backgroundColor: 'var(--app-bg-tertiary)' }}>
                              <div className="grid grid-cols-2 gap-3">
                                <div>
                                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>New API Key (leave blank to keep current)</label>
                                  <input
                                    type="password"
                                    value={editKeyValue}
                                    onChange={(e) => setEditKeyValue(e.target.value)}
                                    className="w-full px-3 py-1.5 rounded-lg text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                                    placeholder={key.api_key_hint}
                                  />
                                </div>
                                {key.provider === 'openai_compatible' && (
                                  <div>
                                    <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Base URL</label>
                                    <input
                                      type="text"
                                      value={editBaseUrl}
                                      onChange={(e) => setEditBaseUrl(e.target.value)}
                                      className="w-full px-3 py-1.5 rounded-lg text-xs focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
                                      style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                                      placeholder="http://localhost:11434/v1"
                                    />
                                  </div>
                                )}
                              </div>
                              <div className="flex gap-2">
                                <button
                                  onClick={() => handleUpdateKey(key.id)}
                                  disabled={isUpdating || (!editKeyValue && !editBaseUrl && editBaseUrl === (key.base_url || ''))}
                                  className="px-3 py-1.5 rounded-lg text-xs text-white disabled:opacity-50"
                                  style={{ background: 'var(--app-gradient-primary)' }}
                                >
                                  {isUpdating ? 'Saving...' : 'Save'}
                                </button>
                                <button
                                  onClick={() => setEditingId(null)}
                                  className="px-3 py-1.5 rounded-lg text-xs"
                                  style={{ color: 'var(--app-text-muted)' }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
