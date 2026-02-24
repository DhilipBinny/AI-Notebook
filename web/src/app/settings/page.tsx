'use client'

import { useState, useEffect, useCallback } from 'react'
import { apiKeys, credits } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import AppHeader from '@/components/AppHeader'
import type { ApiKey, CreditBalance, UsageRecord } from '@/types'

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI', icon: '>' },
  { value: 'anthropic', label: 'Anthropic', icon: 'A' },
  { value: 'gemini', label: 'Gemini', icon: 'G' },
  { value: 'openai_compatible', label: 'OpenAI Compatible', icon: 'O' },
]

export default function SettingsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([])
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [usageRecords, setUsageRecords] = useState<UsageRecord[]>([])
  const [usageTotal, setUsageTotal] = useState(0)
  const [usagePage, setUsagePage] = useState(1)

  const [isLoadingKeys, setIsLoadingKeys] = useState(true)
  const [isLoadingBalance, setIsLoadingBalance] = useState(true)
  const [isLoadingUsage, setIsLoadingUsage] = useState(true)
  const [error, setError] = useState('')

  const [showAddForm, setShowAddForm] = useState(false)
  const [addProvider, setAddProvider] = useState('openai')
  const [addKeyValue, setAddKeyValue] = useState('')
  const [addBaseUrl, setAddBaseUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [validatingId, setValidatingId] = useState<string | null>(null)
  const [validationResult, setValidationResult] = useState<{ id: string; valid: boolean; message: string } | null>(null)

  const user = useAuthStore((state) => state.user)

  const fetchKeys = useCallback(async () => {
    try {
      setIsLoadingKeys(true)
      const data = await apiKeys.list()
      setKeys(data)
    } catch {
      setError('Failed to load API keys')
    } finally {
      setIsLoadingKeys(false)
    }
  }, [])

  const fetchBalance = useCallback(async () => {
    try {
      setIsLoadingBalance(true)
      const data = await credits.getBalance()
      setBalance(data)
    } catch {
      setError('Failed to load credit balance')
    } finally {
      setIsLoadingBalance(false)
    }
  }, [])

  const fetchUsage = useCallback(async (page: number) => {
    try {
      setIsLoadingUsage(true)
      const data = await credits.getUsageHistory(page, 20)
      setUsageRecords(data.records)
      setUsageTotal(data.total)
      setUsagePage(data.page)
    } catch {
      setError('Failed to load usage history')
    } finally {
      setIsLoadingUsage(false)
    }
  }, [])

  useEffect(() => {
    fetchKeys()
    fetchBalance()
    fetchUsage(1)
  }, [fetchKeys, fetchBalance, fetchUsage])

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!addKeyValue.trim() && addProvider !== 'openai_compatible') return

    try {
      setIsSubmitting(true)
      await apiKeys.create({
        provider: addProvider,
        api_key: addKeyValue,
        base_url: addBaseUrl || undefined,
      })
      setShowAddForm(false)
      setAddProvider('openai')
      setAddKeyValue('')
      setAddBaseUrl('')
      fetchKeys()
    } catch {
      setError('Failed to add API key')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteKey = async (keyId: string) => {
    try {
      await apiKeys.delete(keyId)
      fetchKeys()
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
        fetchKeys()
      }
    } catch {
      setValidationResult({ id: keyId, valid: false, message: 'Validation request failed' })
    } finally {
      setValidatingId(null)
    }
  }

  const getProviderLabel = (provider: string) => {
    return PROVIDERS.find((p) => p.value === provider)?.label || provider
  }

  const getProviderIcon = (provider: string) => {
    return PROVIDERS.find((p) => p.value === provider)?.icon || '?'
  }

  const getKeyForProvider = (provider: string) => {
    return keys.find((k) => k.provider === provider)
  }

  const totalPages = Math.ceil(usageTotal / 20)

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
      <AppHeader title="Settings" subtitle="API keys & usage" />

      <div className="px-6 py-6">

        {error && (
          <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
          </div>
        )}

        {/* ========== API Keys Management ========== */}
        <div className="mb-8">
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
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Provider</label>
                    <select
                      value={addProvider}
                      onChange={(e) => setAddProvider(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                      style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>
                      API Key{addProvider === 'openai_compatible' ? ' (optional)' : ''}
                    </label>
                    <input
                      type="password"
                      value={addKeyValue}
                      onChange={(e) => setAddKeyValue(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
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
                      className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
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
                    onClick={() => { setShowAddForm(false); setAddKeyValue(''); setAddBaseUrl('') }}
                    className="px-4 py-2 rounded-lg text-sm"
                    style={{ color: 'var(--app-text-muted)' }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Provider Cards */}
          <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            {isLoadingKeys ? (
              <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'var(--app-border-default)' }}>
                {PROVIDERS.map((provider) => {
                  const key = getKeyForProvider(provider.value)
                  const isValidating = validatingId === key?.id
                  const showResult = validationResult && validationResult.id === key?.id

                  return (
                    <div
                      key={provider.value}
                      className="flex items-center justify-between px-5 py-4"
                      style={{ borderBottom: '1px solid var(--app-border-default)' }}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center text-sm font-bold"
                          style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-primary)' }}
                        >
                          {provider.icon}
                        </div>
                        <div>
                          <p className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                            {provider.label}
                          </p>
                          <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                            {key ? (
                              <>
                                <span className="font-mono">{key.api_key_hint}</span>
                                {key.is_validated && (
                                  <span className="ml-2" style={{ color: 'var(--app-accent-success)' }}>Validated</span>
                                )}
                              </>
                            ) : (
                              'Not configured'
                            )}
                          </p>
                          {showResult && (
                            <p className="text-xs mt-0.5" style={{ color: validationResult.valid ? 'var(--app-accent-success)' : 'var(--app-accent-error)' }}>
                              {validationResult.message}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {key ? (
                          <>
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
                              {isValidating ? 'Checking...' : 'Validate'}
                            </button>
                            <button
                              onClick={() => handleDeleteKey(key.id)}
                              className="px-3 py-1.5 rounded-lg text-xs transition-colors"
                              style={{ color: 'var(--app-accent-error)' }}
                            >
                              Remove
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => { setAddProvider(provider.value); setShowAddForm(true) }}
                            className="px-3 py-1.5 rounded-lg text-xs transition-colors"
                            style={{
                              backgroundColor: 'var(--app-bg-tertiary)',
                              color: 'var(--app-text-secondary)',
                              border: '1px solid var(--app-border-default)',
                            }}
                          >
                            Add Key
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* ========== Usage & Credits ========== */}
        <div>
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--app-text-primary)' }}>
            Usage &amp; Credits
          </h2>

          {/* Credit Balance */}
          <div className="mb-4 p-5 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            {isLoadingBalance ? (
              <div className="text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
            ) : balance ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm" style={{ color: 'var(--app-text-secondary)' }}>Credit Balance</p>
                  <p className="text-3xl font-bold mt-1" style={{ color: 'var(--app-text-primary)' }}>
                    ${balance.balance_dollars.toFixed(2)}
                  </p>
                </div>
                <div className="text-right text-xs space-y-1" style={{ color: 'var(--app-text-muted)' }}>
                  <p>Total deposited: ${(balance.total_deposited_cents / 100).toFixed(2)}</p>
                  <p>Total consumed: ${(balance.total_consumed_cents / 100).toFixed(2)}</p>
                  {balance.last_charged_at && (
                    <p>Last charge: {new Date(balance.last_charged_at).toLocaleDateString()}</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center" style={{ color: 'var(--app-text-muted)' }}>No balance data</div>
            )}
          </div>

          {/* Usage History Table */}
          <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            {isLoadingUsage ? (
              <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
            ) : usageRecords.length === 0 ? (
              <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>No usage records yet</div>
            ) : (
              <>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                      <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Date</th>
                      <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Provider</th>
                      <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Model</th>
                      <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Tokens</th>
                      <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Cost</th>
                      <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Key</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageRecords.map((record) => (
                      <tr key={record.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                        <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                          {new Date(record.created_at).toLocaleDateString()}{' '}
                          {new Date(record.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-secondary)' }}>
                          {getProviderLabel(record.provider)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--app-text-primary)' }}>
                          {record.model}
                        </td>
                        <td className="px-4 py-3 text-right text-xs" style={{ color: 'var(--app-text-muted)' }}>
                          {(record.input_tokens + record.output_tokens).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-right text-xs" style={{ color: 'var(--app-text-primary)' }}>
                          ${(record.cost_cents / 100).toFixed(4)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {record.is_own_key ? (
                            <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ color: 'var(--app-accent-success)', backgroundColor: 'rgba(74, 222, 128, 0.1)' }}>
                              own key
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-xs" style={{ color: 'var(--app-text-muted)' }}>
                              platform
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                    <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      Page {usagePage} of {totalPages} ({usageTotal} records)
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => fetchUsage(usagePage - 1)}
                        disabled={usagePage <= 1}
                        className="px-3 py-1 rounded text-xs transition-colors disabled:opacity-30"
                        style={{
                          backgroundColor: 'var(--app-bg-tertiary)',
                          color: 'var(--app-text-secondary)',
                          border: '1px solid var(--app-border-default)',
                        }}
                      >
                        Previous
                      </button>
                      <button
                        onClick={() => fetchUsage(usagePage + 1)}
                        disabled={usagePage >= totalPages}
                        className="px-3 py-1 rounded text-xs transition-colors disabled:opacity-30"
                        style={{
                          backgroundColor: 'var(--app-bg-tertiary)',
                          color: 'var(--app-text-secondary)',
                          border: '1px solid var(--app-border-default)',
                        }}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
