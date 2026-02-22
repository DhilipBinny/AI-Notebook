'use client'

import { useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import AppHeader from '@/components/AppHeader'

const TABS = [
  { key: 'users', label: 'Users' },
  { key: 'platform-keys', label: 'Platform Keys' },
  { key: 'invitations', label: 'Invitations' },
  { key: 'models', label: 'Models' },
  { key: 'templates', label: 'Templates' },
] as const

export type AdminTabKey = (typeof TABS)[number]['key']

interface AdminLayoutProps {
  activeTab: AdminTabKey
  onTabChange: (tab: AdminTabKey) => void
  children: ReactNode
}

export default function AdminLayout({ activeTab, onTabChange, children }: AdminLayoutProps) {
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
      <AppHeader title="Admin" subtitle="Manage users, keys, models & templates" />

      <div className="px-6 py-6">
        {/* Tab bar */}
        <div className="flex gap-1 mb-6 rounded-lg p-1" style={{ backgroundColor: 'var(--app-bg-secondary)' }}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className="px-4 py-2 rounded-md text-sm font-medium transition-all"
              style={{
                backgroundColor: activeTab === tab.key ? 'var(--app-bg-card)' : 'transparent',
                color: activeTab === tab.key ? 'var(--app-text-primary)' : 'var(--app-text-muted)',
                boxShadow: activeTab === tab.key ? '0 1px 3px rgba(0,0,0,0.2)' : 'none',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {children}
      </div>
    </div>
  )
}
