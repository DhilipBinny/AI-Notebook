'use client'

import { Suspense, useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

// Loading fallback
function LoginLoading() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--app-bg-primary)' }}
    >
      <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
        style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }}
      />
    </div>
  )
}

// Main login form component
function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((state) => state.setUser)

  // Check for OAuth error in URL
  useEffect(() => {
    const oauthError = searchParams.get('error')
    const oauthMessage = searchParams.get('message')
    if (oauthError) {
      setError(oauthMessage || 'Authentication failed')
    }
  }, [searchParams])

  // Redirect to dashboard if already logged in (validate token first)
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      auth.getMe().then(() => {
        router.push('/dashboard')
      }).catch(() => {
        // Token is invalid, clear it and stay on login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      })
    }
  }, [router])

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
      const error = err as { response?: { data?: { detail?: string | Array<{ msg: string }> } } }
      const detail = error.response?.data?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        setError(detail.map(d => d.msg).join(', '))
      } else {
        setError('Login failed')
      }
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
          <Image
            src="/a7ac5906-c5c1-4819-b60b-6141da54bf2f.png"
            alt="AI Notebook"
            width={72}
            height={72}
            className="mx-auto mb-4"
            style={{ objectFit: 'contain' }}
            priority
          />
          <h2
            className="text-xl font-bold"
            style={{ color: 'var(--app-text-primary)' }}
          >
            AI Notebook
          </h2>
          <p
            className="mt-2 text-sm"
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
                <div className="mt-1.5 text-right">
                  <Link
                    href="/auth/forgot-password"
                    className="text-xs font-medium transition-colors hover:opacity-80"
                    style={{ color: 'var(--app-accent-primary)' }}
                  >
                    Forgot password?
                  </Link>
                </div>
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

// Page component with Suspense boundary (required for useSearchParams in Next.js 15)
export default function LoginPage() {
  return (
    <Suspense fallback={<LoginLoading />}>
      <LoginForm />
    </Suspense>
  )
}
