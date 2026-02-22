'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

interface AppHeaderProps {
  title?: string
  subtitle?: string
}

export default function AppHeader({ title, subtitle }: AppHeaderProps) {
  const router = useRouter()
  const { user, setUser } = useAuthStore()
  const [showMenu, setShowMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const getUserInitials = () => {
    if (user?.name) {
      return user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    }
    return user?.email?.charAt(0).toUpperCase() || '?'
  }

  const handleLogout = async () => {
    try { await auth.logout() } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    router.push('/auth/login')
  }

  return (
    <header
      className="relative z-50 backdrop-blur-xl"
      style={{
        backgroundColor: 'var(--app-bg-secondary)',
        borderBottom: '1px solid var(--app-border-default)',
      }}
    >
      <div className="px-6 py-3">
        <div className="flex justify-between items-center">
          {/* Left: Logo + Title */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/dashboard')}
              className="flex items-center gap-3 hover:opacity-80 transition-opacity"
            >
              <Image
                src="/a7ac5906-c5c1-4819-b60b-6141da54bf2f.png"
                alt="AI Notebook"
                width={36}
                height={36}
                className="rounded-xl"
                style={{ objectFit: 'contain' }}
              />
              <div>
                <h1 className="text-base font-bold" style={{ color: 'var(--app-text-primary)' }}>
                  {title || 'AI Notebook'}
                </h1>
                {subtitle && (
                  <p className="text-xs" style={{ color: 'var(--app-accent-primary)' }}>{subtitle}</p>
                )}
              </div>
            </button>
          </div>

          {/* Right: Profile */}
          <div className="relative z-50" ref={menuRef}>
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="flex items-center gap-2.5 px-3 py-1.5 rounded-full transition-all hover:bg-white/5"
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold"
                style={{ background: 'var(--app-gradient-primary)', color: 'white' }}
              >
                {getUserInitials()}
              </div>
              <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                {user?.email?.split('@')[0]}
              </span>
              <svg
                className={`w-3.5 h-3.5 transition-transform duration-200 ${showMenu ? 'rotate-180' : ''}`}
                style={{ color: 'var(--app-text-muted)' }}
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showMenu && (
              <div
                className="absolute right-0 top-full mt-2 w-64 rounded-xl shadow-2xl overflow-hidden z-50"
                style={{
                  backgroundColor: 'var(--app-bg-secondary)',
                  border: '1px solid var(--app-border-default)',
                }}
              >
                {/* User Info */}
                <div className="p-4" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold"
                      style={{ background: 'var(--app-gradient-primary)', color: 'white' }}
                    >
                      {getUserInitials()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--app-text-primary)' }}>
                        {user?.email?.split('@')[0]}
                      </p>
                      <p className="text-xs truncate" style={{ color: 'var(--app-text-muted)' }}>
                        {user?.email}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Navigation */}
                <div className="p-2" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <button
                    onClick={() => { setShowMenu(false); router.push('/dashboard') }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                    style={{ color: 'var(--app-text-secondary)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                    </svg>
                    <span className="text-sm">Dashboard</span>
                  </button>
                  <button
                    onClick={() => { setShowMenu(false); router.push('/settings') }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                    style={{ color: 'var(--app-text-secondary)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <span className="text-sm">Settings & API Keys</span>
                  </button>
                </div>

                {/* Admin Link */}
                {user?.is_admin && (
                  <div className="p-2" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <button
                      onClick={() => { setShowMenu(false); router.push('/admin') }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                      </svg>
                      <span className="text-sm">Admin</span>
                    </button>
                  </div>
                )}

                {/* Sign Out */}
                <div className="p-2">
                  <button
                    onClick={() => { setShowMenu(false); handleLogout() }}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                    style={{ color: 'var(--app-accent-error)' }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    <span className="text-sm">Sign Out</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
