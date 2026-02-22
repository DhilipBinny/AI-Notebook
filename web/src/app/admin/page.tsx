'use client'

import { Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import AdminLayout, { type AdminTabKey } from './components/AdminLayout'
import UsersTab from './components/UsersTab'
import PlatformKeysTab from './components/PlatformKeysTab'
import InvitationsTab from './components/InvitationsTab'
import CreditsTab from './components/CreditsTab'
import TemplatesTab from './components/TemplatesTab'

function AdminPageContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const tab = (searchParams.get('tab') || 'users') as AdminTabKey

  const handleTabChange = (newTab: AdminTabKey) => {
    router.push(`/admin?tab=${newTab}`, { scroll: false })
  }

  return (
    <AdminLayout activeTab={tab} onTabChange={handleTabChange}>
      {tab === 'users' && <UsersTab />}
      {tab === 'platform-keys' && <PlatformKeysTab />}
      {tab === 'invitations' && <InvitationsTab />}
      {tab === 'models' && <CreditsTab />}
      {tab === 'templates' && <TemplatesTab />}
    </AdminLayout>
  )
}

export default function AdminPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
        <div className="w-8 h-8 border-4 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    }>
      <AdminPageContent />
    </Suspense>
  )
}
