'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

// Google Icon SVG
const GoogleIcon = () => (
  <svg className="w-5 h-5" viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
)

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((state) => state.setUser)

  // Check for OAuth error in URL
  useEffect(() => {
    const oauthError = searchParams.get('error')
    const oauthMessage = searchParams.get('message')
    if (oauthError) {
      setError(oauthMessage || 'OAuth authentication failed')
    }
  }, [searchParams])

  // Redirect to dashboard if already logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      router.push('/dashboard')
    }
  }, [router])

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

            {/* Divider */}
            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full" style={{ borderTop: '1px solid var(--app-border-default)' }} />
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4" style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-muted)' }}>
                  Or continue with
                </span>
              </div>
            </div>

            {/* Google Login Button */}
            <button
              type="button"
              onClick={() => {
                setIsGoogleLoading(true)
                window.location.href = '/api/auth/google'
              }}
              disabled={isGoogleLoading}
              className="w-full py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3 hover:opacity-90"
              style={{
                backgroundColor: 'var(--app-bg-input)',
                border: '1px solid var(--app-border-default)',
                color: 'var(--app-text-primary)',
              }}
            >
              {isGoogleLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-gray-400/30 border-t-gray-400 rounded-full animate-spin" />
                  Redirecting to Google...
                </>
              ) : (
                <>
                  <GoogleIcon />
                  Sign in with Google
                </>
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
