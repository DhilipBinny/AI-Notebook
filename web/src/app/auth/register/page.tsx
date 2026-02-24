'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Image from 'next/image'
import { auth } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

function RegisterPageContent() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()
  const searchParams = useSearchParams()
  const setUser = useAuthStore((state) => state.setUser)

  const hasInviteToken = Boolean(inviteCode)
  const emailFromInvite = Boolean(searchParams.get('email'))

  // Pre-fill invite code and email from URL query params
  useEffect(() => {
    const invite = searchParams.get('invite')
    const emailParam = searchParams.get('email')
    if (invite) setInviteCode(invite)
    if (emailParam) setEmail(emailParam)
  }, [searchParams])

  // Redirect to dashboard if already logged in (validate token first)
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      auth.getMe().then(() => {
        router.push('/dashboard')
      }).catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      })
    }
  }, [router])

  const passwordPolicy = {
    minLength: password.length >= 8,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/~`]/.test(password),
  }
  const allPoliciesMet = Object.values(passwordPolicy).every(Boolean)
  const passwordsMatch = password === confirmPassword && confirmPassword.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!allPoliciesMet) {
      setError('Password does not meet all requirements')
      return
    }

    if (!passwordsMatch) {
      setError('Passwords do not match')
      return
    }

    setIsLoading(true)

    try {
      const tokens = await auth.register(email, password, inviteCode || undefined)
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
      // Fetch user info after successful registration
      const user = await auth.getMe()
      setUser(user)
      router.push('/dashboard')
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Registration failed')
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
            className="text-3xl font-bold"
            style={{ color: 'var(--app-text-primary)' }}
          >
            Create Account
          </h2>
          <p
            className="mt-2"
            style={{ color: 'var(--app-text-muted)' }}
          >
            Sign up for AI Notebook
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
          {!hasInviteToken ? (
            /* No invite token — show gated message */
            <div className="text-center py-6">
              <div
                className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)' }}
              >
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: 'var(--app-accent-primary)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h3
                className="text-lg font-semibold mb-2"
                style={{ color: 'var(--app-text-primary)' }}
              >
                Invitation Required
              </h3>
              <p
                className="text-sm mb-6"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Registration is by invitation only. Please use the invite link sent to your email, or contact an administrator to request access.
              </p>
              <div className="text-center text-sm">
                <span style={{ color: 'var(--app-text-muted)' }}>
                  Already have an account?{' '}
                </span>
                <Link
                  href="/auth/login"
                  className="font-medium transition-colors hover:opacity-80"
                  style={{ color: 'var(--app-accent-primary)' }}
                >
                  Sign in
                </Link>
              </div>
            </div>
          ) : (
            /* Has invite token — show registration form */
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
                    readOnly={emailFromInvite}
                    value={email}
                    onChange={(e) => !emailFromInvite && setEmail(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none"
                    style={{
                      backgroundColor: emailFromInvite ? 'var(--app-bg-tertiary)' : 'var(--app-bg-input)',
                      border: '1px solid var(--app-border-default)',
                      color: 'var(--app-text-primary)',
                      opacity: emailFromInvite ? 0.7 : 1,
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
                    placeholder="Create a strong password"
                  />
                  {/* Password Policy Checklist */}
                  {password.length > 0 && (
                    <div className="mt-2 p-3 rounded-lg" style={{ backgroundColor: 'var(--app-bg-tertiary)', border: '1px solid var(--app-border-default)' }}>
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
                </div>
                <div>
                  <label
                    htmlFor="confirm-password"
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--app-text-secondary)' }}
                  >
                    Confirm Password
                  </label>
                  <input
                    id="confirm-password"
                    name="confirmPassword"
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none"
                    style={{
                      backgroundColor: 'var(--app-bg-input)',
                      border: '1px solid var(--app-border-default)',
                      color: 'var(--app-text-primary)',
                    }}
                    placeholder="Confirm your password"
                  />
                  {confirmPassword && !passwordsMatch && (
                    <p className="text-xs mt-1.5" style={{ color: 'var(--app-accent-error)' }}>Passwords do not match</p>
                  )}
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading || !allPoliciesMet || !passwordsMatch}
                className="w-full py-3 rounded-xl text-white font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 hover:opacity-90"
                style={{
                  background: 'var(--app-gradient-primary)',
                  boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
                }}
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Creating account...
                  </>
                ) : (
                  'Create account'
                )}
              </button>

              <div className="text-center text-sm">
                <span style={{ color: 'var(--app-text-muted)' }}>
                  Already have an account?{' '}
                </span>
                <Link
                  href="/auth/login"
                  className="font-medium transition-colors hover:opacity-80"
                  style={{ color: 'var(--app-accent-primary)' }}
                >
                  Sign in
                </Link>
              </div>
            </form>
          )}
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

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterPageContent />
    </Suspense>
  )
}
