'use client'

import { Suspense, useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import Image from 'next/image'
import { auth } from '@/lib/api'

function ResetPasswordLoading() {
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

function ResetPasswordForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  // Token validation state
  const [tokenValid, setTokenValid] = useState<boolean | null>(null)
  const [maskedEmail, setMaskedEmail] = useState('')
  const [tokenError, setTokenError] = useState('')

  // Validate token on mount
  useEffect(() => {
    if (!token) {
      setTokenValid(false)
      setTokenError('No reset token provided')
      return
    }

    auth.validateResetToken(token)
      .then((res) => {
        setTokenValid(true)
        setMaskedEmail(res.email)
      })
      .catch((err: unknown) => {
        setTokenValid(false)
        const error = err as { response?: { data?: { detail?: string } } }
        setTokenError(error.response?.data?.detail || 'Invalid or expired reset link')
      })
  }, [token])

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
      await auth.resetPassword(token, password)
      setSuccess(true)
      // Redirect to login after short delay
      setTimeout(() => router.push('/auth/login'), 3000)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Password reset failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: 'var(--app-bg-primary)' }}
    >
      {/* Background elements */}
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
            Reset password
          </h2>
          {maskedEmail && (
            <p
              className="mt-2 text-sm"
              style={{ color: 'var(--app-text-muted)' }}
            >
              for {maskedEmail}
            </p>
          )}
        </div>

        {/* Form Card */}
        <div
          className="rounded-2xl backdrop-blur-sm p-8 mb-8"
          style={{
            backgroundColor: 'var(--app-bg-card)',
            border: '1px solid var(--app-border-default)'
          }}
        >
          {/* Loading state */}
          {tokenValid === null && (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }}
              />
              <span className="ml-3 text-sm" style={{ color: 'var(--app-text-muted)' }}>
                Validating reset link...
              </span>
            </div>
          )}

          {/* Invalid token */}
          {tokenValid === false && (
            <div className="text-center py-4">
              <div
                className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ backgroundColor: 'var(--app-alert-error-bg)' }}
              >
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: 'var(--app-accent-error)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <h3
                className="text-lg font-semibold mb-2"
                style={{ color: 'var(--app-text-primary)' }}
              >
                {tokenError}
              </h3>
              <p
                className="text-sm mb-6"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Please request a new password reset link.
              </p>
              <div className="flex flex-col gap-3 items-center">
                <Link
                  href="/auth/forgot-password"
                  className="inline-block px-6 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:opacity-90"
                  style={{
                    background: 'var(--app-gradient-primary)',
                  }}
                >
                  Request new link
                </Link>
                <Link
                  href="/auth/login"
                  className="text-sm font-medium transition-colors hover:opacity-80"
                  style={{ color: 'var(--app-accent-primary)' }}
                >
                  Back to sign in
                </Link>
              </div>
            </div>
          )}

          {/* Success state */}
          {success && (
            <div className="text-center py-4">
              <div
                className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ backgroundColor: 'var(--app-alert-success-bg)' }}
              >
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: 'var(--app-accent-success)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3
                className="text-lg font-semibold mb-2"
                style={{ color: 'var(--app-text-primary)' }}
              >
                Password reset successfully
              </h3>
              <p
                className="text-sm mb-4"
                style={{ color: 'var(--app-text-muted)' }}
              >
                Redirecting to sign in...
              </p>
              <Link
                href="/auth/login"
                className="text-sm font-medium transition-colors hover:opacity-80"
                style={{ color: 'var(--app-accent-primary)' }}
              >
                Go to sign in now
              </Link>
            </div>
          )}

          {/* Password form */}
          {tokenValid === true && !success && (
            <form className="space-y-6" onSubmit={handleSubmit}>
              {error && (
                <div
                  className="rounded-xl p-4"
                  style={{
                    backgroundColor: 'var(--app-alert-error-bg)',
                    border: '1px solid var(--app-alert-error-border)'
                  }}
                >
                  <p className="text-sm" style={{ color: 'var(--app-accent-error)' }}>{error}</p>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="password"
                    className="block text-sm font-medium mb-2"
                    style={{ color: 'var(--app-text-secondary)' }}
                  >
                    New password
                  </label>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
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
                    Confirm new password
                  </label>
                  <input
                    id="confirm-password"
                    name="confirmPassword"
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
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
                    Resetting password...
                  </>
                ) : (
                  'Reset password'
                )}
              </button>

              <div className="text-center text-sm">
                <Link
                  href="/auth/login"
                  className="font-medium transition-colors hover:opacity-80"
                  style={{ color: 'var(--app-accent-primary)' }}
                >
                  Back to sign in
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordLoading />}>
      <ResetPasswordForm />
    </Suspense>
  )
}
