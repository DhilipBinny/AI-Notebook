'use client'

import { useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import AppHeader from '@/components/AppHeader'
import { Key, BarChart3, LucideIcon } from 'lucide-react'

const TABS = [
  { key: 'api-keys', label: 'API Keys', icon: Key },
  { key: 'usage', label: 'Usage', icon: BarChart3 },
] as const

export type SettingsTabKey = (typeof TABS)[number]['key']

interface SettingsLayoutProps {
  activeTab: SettingsTabKey
  onTabChange: (tab: SettingsTabKey) => void
  children: ReactNode
}

export default function SettingsLayout({ activeTab, onTabChange, children }: SettingsLayoutProps) {
  const router = useRouter()
  const { user, setUser } = useAuthStore()
  const [authChecked, setAuthChecked] = useState(false)
  const [hoveredTab, setHoveredTab] = useState<string | null>(null)

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

  if (!authChecked || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
        <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
      <AppHeader title="Settings" subtitle="API keys & usage" />

      <div className="flex" style={{ height: 'calc(100vh - 57px)' }}>
        {/* Sidebar */}
        <aside
          className="w-[220px] flex-shrink-0 overflow-y-auto p-4"
          style={{
            backgroundColor: 'var(--app-bg-secondary)',
            borderRight: '1px solid var(--app-border-primary)',
          }}
        >
          <div
            className="text-[11px] font-semibold tracking-wider uppercase mb-3 px-3"
            style={{ color: 'var(--app-text-muted)' }}
          >
            Navigation
          </div>

          <nav className="flex flex-col gap-1">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.key
              const isHovered = hoveredTab === tab.key
              const Icon: LucideIcon = tab.icon

              return (
                <button
                  key={tab.key}
                  onClick={() => onTabChange(tab.key)}
                  onMouseEnter={() => setHoveredTab(tab.key)}
                  onMouseLeave={() => setHoveredTab(null)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left"
                  style={{
                    backgroundColor: isActive
                      ? 'var(--app-bg-input)'
                      : isHovered
                        ? 'var(--app-bg-tertiary)'
                        : 'transparent',
                    color: isActive ? 'var(--app-text-primary)' : 'var(--app-text-muted)',
                  }}
                >
                  <Icon size={18} />
                  {tab.label}
                </button>
              )
            })}
          </nav>
        </aside>

        {/* Content area */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
