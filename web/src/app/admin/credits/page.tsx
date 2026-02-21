'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { admin, credits } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { LLMPricing, CreditBalance } from '@/types'

export default function AdminCreditsPage() {
  // Adjust credits form
  const [userId, setUserId] = useState('')
  const [amountCents, setAmountCents] = useState('')
  const [reason, setReason] = useState('')
  const [adjustResult, setAdjustResult] = useState<CreditBalance | null>(null)
  const [adjustError, setAdjustError] = useState('')
  const [isAdjusting, setIsAdjusting] = useState(false)

  // Pricing table
  const [pricing, setPricing] = useState<LLMPricing[]>([])
  const [isLoadingPricing, setIsLoadingPricing] = useState(true)
  const [pricingError, setPricingError] = useState('')

  // Inline editing
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState({
    input_cost_per_1m_cents: 0,
    output_cost_per_1m_cents: 0,
    margin_multiplier: 1,
    is_active: true,
  })
  const [isSavingPricing, setIsSavingPricing] = useState(false)

  const router = useRouter()
  const user = useAuthStore((state) => state.user)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      router.push('/dashboard')
    }
  }, [user, router])

  const fetchPricing = useCallback(async () => {
    try {
      setIsLoadingPricing(true)
      const data = await credits.getPricing()
      setPricing(data)
    } catch {
      setPricingError('Failed to load pricing')
    } finally {
      setIsLoadingPricing(false)
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchPricing()
    }
  }, [user, fetchPricing])

  const handleAdjustCredits = async (e: React.FormEvent) => {
    e.preventDefault()
    setAdjustError('')
    setAdjustResult(null)

    const amount = parseInt(amountCents, 10)
    if (!userId.trim()) {
      setAdjustError('User ID is required')
      return
    }
    if (isNaN(amount) || amount === 0) {
      setAdjustError('Amount must be a non-zero integer')
      return
    }
    if (!reason.trim()) {
      setAdjustError('Reason is required')
      return
    }

    try {
      setIsAdjusting(true)
      const result = await admin.credits.adjust({
        user_id: userId.trim(),
        amount_cents: amount,
        reason: reason.trim(),
      })
      setAdjustResult(result)
      setUserId('')
      setAmountCents('')
      setReason('')
    } catch {
      setAdjustError('Failed to adjust credits')
    } finally {
      setIsAdjusting(false)
    }
  }

  const startEditing = (row: LLMPricing) => {
    setEditingId(row.id)
    setEditForm({
      input_cost_per_1m_cents: row.input_cost_per_1m_cents,
      output_cost_per_1m_cents: row.output_cost_per_1m_cents,
      margin_multiplier: row.margin_multiplier,
      is_active: row.is_active,
    })
  }

  const cancelEditing = () => {
    setEditingId(null)
  }

  const handleSavePricing = async (row: LLMPricing) => {
    try {
      setIsSavingPricing(true)
      await admin.credits.updatePricing({
        provider: row.provider,
        model: row.model,
        input_cost_per_1m_cents: editForm.input_cost_per_1m_cents,
        output_cost_per_1m_cents: editForm.output_cost_per_1m_cents,
        margin_multiplier: editForm.margin_multiplier,
        is_active: editForm.is_active,
      })
      setEditingId(null)
      fetchPricing()
    } catch {
      setPricingError('Failed to update pricing')
    } finally {
      setIsSavingPricing(false)
    }
  }

  if (!user?.is_admin) {
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
              Credits & LLM Pricing
            </h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Adjust user credits and manage LLM pricing configuration
            </p>
          </div>
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

        {/* Adjust User Credits */}
        <div className="mb-8 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h2 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>
            Adjust User Credits
          </h2>

          {adjustError && (
            <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
              {adjustError}
              <button onClick={() => setAdjustError('')} className="ml-2 underline">dismiss</button>
            </div>
          )}

          {adjustResult && (
            <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
              Credits adjusted. New balance: ${adjustResult.balance_dollars.toFixed(2)} ({adjustResult.balance_cents} cents)
              <button onClick={() => setAdjustResult(null)} className="ml-2 underline">dismiss</button>
            </div>
          )}

          <form onSubmit={handleAdjustCredits} className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>User ID</label>
                <input
                  type="text"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="user-uuid"
                  required
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Amount (cents)</label>
                <input
                  type="number"
                  value={amountCents}
                  onChange={(e) => setAmountCents(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="positive to add, negative to deduct"
                  required
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Reason</label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., Welcome bonus"
                  required
                />
              </div>
            </div>
            <div>
              <button
                type="submit"
                disabled={isAdjusting}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isAdjusting ? 'Adjusting...' : 'Adjust Credits'}
              </button>
            </div>
          </form>
        </div>

        {/* LLM Pricing Table */}
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <div className="px-6 py-4" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
            <h2 className="text-lg font-medium" style={{ color: 'var(--app-text-primary)' }}>
              LLM Pricing
            </h2>
            <p className="mt-1 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Active pricing configuration for all LLM providers
            </p>
          </div>

          {pricingError && (
            <div className="mx-6 mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
              {pricingError}
              <button onClick={() => setPricingError('')} className="ml-2 underline">dismiss</button>
            </div>
          )}

          {isLoadingPricing ? (
            <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
          ) : pricing.length === 0 ? (
            <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>No pricing configured</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Provider</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Model</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Input Cost/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Output Cost/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Margin</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Active</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pricing.map((row) => (
                  <tr key={row.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    {editingId === row.id ? (
                      <>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.provider}</td>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.model}</td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.input_cost_per_1m_cents}
                            onChange={(e) => setEditForm({ ...editForm, input_cost_per_1m_cents: parseFloat(e.target.value) || 0 })}
                            className="w-24 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.output_cost_per_1m_cents}
                            onChange={(e) => setEditForm({ ...editForm, output_cost_per_1m_cents: parseFloat(e.target.value) || 0 })}
                            className="w-24 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.margin_multiplier}
                            onChange={(e) => setEditForm({ ...editForm, margin_multiplier: parseFloat(e.target.value) || 1 })}
                            className="w-20 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <input
                            type="checkbox"
                            checked={editForm.is_active}
                            onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                            className="rounded"
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => handleSavePricing(row)}
                              disabled={isSavingPricing}
                              className="px-2 py-1 rounded text-xs text-white transition-colors disabled:opacity-50"
                              style={{ background: 'var(--app-gradient-primary)' }}
                            >
                              {isSavingPricing ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              onClick={cancelEditing}
                              className="px-2 py-1 rounded text-xs transition-colors"
                              style={{ color: 'var(--app-text-muted)' }}
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.provider}</td>
                        <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--app-text-primary)' }}>{row.model}</td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--app-text-secondary)' }}>
                          {row.input_cost_per_1m_cents.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--app-text-secondary)' }}>
                          {row.output_cost_per_1m_cents.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--app-text-secondary)' }}>
                          {row.margin_multiplier.toFixed(2)}x
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className="px-2 py-0.5 rounded text-xs font-medium"
                            style={{ color: row.is_active ? '#10b981' : 'var(--app-text-muted)' }}
                          >
                            {row.is_active ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => startEditing(row)}
                            className="px-2 py-1 rounded text-xs transition-colors"
                            style={{
                              backgroundColor: 'var(--app-bg-tertiary)',
                              color: 'var(--app-text-secondary)',
                              border: '1px solid var(--app-border-default)',
                            }}
                          >
                            Edit
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
