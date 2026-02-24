'use client'

import { useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { auth } from '@/lib/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      await auth.forgotPassword(email, window.location.origin)
      setSubmitted(true)
    } catch {
      // Always show success to prevent user enumeration
      setSubmitted(true)
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
            Forgot password
          </h2>
          <p
            className="mt-2 text-sm"
            style={{ color: 'var(--app-text-muted)' }}
          >
            {submitted
              ? 'Check your email for a reset link'
              : "Enter your email and we'll send you a reset link"}
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
          {submitted ? (
            <div className="text-center py-4">
              <div
                className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)' }}
              >
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: 'var(--app-accent-success)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <p
                className="text-sm mb-6"
                style={{ color: 'var(--app-text-secondary)' }}
              >
                If <strong>{email}</strong> is registered, you'll receive a password reset link shortly. The link expires in 10 minutes.
              </p>
              <Link
                href="/auth/login"
                className="inline-block px-6 py-2.5 rounded-xl text-sm font-medium transition-all hover:opacity-90"
                style={{
                  background: 'var(--app-gradient-primary)',
                  color: '#ffffff',
                }}
              >
                Back to sign in
              </Link>
            </div>
          ) : (
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
                    Sending...
                  </>
                ) : (
                  'Send reset link'
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
