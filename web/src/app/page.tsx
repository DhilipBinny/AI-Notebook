'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'

const LOGOS = [
  { file: '/6984702b-a107-45ed-b1aa-706705deb50c.png', label: 'Logo A' },
  { file: '/8a05c0de-dc57-4a3f-8b5c-ea9b00f42203.png', label: 'Logo B' },
  { file: '/a7ac5906-c5c1-4819-b60b-6141da54bf2f.png', label: 'Logo C' },
  { file: '/eecb3725-8be7-406e-918c-0032c6b2b299.png', label: 'Logo D' },
]

export default function Home() {
  const router = useRouter()
  const [selected, setSelected] = useState<number | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
    }}>
      {/* Header */}
      <h1 style={{
        fontSize: '2.5rem',
        fontWeight: 700,
        color: '#F8FAFC',
        marginBottom: '0.5rem',
        letterSpacing: '-0.02em',
      }}>
        AI Notebook
      </h1>
      <p style={{
        fontSize: '1.1rem',
        color: '#94A3B8',
        marginBottom: '3rem',
        textAlign: 'center',
        maxWidth: '500px',
      }}>
        Pick a logo — click to see it in the navbar preview below
      </p>

      {/* Logo Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: '2rem',
        marginBottom: '3rem',
        maxWidth: '700px',
        width: '100%',
      }}>
        {LOGOS.map((logo, i) => (
          <div
            key={i}
            onClick={() => setSelected(i)}
            style={{
              background: selected === i ? 'rgba(59, 130, 246, 0.15)' : 'rgba(30, 41, 59, 0.8)',
              border: selected === i ? '2px solid #3B82F6' : '2px solid rgba(148, 163, 184, 0.15)',
              borderRadius: '16px',
              padding: '2rem',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '1rem',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{
              width: '120px',
              height: '120px',
              position: 'relative',
              borderRadius: '12px',
              overflow: 'hidden',
              background: '#0F172A',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <Image
                src={logo.file}
                alt={logo.label}
                width={120}
                height={120}
                style={{ objectFit: 'contain' }}
              />
            </div>
            <span style={{
              color: selected === i ? '#3B82F6' : '#CBD5E1',
              fontWeight: 600,
              fontSize: '1rem',
            }}>
              {logo.label}
            </span>
          </div>
        ))}
      </div>

      {/* Navbar Preview */}
      {selected !== null && (
        <div style={{ width: '100%', maxWidth: '700px', marginBottom: '2rem' }}>
          <p style={{ color: '#64748B', fontSize: '0.85rem', marginBottom: '0.75rem', textAlign: 'center' }}>
            Navbar preview
          </p>
          <div style={{
            background: '#1E293B',
            borderRadius: '12px',
            padding: '0.75rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            border: '1px solid rgba(148, 163, 184, 0.1)',
          }}>
            <Image
              src={LOGOS[selected].file}
              alt="Logo preview"
              width={36}
              height={36}
              style={{ borderRadius: '6px', objectFit: 'contain' }}
            />
            <span style={{ color: '#F1F5F9', fontWeight: 700, fontSize: '1.1rem', letterSpacing: '-0.01em' }}>
              AI Notebook
            </span>
            <div style={{ flex: 1 }} />
            <span style={{ color: '#64748B', fontSize: '0.85rem' }}>Dashboard</span>
            <span style={{ color: '#64748B', fontSize: '0.85rem' }}>Templates</span>
            <span style={{ color: '#64748B', fontSize: '0.85rem' }}>Settings</span>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '1rem' }}>
        <button
          onClick={() => router.push('/auth/login')}
          style={{
            background: '#3B82F6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            padding: '0.75rem 2rem',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Go to Login
        </button>
        <button
          onClick={() => router.push('/dashboard')}
          style={{
            background: 'transparent',
            color: '#94A3B8',
            border: '1px solid rgba(148, 163, 184, 0.3)',
            borderRadius: '8px',
            padding: '0.75rem 2rem',
            fontSize: '1rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Dashboard
        </button>
      </div>
    </div>
  )
}
