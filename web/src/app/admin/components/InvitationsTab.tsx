'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { admin } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Trash2 } from 'lucide-react'
import type { Invitation } from '@/types'

export default function InvitationsTab() {
  const [invitations, setInvitations] = useState<Invitation[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showBatch, setShowBatch] = useState(false)

  // Search
  const [search, setSearch] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Create form
  const [newEmail, setNewEmail] = useState('')
  const [newNote, setNewNote] = useState('')

  // Batch form
  const [batchEmails, setBatchEmails] = useState('')
  const [batchNote, setBatchNote] = useState('')

  const user = useAuthStore((state) => state.user)

  const fetchInvitations = useCallback(async () => {
    try {
      setIsLoading(true)
      const params: Record<string, string | number | boolean> = { page, page_size: pageSize }
      if (search) params.search = search
      const data = await admin.invitations.list(params as Parameters<typeof admin.invitations.list>[0])
      setInvitations(data.invitations)
      setTotal(data.total)
    } catch {
      setError('Failed to load invitations')
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, search])

  const handleSearchChange = (value: string) => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setSearch(value)
      setPage(1)
    }, 300)
  }

  useEffect(() => {
    if (user?.is_admin) {
      fetchInvitations()
    }
  }, [user, fetchInvitations])

  const showSuccess = (msg: string) => {
    setSuccess(msg)
    setTimeout(() => setSuccess(''), 3000)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await admin.invitations.create({
        email: newEmail || undefined,
        note: newNote || undefined,
        base_url: window.location.origin,
      })
      setShowCreate(false)
      setNewEmail('')
      setNewNote('')
      showSuccess('Invitation sent')
      fetchInvitations()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Failed to create invitation')
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
        base_url: window.location.origin,
      })
      setShowBatch(false)
      setBatchEmails('')
      setBatchNote('')
      showSuccess(`${emails.length} invitations sent`)
      fetchInvitations()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Failed to create invitations')
    }
  }

  const handleReinvite = async (id: string) => {
    try {
      await admin.invitations.reinvite(id, window.location.origin)
      showSuccess('New invitation sent')
      fetchInvitations()
    } catch {
      setError('Failed to re-invite')
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

  const handleDelete = async (id: string) => {
    if (!confirm('Permanently delete this invitation? This cannot be undone.')) return
    try {
      await admin.invitations.delete(id)
      fetchInvitations()
    } catch {
      setError('Failed to delete invitation')
    }
  }

  return (
    <div>
      {/* Search & Action bar */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <input
          type="text"
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search by email or note..."
          autoComplete="off"
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
        />
        <div className="flex gap-3">
          <button
            onClick={() => { setShowBatch(true); setShowCreate(false) }}
            className="px-4 py-2 rounded-lg text-sm transition-colors"
            style={{
              backgroundColor: 'var(--app-bg-tertiary)',
              color: 'var(--app-text-primary)',
              border: '1px solid var(--app-border-default)',
            }}
          >
            Batch Invite
          </button>
          <button
            onClick={() => { setShowCreate(true); setShowBatch(false) }}
            className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
            style={{ background: 'var(--app-gradient-primary)' }}
          >
            Invite User
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-success-bg)', color: 'var(--app-accent-success)' }}>
          {success}
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Invite User</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Email</label>
              <input
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                placeholder="user@example.com"
              />
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
              <button type="submit" className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: 'var(--app-gradient-primary)' }}>Send Invite</button>
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--app-text-muted)' }}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Batch Create Form */}
      {showBatch && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h3 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>Batch Invite</h3>
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
              <button type="submit" className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: 'var(--app-gradient-primary)' }}>Send All</button>
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
          <>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Email</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Status</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Note</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Expires</th>
                <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Created</th>
                <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((inv, idx) => {
                const isExpired = inv.expires_at && new Date(inv.expires_at) < new Date()
                const statusLabel = !inv.is_active ? 'Deactivated' : isExpired ? 'Expired' : inv.is_used ? 'Registered' : 'Pending'
                const statusColor = !inv.is_active ? 'var(--app-text-muted)' : isExpired ? 'var(--app-accent-error)' : inv.is_used ? 'var(--app-accent-success)' : 'var(--app-accent-warning)'
                const canReinvite = inv.email && !inv.is_used && (!inv.is_active || isExpired)

                return (
                  <tr key={inv.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>
                      {inv.email || '-'}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ color: statusColor }}>
                        {statusLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      {inv.note || '-'}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: isExpired ? 'var(--app-accent-error)' : 'var(--app-text-muted)' }}>
                      {inv.expires_at ? new Date(inv.expires_at).toLocaleString() : '-'}
                    </td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex gap-2 justify-end">
                        {canReinvite && (
                          <button
                            onClick={() => handleReinvite(inv.id)}
                            className="px-2 py-1 rounded text-xs transition-colors"
                            style={{ color: 'var(--app-accent-primary)' }}
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.1)'}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          >
                            Re-Invite
                          </button>
                        )}
                        {inv.is_active && !inv.is_used && !isExpired && (
                          <button
                            onClick={() => handleDeactivate(inv.id)}
                            className="px-2 py-1 rounded text-xs transition-colors"
                            style={{ color: 'var(--app-accent-warning)' }}
                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.1)'}
                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          >
                            Deactivate
                          </button>
                        )}
                        <button
                          onClick={() => handleDelete(inv.id)}
                          className="p-1.5 rounded-md transition-colors"
                          style={{ color: 'var(--app-text-muted)' }}
                          title="Delete invitation"
                          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--app-accent-error)')}
                          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--app-text-muted)')}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Pagination */}
          {total > 0 && (() => {
            const totalPages = Math.ceil(total / pageSize)
            const startIdx = (page - 1) * pageSize + 1
            const endIdx = Math.min(page * pageSize, total)
            return (
              <div className="px-4 py-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                  Showing {startIdx}-{endIdx} of {total}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page <= 1}
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
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page >= totalPages}
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
            )
          })()}
          </>
        )}
      </div>
    </div>
  )
}
