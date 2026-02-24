'use client'

import { Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import SettingsLayout, { type SettingsTabKey } from './components/SettingsLayout'
import ApiKeysTab from './components/ApiKeysTab'
import UsageTab from './components/UsageTab'

function SettingsPageContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const tab = (searchParams.get('tab') || 'api-keys') as SettingsTabKey

  const handleTabChange = (newTab: SettingsTabKey) => {
    router.push(`/settings?tab=${newTab}`, { scroll: false })
  }

  return (
    <SettingsLayout activeTab={tab} onTabChange={handleTabChange}>
      {tab === 'api-keys' && <ApiKeysTab />}
      {tab === 'usage' && <UsageTab />}
    </SettingsLayout>
  )
}

export default function SettingsPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
        <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    }>
      <SettingsPageContent />
    </Suspense>
  )
}
