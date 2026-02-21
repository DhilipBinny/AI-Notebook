'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { admin } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { Invitation } from '@/types'

export default function AdminInvitationsPage() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showBatch, setShowBatch] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Create form
  const [newEmail, setNewEmail] = useState('')
  const [newMaxUses, setNewMaxUses] = useState(1)
  const [newNote, setNewNote] = useState('')

  // Batch form
  const [batchEmails, setBatchEmails] = useState('')
  const [batchNote, setBatchNote] = useState('')

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

  const fetchInvitations = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await admin.invitations.list()
      setInvitations(data)
    } catch {
      setError('Failed to load invitations')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchInvitations()
    }
  }, [user, fetchInvitations])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await admin.invitations.create({
        email: newEmail || undefined,
        max_uses: newMaxUses,
        note: newNote || undefined,
      })
      setShowCreate(false)
      setNewEmail('')
      setNewMaxUses(1)
      setNewNote('')
      fetchInvitations()
    } catch {
      setError('Failed to create invitation')
    }
  }

  const handleBatchCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const emails = batchEmails.split(/[\n,;]+/).map(e => e.trim()).filter(Boolean)
    if (emails.length === 0) return

    try {
      await admin.invitations.batchCreate({
        emails,
        note: batchNote || undefined,
      })
      setShowBatch(false)
      setBatchEmails('')
      setBatchNote('')
      fetchInvitations()
    } catch {
      setError('Failed to create invitations')
    }
  }

  const handleDeactivate = async (id: string) => {
    try {
      await admin.invitations.deactivate(id)
      fetchInvitations()
    } catch {
      setError('Failed to deactivate invitation')
    }
  }

  const copyInviteLink = (code: string, id: string) => {
    const url = `${window.location.origin}/auth/register?invite=${code}`
    navigator.clipboard.writeText(url)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
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
              Invitation Management
            </h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Create and manage invitation codes for user registration
            </p>
          </div>
          <div className="flex gap-3">
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
            <button
              onClick={() => { setShowBatch(true); setShowCreate(false) }}
              className="px-4 py-2 rounded-lg text-sm transition-colors"
              style={{
                backgroundColor: 'var(--app-bg-tertiary)',
                color: 'var(--app-text-primary)',
                border: '1px solid var(--app-border-default)',
              }}
            >
              Batch Create
            </button>
            <button
              onClick={() => { setShowCreate(true); setShowBatch(false) }}
              className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
              style={{ background: 'var(--app-gradient-primary)' }}
            >
              Create Invitation
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
          </div>
        )}

        {/* Create Form */}
        {showCreate && (
          <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Create Invitation</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Email (optional - lock to email)</label>
                  <input
                    type="email"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                    placeholder="user@example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Max uses</label>
                  <input
                    type="number"
                    value={newMaxUses}
                    onChange={(e) => setNewMaxUses(parseInt(e.target.value) || 1)}
                    min={1}
                    max={1000}
                    className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Note (optional)</label>
                <input
                  type="text"
                  value={newNote}
                  onChange={(e) => setNewNote(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., AGAI-101 Batch 1"
                />
              </div>
              <div className="flex gap-3">
                <button type="submit" className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: 'var(--app-gradient-primary)' }}>Create</button>
                <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Batch Create Form */}
        {showBatch && (
          <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Batch Create Invitations</h3>
            <form onSubmit={handleBatchCreate} className="space-y-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Emails (one per line, or comma-separated)</label>
                <textarea
                  value={batchEmails}
                  onChange={(e) => setBatchEmails(e.target.value)}
                  rows={5}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none resize-y"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder={"student1@email.com\nstudent2@email.com\nstudent3@email.com"}
                />
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Note (optional)</label>
                <input
                  type="text"
                  value={batchNote}
                  onChange={(e) => setBatchNote(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., AGAI-101 Batch 1"
                />
              </div>
              <div className="flex gap-3">
                <button type="submit" className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: 'var(--app-gradient-primary)' }}>Create All</button>
                <button type="button" onClick={() => setShowBatch(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* Invitations Table */}
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          {isLoading ? (
            <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
          ) : invitations.length === 0 ? (
            <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>No invitations yet</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Code</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Email</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Usage</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Status</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Note</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Created</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {invitations.map((inv) => {
                  const isExpired = inv.expires_at && new Date(inv.expires_at) < new Date()
                  const isFull = inv.used_count >= inv.max_uses
                  const statusLabel = !inv.is_active ? 'Deactivated' : isExpired ? 'Expired' : isFull ? 'Fully Used' : 'Active'
                  const statusColor = !inv.is_active || isExpired ? 'var(--app-text-muted)' : isFull ? '#f59e0b' : '#10b981'

                  return (
                    <tr key={inv.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                      <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--app-text-primary)' }}>
                        {inv.code.slice(0, 12)}...
                      </td>
                      <td className="px-4 py-3" style={{ color: 'var(--app-text-secondary)' }}>
                        {inv.email || '-'}
                      </td>
                      <td className="px-4 py-3" style={{ color: 'var(--app-text-secondary)' }}>
                        {inv.used_count}/{inv.max_uses}
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ color: statusColor }}>
                          {statusLabel}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                        {inv.note || '-'}
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                        {new Date(inv.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => copyInviteLink(inv.code, inv.id)}
                            className="px-2 py-1 rounded text-xs transition-colors"
                            style={{
                              backgroundColor: 'var(--app-bg-tertiary)',
                              color: copiedId === inv.id ? '#10b981' : 'var(--app-text-secondary)',
                              border: '1px solid var(--app-border-default)',
                            }}
                          >
                            {copiedId === inv.id ? 'Copied!' : 'Copy Link'}
                          </button>
                          {inv.is_active && !isFull && (
                            <button
                              onClick={() => handleDeactivate(inv.id)}
                              className="px-2 py-1 rounded text-xs transition-colors"
                              style={{ color: 'var(--app-accent-error)' }}
                            >
                              Deactivate
                            </button>
                          )}
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
    </div>
  )
}
