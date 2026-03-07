'use client'

import { useState, useEffect, useCallback } from 'react'
import { credits } from '@/lib/api'
import type { CreditBalance, UsageRecord } from '@/types'

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'openai_compatible', label: 'OpenAI Compatible' },
]

export default function UsageTab() {
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [usageRecords, setUsageRecords] = useState<UsageRecord[]>([])
  const [usageTotal, setUsageTotal] = useState(0)
  const [usagePage, setUsagePage] = useState(1)

  const [isLoadingBalance, setIsLoadingBalance] = useState(true)
  const [isLoadingUsage, setIsLoadingUsage] = useState(true)
  const [error, setError] = useState('')

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
    fetchBalance()
    fetchUsage(1)
  }, [fetchBalance, fetchUsage])

  const getProviderLabel = (provider: string) => {
    return PROVIDERS.find((p) => p.value === provider)?.label || provider
  }

  const pageSize = 20
  const totalPages = Math.ceil(usageTotal / pageSize)
  const startIdx = (usagePage - 1) * pageSize + 1
  const endIdx = Math.min(usagePage * pageSize, usageTotal)

  return (
    <>
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}

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
                        <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ color: 'var(--app-accent-success)', backgroundColor: 'var(--app-alert-success-bg)' }}>
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
            <div className="px-4 py-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--app-border-default)' }}>
              <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                Showing {startIdx}-{endIdx} of {usageTotal}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => fetchUsage(Math.max(1, usagePage - 1))}
                  disabled={usagePage <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs disabled:opacity-30"
                  style={{
                    backgroundColor: 'var(--app-bg-tertiary)',
                    color: 'var(--app-text-secondary)',
                    border: '1px solid var(--app-border-default)',
                  }}
                >
                  Prev
                </button>
                <span className="px-3 py-1.5 text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                  Page {usagePage} of {totalPages || 1}
                </span>
                <button
                  onClick={() => fetchUsage(Math.min(totalPages, usagePage + 1))}
                  disabled={usagePage >= totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs disabled:opacity-30"
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
          </>
        )}
      </div>
    </>
  )
}
