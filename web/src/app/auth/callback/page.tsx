'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

// Loading fallback component
function CallbackLoading() {
  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--app-bg-primary)' }}
    >
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4">
          <div
            className="w-full h-full border-4 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }}
          />
        </div>
        <h2
          className="text-xl font-semibold mb-2"
          style={{ color: 'var(--app-text-primary)' }}
        >
          Loading...
        </h2>
      </div>
    </div>
  )
}

// Main callback handler component (uses useSearchParams)
function OAuthCallbackHandler() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState('')
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((state) => state.setUser)

  useEffect(() => {
    const handleCallback = async () => {
      // Get tokens from URL params
      const accessToken = searchParams.get('access_token')
      const refreshToken = searchParams.get('refresh_token')
      const errorParam = searchParams.get('error')
      const errorMessage = searchParams.get('message')

      if (errorParam) {
        setStatus('error')
        setError(errorMessage || 'OAuth authentication failed')
        return
      }

      if (!accessToken || !refreshToken) {
        setStatus('error')
        setError('Missing tokens in callback')
        return
      }

      try {
        // Store tokens
        localStorage.setItem('access_token', accessToken)
        localStorage.setItem('refresh_token', refreshToken)

        // Fetch user info
        const user = await auth.getMe()
        setUser(user)

        setStatus('success')

        // Redirect to dashboard after short delay
        setTimeout(() => {
          router.push('/dashboard')
        }, 1000)
      } catch (err) {
        console.error('OAuth callback error:', err)
        setStatus('error')
        setError('Failed to complete authentication')
        // Clear any partial state
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }

    handleCallback()
  }, [searchParams, router, setUser])

  // Apply dark theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--app-bg-primary)' }}
    >
      <div className="text-center">
        {status === 'loading' && (
          <>
            <div className="w-16 h-16 mx-auto mb-4">
              <div
                className="w-full h-full border-4 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }}
              />
            </div>
            <h2
              className="text-xl font-semibold mb-2"
              style={{ color: 'var(--app-text-primary)' }}
            >
              Completing sign in...
            </h2>
            <p style={{ color: 'var(--app-text-muted)' }}>
              Please wait while we set up your account
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <div
              className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(34, 197, 94, 0.2)' }}
            >
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                style={{ color: '#22c55e' }}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2
              className="text-xl font-semibold mb-2"
              style={{ color: 'var(--app-text-primary)' }}
            >
              Successfully signed in!
            </h2>
            <p style={{ color: 'var(--app-text-muted)' }}>
              Redirecting to dashboard...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div
              className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)' }}
            >
              <svg
                className="w-8 h-8"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                style={{ color: '#ef4444' }}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h2
              className="text-xl font-semibold mb-2"
              style={{ color: 'var(--app-text-primary)' }}
            >
              Authentication failed
            </h2>
            <p className="mb-4" style={{ color: 'var(--app-text-muted)' }}>
              {error}
            </p>
            <button
              onClick={() => router.push('/auth/login')}
              className="px-6 py-2 rounded-lg font-medium transition-all hover:opacity-90"
              style={{
                background: 'var(--app-gradient-primary)',
                color: 'white'
              }}
            >
              Back to Login
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// Page component with Suspense boundary (required for useSearchParams in Next.js 15)
export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={<CallbackLoading />}>
      <OAuthCallbackHandler />
    </Suspense>
  )
}
