'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const setUser = useAuthStore((state) => state.setUser)

  // Apply dark theme on mount for auth pages
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const tokens = await auth.login(email, password)
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
      // Fetch user info after successful login
      const user = await auth.getMe()
      setUser(user)
      router.push('/dashboard')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--app-bg-primary)' }}
    >
      {/* Subtle background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute -top-40 -right-40 w-80 h-80 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          style={{ backgroundColor: 'var(--app-accent-primary)' }}
        />
        <div
          className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          style={{ backgroundColor: 'var(--app-accent-secondary)' }}
        />
      </div>

      <div className="relative z-10 max-w-md w-full">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div
            className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center shadow-lg"
            style={{
              background: 'var(--app-gradient-primary)',
              boxShadow: '0 10px 40px rgba(59, 130, 246, 0.3)'
            }}
          >
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h2
            className="text-3xl font-bold"
            style={{ color: 'var(--app-text-primary)' }}
          >
            AI Notebook
          </h2>
          <p
            className="mt-2"
            style={{ color: 'var(--app-text-muted)' }}
          >
            Sign in to your account
          </p>
        </div>

        {/* Form Card */}
        <div
          className="rounded-2xl backdrop-blur-sm p-8 mb-8"
          style={{
            backgroundColor: 'var(--app-bg-card)',
            border: '1px solid var(--app-border-default)'
          }}
        >
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div
                className="rounded-xl p-4"
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)'
                }}
              >
                <p className="text-sm" style={{ color: 'var(--app-accent-error)' }}>{error}</p>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-medium mb-2"
                  style={{ color: 'var(--app-text-secondary)' }}
                >
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none"
                  style={{
                    backgroundColor: 'var(--app-bg-input)',
                    border: '1px solid var(--app-border-default)',
                    color: 'var(--app-text-primary)',
                  }}
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium mb-2"
                  style={{ color: 'var(--app-text-secondary)' }}
                >
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none"
                  style={{
                    backgroundColor: 'var(--app-bg-input)',
                    border: '1px solid var(--app-border-default)',
                    color: 'var(--app-text-primary)',
                  }}
                  placeholder="Enter your password"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-xl text-white font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:opacity-90"
              style={{
                background: 'var(--app-gradient-primary)',
                boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
              }}
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>

            <div className="text-center text-sm">
              <span style={{ color: 'var(--app-text-muted)' }}>
                {"Don't have an account? "}
              </span>
              <Link
                href="/auth/register"
                className="font-medium transition-colors hover:opacity-80"
                style={{ color: 'var(--app-accent-primary)' }}
              >
                Sign up
              </Link>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="text-center text-sm" style={{ color: 'var(--app-text-muted)' }}>
          <p>Version 1.0.0</p>
          <p className="mt-1">&copy; {new Date().getFullYear()} AI Notebook. All rights reserved.</p>
        </div>
      </div>
    </div>
  )
}
