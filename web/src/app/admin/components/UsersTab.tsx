'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { admin } from '@/lib/api'
import type { CreditBalance } from '@/types'
import { useAuthStore } from '@/lib/store'
import type { AdminUser, AdminUserDetail } from '@/types'

export default function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Search & filters
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Slide-out drawer
  const [drawerUser, setDrawerUser] = useState<AdminUser | null>(null)
  const [drawerDetail, setDrawerDetail] = useState<AdminUserDetail | null>(null)
  const [loadingDrawer, setLoadingDrawer] = useState(false)

  // Drawer inline edits
  const [editingMaxProjects, setEditingMaxProjects] = useState(false)
  const [newMaxProjects, setNewMaxProjects] = useState('')
  const [editingCredits, setEditingCredits] = useState(false)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustReason, setAdjustReason] = useState('')

  // Actions
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [resetPasswordUser, setResetPasswordUser] = useState<AdminUser | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  // Kebab menu
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  const user = useAuthStore((state) => state.user)

  const fetchUsers = useCallback(async () => {
    try {
      setIsLoading(true)
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      }
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      if (roleFilter) params.role = roleFilter

      const data = await admin.users.list(params as Parameters<typeof admin.users.list>[0])
      setUsers(data.users)
      setTotal(data.total)
    } catch {
      setError('Failed to load users')
    } finally {
      setIsLoading(false)
    }
  }, [page, pageSize, search, statusFilter, roleFilter, sortBy, sortOrder])

  useEffect(() => {
    if (user?.is_admin) {
      fetchUsers()
    }
  }, [user, fetchUsers])

  // Close kebab menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    if (openMenuId) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [openMenuId])

  const handleSearchChange = (value: string) => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setSearch(value)
      setPage(1)
    }, 300)
  }

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(''), 3000)
  }

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(col)
      setSortOrder('asc')
    }
    setPage(1)
  }

  // Open drawer with user detail
  const openDrawer = async (u: AdminUser) => {
    setDrawerUser(u)
    setEditingMaxProjects(false)
    setEditingCredits(false)
    try {
      setLoadingDrawer(true)
      const data = await admin.users.get(u.id)
      setDrawerDetail(data)
    } catch {
      setError('Failed to load user details')
    } finally {
      setLoadingDrawer(false)
    }
  }

  const closeDrawer = () => {
    setDrawerUser(null)
    setDrawerDetail(null)
    setEditingMaxProjects(false)
    setEditingCredits(false)
  }

  const handleToggleActive = async (u: AdminUser) => {
    const action = u.is_active ? 'deactivate' : 'activate'
    if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} user ${u.email}?${u.is_active ? ' All sessions will be revoked.' : ''}`)) return
    try {
      setActionLoading(u.id)
      await admin.users.toggleActive(u.id, !u.is_active)
      showSuccess(`User ${action}d successfully`)
      fetchUsers()
      if (drawerUser?.id === u.id) closeDrawer()
    } catch {
      setError(`Failed to ${action} user`)
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggleAdmin = async (u: AdminUser) => {
    const action = u.is_admin ? 'remove admin from' : 'make admin'
    if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} ${u.email}?`)) return
    try {
      setActionLoading(u.id)
      await admin.users.toggleAdmin(u.id, !u.is_admin)
      showSuccess(`User admin status updated`)
      fetchUsers()
      if (drawerUser?.id === u.id) closeDrawer()
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || `Failed to update admin status`
        : `Failed to update admin status`
      setError(msg)
    } finally {
      setActionLoading(null)
    }
  }

  const passwordPolicy = {
    minLength: newPassword.length >= 8,
    uppercase: /[A-Z]/.test(newPassword),
    lowercase: /[a-z]/.test(newPassword),
    number: /[0-9]/.test(newPassword),
    special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]/.test(newPassword),
  }
  const allPoliciesMet = Object.values(passwordPolicy).every(Boolean)
  const passwordsMatch = newPassword === confirmPassword && confirmPassword.length > 0

  const handleResetPassword = async () => {
    if (!resetPasswordUser) return
    if (!allPoliciesMet) {
      setError('Password does not meet all requirements')
      return
    }
    if (!passwordsMatch) {
      setError('Passwords do not match')
      return
    }
    try {
      setActionLoading(resetPasswordUser.id)
      await admin.users.resetPassword(resetPasswordUser.id, newPassword)
      showSuccess(`Password reset for ${resetPasswordUser.email}. All sessions revoked.`)
      setResetPasswordUser(null)
      setNewPassword('')
      setConfirmPassword('')
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to reset password'
        : 'Failed to reset password'
      setError(msg)
    } finally {
      setActionLoading(null)
    }
  }

  const handleUpdateMaxProjects = async (userId: string) => {
    const val = parseInt(newMaxProjects, 10)
    if (isNaN(val) || val < 1 || val > 100) {
      setError('Max projects must be between 1 and 100')
      return
    }
    try {
      setActionLoading(userId)
      await admin.users.updateMaxProjects(userId, val)
      showSuccess('Max projects updated')
      setEditingMaxProjects(false)
      setNewMaxProjects('')
      fetchUsers()
      // Refresh drawer detail
      const data = await admin.users.get(userId)
      setDrawerDetail(data)
    } catch {
      setError('Failed to update max projects')
    } finally {
      setActionLoading(null)
    }
  }

  const handleAdjustCredits = async (userId: string) => {
    const amount = parseInt(adjustAmount, 10)
    if (isNaN(amount) || amount === 0) {
      setError('Amount must be a non-zero integer (cents)')
      return
    }
    try {
      setActionLoading(userId)
      const result: CreditBalance = await admin.credits.adjust({
        user_id: userId,
        amount_cents: amount,
        reason: adjustReason.trim() || undefined,
      })
      showSuccess(`Credits adjusted. New balance: $${result.balance_dollars.toFixed(2)}`)
      setEditingCredits(false)
      setAdjustAmount('')
      setAdjustReason('')
      fetchUsers()
      // Refresh drawer detail
      const data = await admin.users.get(userId)
      setDrawerDetail(data)
    } catch {
      setError('Failed to adjust credits')
    } finally {
      setActionLoading(null)
    }
  }

  const totalPages = Math.ceil(total / pageSize)
  const startIdx = (page - 1) * pageSize + 1
  const endIdx = Math.min(page * pageSize, total)

  const SortIcon = ({ col }: { col: string }) => {
    if (sortBy !== col) return <span className="ml-1 opacity-30">{'\u2195'}</span>
    return <span className="ml-1">{sortOrder === 'asc' ? '\u25B2' : '\u25BC'}</span>
  }

  return (
    <div>
      {/* Search & Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <input
          type="text"
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Search name or email..."
          autoComplete="off"
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg text-sm focus:outline-none"
          style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
        >
          <option value="">All Roles</option>
          <option value="admin">Admin</option>
          <option value="user">User</option>
        </select>
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

      {/* Reset Password Modal (portal to body) */}
      {resetPasswordUser && createPortal(
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => { setResetPasswordUser(null); setNewPassword(''); setConfirmPassword('') }}
          />
          <div className="relative w-full max-w-md rounded-xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-lg font-bold mb-1" style={{ color: 'var(--app-text-primary)' }}>
              Reset Password
            </h3>
            <p className="text-sm mb-5" style={{ color: 'var(--app-text-muted)' }}>
              {resetPasswordUser.name || resetPasswordUser.email}
              {resetPasswordUser.name && (
                <span className="ml-1 text-xs">({resetPasswordUser.email})</span>
              )}
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password"
                  autoComplete="new-password"
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                />
              </div>

              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  autoComplete="new-password"
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: `1px solid ${confirmPassword && !passwordsMatch ? 'rgba(239, 68, 68, 0.5)' : 'var(--app-border-default)'}`, color: 'var(--app-text-primary)' }}
                />
                {confirmPassword && !passwordsMatch && (
                  <p className="text-xs mt-1" style={{ color: 'var(--app-accent-error)' }}>Passwords do not match</p>
                )}
              </div>

              {newPassword.length > 0 && (
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'var(--app-bg-tertiary)', border: '1px solid var(--app-border-default)' }}>
                  <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Password Requirements</p>
                  <div className="grid grid-cols-2 gap-1">
                    {[
                      { met: passwordPolicy.minLength, label: 'Min 8 characters' },
                      { met: passwordPolicy.uppercase, label: 'Uppercase letter' },
                      { met: passwordPolicy.lowercase, label: 'Lowercase letter' },
                      { met: passwordPolicy.number, label: 'Number' },
                      { met: passwordPolicy.special, label: 'Special character' },
                    ].map((rule) => (
                      <div key={rule.label} className="flex items-center gap-1.5">
                        <span className="text-xs">{rule.met ? '\u2705' : '\u274C'}</span>
                        <span className="text-xs" style={{ color: rule.met ? 'var(--app-accent-success)' : 'var(--app-text-muted)' }}>
                          {rule.label}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="p-3 rounded-lg text-xs" style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', color: 'var(--app-accent-warning)' }}>
                This will revoke all active sessions. The user will need to log in again.
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  onClick={() => { setResetPasswordUser(null); setNewPassword(''); setConfirmPassword('') }}
                  className="flex-1 px-4 py-2.5 rounded-xl text-sm"
                  style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleResetPassword}
                  disabled={!allPoliciesMet || !passwordsMatch || actionLoading === resetPasswordUser.id}
                  className="flex-1 px-4 py-2.5 rounded-xl text-sm text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  style={{ background: 'var(--app-gradient-primary)' }}
                >
                  {actionLoading === resetPasswordUser.id && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  Reset Password
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Slide-out Drawer (portal to body) */}
      {drawerUser && createPortal(
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={closeDrawer} />
          <div
            className="absolute right-0 top-0 h-full w-full max-w-lg overflow-y-auto shadow-2xl"
            style={{ backgroundColor: 'var(--app-bg-primary)', borderLeft: '1px solid var(--app-border-default)' }}
          >
            {/* Drawer Header */}
            <div className="sticky top-0 z-10 px-6 py-4 flex items-center justify-between" style={{ backgroundColor: 'var(--app-bg-primary)', borderBottom: '1px solid var(--app-border-default)' }}>
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text-primary)' }}>User Details</h2>
              <button
                onClick={closeDrawer}
                className="p-1.5 rounded-lg transition-colors hover:opacity-80"
                style={{ color: 'var(--app-text-muted)' }}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {loadingDrawer ? (
              <div className="p-8 text-center">
                <div className="w-8 h-8 rounded-full animate-spin mx-auto mb-3" style={{ borderWidth: '3px', borderColor: 'rgba(59, 130, 246, 0.3)', borderTopColor: 'var(--app-accent-primary)' }} />
                <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>Loading user details...</p>
              </div>
            ) : (
              <div className="p-6 space-y-6">
                {/* User Identity */}
                <div className="flex items-start gap-4">
                  <div
                    className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold flex-shrink-0"
                    style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-default)' }}
                  >
                    {(drawerUser.name || drawerUser.email).charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold truncate" style={{ color: 'var(--app-text-primary)' }}>
                      {drawerUser.name || '(no name)'}
                    </h3>
                    <p className="text-sm truncate" style={{ color: 'var(--app-text-muted)' }}>{drawerUser.email}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: drawerUser.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: drawerUser.is_active ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                        }}
                      >
                        {drawerUser.is_active ? 'Active' : 'Inactive'}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: drawerUser.is_admin ? 'rgba(99, 102, 241, 0.15)' : 'var(--app-bg-tertiary)',
                          color: drawerUser.is_admin ? 'var(--app-accent-indigo)' : 'var(--app-text-muted)',
                        }}
                      >
                        {drawerUser.is_admin ? 'Admin' : 'User'}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded text-xs"
                        style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-muted)' }}
                      >
                        {drawerUser.oauth_provider}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Stats Grid */}
                {drawerDetail && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Active Sessions</p>
                      <p className="text-xl font-bold" style={{ color: 'var(--app-text-primary)' }}>{drawerDetail.active_sessions_count}</p>
                    </div>
                    <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>API Keys</p>
                      <p className="text-xl font-bold" style={{ color: 'var(--app-text-primary)' }}>{drawerDetail.api_keys_count}</p>
                    </div>
                    <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Created</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                        {new Date(drawerUser.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                      <p className="text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Last Login</p>
                      <p className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                        {drawerUser.last_login_at ? new Date(drawerUser.last_login_at).toLocaleDateString() : 'Never'}
                      </p>
                    </div>
                  </div>
                )}

                {/* Projects Section */}
                <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--app-text-muted)' }}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                      </svg>
                      <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>Projects</span>
                    </div>
                    {!editingMaxProjects && (
                      <button
                        onClick={() => { setEditingMaxProjects(true); setNewMaxProjects(String(drawerUser.max_projects)) }}
                        className="text-xs px-2 py-1 rounded-lg transition-colors hover:opacity-80"
                        style={{ color: 'var(--app-accent-primary)' }}
                      >
                        Edit Limit
                      </button>
                    )}
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold" style={{ color: 'var(--app-text-primary)' }}>
                      {drawerDetail?.project_count ?? '...'}
                    </span>
                    <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>/ {drawerUser.max_projects} max</span>
                  </div>
                  {/* Progress bar */}
                  {drawerDetail && (
                    <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--app-bg-tertiary)' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(((drawerDetail.project_count ?? 0) / drawerUser.max_projects) * 100, 100)}%`,
                          backgroundColor: (drawerDetail.project_count ?? 0) >= drawerUser.max_projects ? 'var(--app-accent-error)' : 'var(--app-accent-primary)',
                        }}
                      />
                    </div>
                  )}
                  {/* Inline edit */}
                  {editingMaxProjects && (
                    <div className="mt-3 pt-3 flex items-center gap-2" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                      <label className="text-xs" style={{ color: 'var(--app-text-muted)' }}>New limit:</label>
                      <input
                        type="number"
                        value={newMaxProjects}
                        onChange={(e) => setNewMaxProjects(e.target.value)}
                        min={1}
                        max={100}
                        className="px-2 py-1.5 rounded-lg text-sm w-20 focus:outline-none"
                        style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                      />
                      <button
                        onClick={() => handleUpdateMaxProjects(drawerUser.id)}
                        disabled={actionLoading === drawerUser.id}
                        className="px-3 py-1.5 rounded-lg text-xs text-white font-medium disabled:opacity-50"
                        style={{ background: 'var(--app-gradient-primary)' }}
                      >
                        Save
                      </button>
                      <button
                        onClick={() => { setEditingMaxProjects(false); setNewMaxProjects('') }}
                        className="px-2 py-1.5 rounded-lg text-xs"
                        style={{ color: 'var(--app-text-muted)' }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>

                {/* Credits Section */}
                <div className="rounded-xl p-4" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--app-text-muted)' }}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>Credits</span>
                    </div>
                    {!editingCredits && (
                      <button
                        onClick={() => { setEditingCredits(true); setAdjustAmount(''); setAdjustReason('') }}
                        className="text-xs px-2 py-1 rounded-lg transition-colors hover:opacity-80"
                        style={{ color: 'var(--app-accent-success)' }}
                      >
                        Adjust
                      </button>
                    )}
                  </div>
                  <p className="text-2xl font-bold" style={{ color: 'var(--app-text-primary)' }}>
                    ${((drawerUser.credit_balance_cents || 0) / 100).toFixed(2)}
                  </p>
                  {drawerDetail && (
                    <div className="flex gap-4 mt-2 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                      <span>Deposited: <span style={{ color: 'var(--app-accent-success)' }}>${(drawerDetail.total_deposited_cents / 100).toFixed(2)}</span></span>
                      <span>Used: <span style={{ color: 'var(--app-accent-warning)' }}>${(drawerDetail.total_consumed_cents / 100).toFixed(2)}</span></span>
                    </div>
                  )}
                  {/* Inline adjust */}
                  {editingCredits && (
                    <div className="mt-3 pt-3 space-y-2" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                      <div className="flex gap-2">
                        <div className="flex-1">
                          <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Amount (cents)</label>
                          <input
                            type="number"
                            value={adjustAmount}
                            onChange={(e) => setAdjustAmount(e.target.value)}
                            placeholder="+500 or -200"
                            className="w-full px-2 py-1.5 rounded-lg text-sm focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </div>
                        <div className="flex-[2]">
                          <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Reason</label>
                          <input
                            type="text"
                            value={adjustReason}
                            onChange={(e) => setAdjustReason(e.target.value)}
                            placeholder="e.g. Bonus credit (optional)"
                            className="w-full px-2 py-1.5 rounded-lg text-sm focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                          />
                        </div>
                      </div>
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => { setEditingCredits(false); setAdjustAmount(''); setAdjustReason('') }}
                          className="px-3 py-1.5 rounded-lg text-xs"
                          style={{ color: 'var(--app-text-muted)' }}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => handleAdjustCredits(drawerUser.id)}
                          disabled={actionLoading === drawerUser.id}
                          className="px-3 py-1.5 rounded-lg text-xs text-white font-medium disabled:opacity-50"
                          style={{ background: 'var(--app-gradient-primary)' }}
                        >
                          Apply
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* Quick Actions in Drawer */}
                <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--app-border-default)' }}>
                  <div className="px-4 py-2.5" style={{ backgroundColor: 'var(--app-bg-card)', borderBottom: '1px solid var(--app-border-default)' }}>
                    <span className="text-xs font-medium" style={{ color: 'var(--app-text-muted)' }}>Actions</span>
                  </div>
                  {drawerUser.oauth_provider === 'local' && (
                    <button
                      onClick={() => {
                        setResetPasswordUser(drawerUser)
                        setNewPassword('')
                        setConfirmPassword('')
                      }}
                      className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors"
                      style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-secondary)', borderBottom: '1px solid var(--app-border-default)' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                    >
                      <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--app-accent-warning)' }}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                      </svg>
                      Reset Password
                    </button>
                  )}
                  <button
                    onClick={() => handleToggleAdmin(drawerUser)}
                    disabled={actionLoading === drawerUser.id || drawerUser.id === user?.id}
                    className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors disabled:opacity-50"
                    style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-secondary)', borderBottom: '1px solid var(--app-border-default)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                  >
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--app-accent-indigo)' }}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    {drawerUser.is_admin ? 'Remove Admin Role' : 'Grant Admin Role'}
                  </button>
                  <button
                    onClick={() => handleToggleActive(drawerUser)}
                    disabled={actionLoading === drawerUser.id || drawerUser.id === user?.id}
                    className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors disabled:opacity-50"
                    style={{ backgroundColor: 'var(--app-bg-card)', color: drawerUser.is_active ? 'var(--app-accent-error)' : 'var(--app-accent-success)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'}
                  >
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      {drawerUser.is_active ? (
                        <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      )}
                    </svg>
                    {drawerUser.is_active ? 'Deactivate User' : 'Activate User'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}

      {/* Users Table */}
      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
        {isLoading ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
        ) : users.length === 0 ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>No users found</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <th
                      className="text-left px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('name')}
                    >
                      Name/Email <SortIcon col="name" />
                    </th>
                    <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Status</th>
                    <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Role</th>
                    <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Provider</th>
                    <th
                      className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('total_deposited_cents')}
                    >
                      Deposited <SortIcon col="total_deposited_cents" />
                    </th>
                    <th
                      className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('total_consumed_cents')}
                    >
                      Consumed <SortIcon col="total_consumed_cents" />
                    </th>
                    <th
                      className="text-center px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('project_count')}
                    >
                      Projects <SortIcon col="project_count" />
                    </th>
                    <th
                      className="text-left px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('created_at')}
                    >
                      Created <SortIcon col="created_at" />
                    </th>
                    <th
                      className="text-left px-4 py-3 font-medium cursor-pointer select-none"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onClick={() => handleSort('last_login_at')}
                    >
                      Last Login <SortIcon col="last_login_at" />
                    </th>
                    <th className="w-12 px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u, idx) => (
                    <tr
                      key={u.id}
                      className="cursor-pointer transition-colors"
                      style={{ borderBottom: '1px solid var(--app-border-default)' }}
                      onClick={() => openDrawer(u)}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-sm" style={{ color: 'var(--app-text-primary)' }}>
                            {u.name || '(no name)'}
                          </p>
                          <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{u.email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: u.is_active ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                            color: u.is_active ? 'var(--app-accent-success)' : 'var(--app-accent-error)',
                          }}
                        >
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: u.is_admin ? 'rgba(99, 102, 241, 0.15)' : 'var(--app-bg-tertiary)',
                            color: u.is_admin ? 'var(--app-accent-indigo)' : 'var(--app-text-muted)',
                          }}
                        >
                          {u.is_admin ? 'Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                          {u.oauth_provider}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs" style={{ color: 'var(--app-accent-success)' }}>
                        ${((u.total_deposited_cents || 0) / 100).toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs" style={{ color: 'var(--app-accent-warning)' }}>
                        ${((u.total_consumed_cents || 0) / 100).toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-center text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                        <span className="font-mono">{u.project_count ?? 0}</span>
                        <span style={{ color: 'var(--app-text-muted)' }}> / {u.max_projects}</span>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--app-text-muted)' }}>
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="relative inline-block" ref={openMenuId === u.id ? menuRef : undefined}>
                          <button
                            onClick={() => setOpenMenuId(openMenuId === u.id ? null : u.id)}
                            className="p-1.5 rounded-lg transition-colors hover:opacity-80"
                            style={{
                              backgroundColor: openMenuId === u.id ? 'var(--app-bg-tertiary)' : 'transparent',
                              color: 'var(--app-text-secondary)',
                            }}
                          >
                            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                            </svg>
                          </button>

                          {openMenuId === u.id && (
                            <div
                              className={`absolute right-0 w-48 rounded-xl shadow-xl z-20 py-1 overflow-hidden ${idx >= users.length - 2 ? 'bottom-full mb-1' : 'top-full mt-1'}`}
                              style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}
                            >
                              {u.oauth_provider === 'local' && (
                                <button
                                  onClick={() => {
                                    setResetPasswordUser(u)
                                    setNewPassword('')
                                    setConfirmPassword('')
                                    setOpenMenuId(null)
                                  }}
                                  className="w-full text-left px-4 py-2 text-sm flex items-center gap-2.5 transition-colors"
                                  style={{ color: 'var(--app-accent-warning)' }}
                                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                >
                                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                                  </svg>
                                  Reset Password
                                </button>
                              )}
                              <button
                                onClick={() => { handleToggleAdmin(u); setOpenMenuId(null) }}
                                disabled={actionLoading === u.id || u.id === user?.id}
                                className="w-full text-left px-4 py-2 text-sm flex items-center gap-2.5 transition-colors disabled:opacity-50"
                                style={{ color: 'var(--app-accent-indigo)' }}
                                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                              >
                                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                                {u.is_admin ? 'Remove Admin' : 'Make Admin'}
                              </button>
                              <div className="my-1" style={{ borderTop: '1px solid var(--app-border-default)' }} />
                              <button
                                onClick={() => { handleToggleActive(u); setOpenMenuId(null) }}
                                disabled={actionLoading === u.id || u.id === user?.id}
                                className="w-full text-left px-4 py-2 text-sm flex items-center gap-2.5 transition-colors disabled:opacity-50"
                                style={{ color: u.is_active ? 'var(--app-accent-error)' : 'var(--app-accent-success)' }}
                                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                              >
                                <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  {u.is_active ? (
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                  ) : (
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  )}
                                </svg>
                                {u.is_active ? 'Deactivate' : 'Activate'}
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
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
                  Page {page} of {totalPages || 1}
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
          </>
        )}
      </div>
    </div>
  )
}
