'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { auth } from '@/lib/api'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      auth.getMe().then(() => {
        router.replace('/dashboard')
      }).catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        router.replace('/auth/login')
      })
    } else {
      router.replace('/auth/login')
    }
  }, [router])

  return null
}
