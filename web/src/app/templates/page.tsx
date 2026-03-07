'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { templates } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import AppHeader from '@/components/AppHeader'
import type { NotebookTemplate } from '@/types'

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  beginner: { bg: 'var(--app-alert-success-bg)', text: 'var(--app-accent-success)', border: 'var(--app-alert-success-border)' },
  intermediate: { bg: 'var(--app-alert-warning-bg)', text: 'var(--app-accent-warning)', border: 'var(--app-alert-warning-border)' },
  advanced: { bg: 'var(--app-alert-error-bg)', text: 'var(--app-accent-error)', border: 'var(--app-alert-error-border)' },
}

export default function TemplatesPage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [templateList, setTemplateList] = useState<NotebookTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [forkingId, setForkingId] = useState<string | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      router.push('/auth/login')
    }
  }, [router])

  const fetchTemplates = useCallback(async () => {
    try {
      setIsLoading(true)
      setError('')
      const data = await templates.list(selectedCategory || undefined)
      setTemplateList(data)
    } catch {
      setError('Failed to load templates')
    } finally {
      setIsLoading(false)
    }
  }, [selectedCategory])

  useEffect(() => {
    fetchTemplates()
  }, [fetchTemplates])

  const categories = Array.from(
    new Set(templateList.map((t) => t.category).filter(Boolean))
  ) as string[]

  const handleUseTemplate = async (id: string) => {
    try {
      setForkingId(id)
      const result = await templates.fork(id)
      router.push(`/notebook/${result.project_id}`)
    } catch {
      setError('Failed to create notebook from template')
      setForkingId(null)
    }
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
      <AppHeader title="Templates" subtitle="Browse & use notebook templates" />

      <div className="px-6 py-6">

        {/* Category Filter */}
        {categories.length > 0 && (
          <div className="mb-6">
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-muted)' }}>
              Filter by Category
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 rounded-lg text-sm focus:outline-none cursor-pointer"
              style={{
                backgroundColor: 'var(--app-bg-input)',
                color: 'var(--app-text-primary)',
                border: '1px solid var(--app-border-default)',
              }}
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="mb-6 p-3 rounded-lg text-sm"
            style={{
              backgroundColor: 'var(--app-alert-error-bg)',
              color: 'var(--app-accent-error)',
              border: '1px solid var(--app-alert-error-border)',
            }}
          >
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">
              dismiss
            </button>
          </div>
        )}

        {/* Loading */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-4">
              <div
                className="w-10 h-10 border-4 rounded-full animate-spin"
                style={{ borderColor: 'var(--app-alert-info-border)', borderTopColor: 'var(--app-accent-primary)' }}
              />
              <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>Loading templates...</span>
            </div>
          </div>
        ) : templateList.length === 0 ? (
          <div
            className="text-center py-20 rounded-2xl"
            style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}
          >
            <div
              className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}
            >
              <svg className="w-8 h-8" style={{ color: 'var(--app-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <h4 className="text-base font-medium mb-2" style={{ color: 'var(--app-text-primary)' }}>No templates available</h4>
            <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
              {selectedCategory
                ? 'No templates found for this category. Try a different filter.'
                : 'Check back later for new templates.'}
            </p>
          </div>
        ) : (
          /* Template Grid */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {templateList.map((template) => {
              const diffStyle = DIFFICULTY_COLORS[template.difficulty_level] || DIFFICULTY_COLORS.beginner
              const isForkingThis = forkingId === template.id

              return (
                <div
                  key={template.id}
                  className="rounded-xl overflow-hidden flex flex-col transition-all hover:shadow-lg"
                  style={{
                    backgroundColor: 'var(--app-bg-card)',
                    border: '1px solid var(--app-border-default)',
                  }}
                >
                  {/* Card Header */}
                  <div className="p-5 flex-1">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <h3 className="text-base font-semibold leading-snug" style={{ color: 'var(--app-text-primary)' }}>
                        {template.name}
                      </h3>
                      <span
                        className="flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          backgroundColor: diffStyle.bg,
                          color: diffStyle.text,
                          border: `1px solid ${diffStyle.border}`,
                        }}
                      >
                        {template.difficulty_level}
                      </span>
                    </div>

                    {template.description && (
                      <p className="text-sm mb-4 line-clamp-3" style={{ color: 'var(--app-text-muted)' }}>
                        {template.description}
                      </p>
                    )}

                    {/* Meta Info */}
                    <div className="flex flex-wrap items-center gap-3 text-xs mb-3" style={{ color: 'var(--app-text-muted)' }}>
                      {template.category && (
                        <span className="flex items-center gap-1">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                          </svg>
                          {template.category}
                        </span>
                      )}
                      {template.estimated_minutes != null && (
                        <span className="flex items-center gap-1">
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {template.estimated_minutes} min
                        </span>
                      )}
                    </div>

                    {/* Tags */}
                    {template.tags && template.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {template.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-0.5 rounded text-xs"
                            style={{
                              backgroundColor: 'var(--app-bg-tertiary)',
                              color: 'var(--app-text-muted)',
                              border: '1px solid var(--app-border-default)',
                            }}
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Card Footer */}
                  <div className="px-5 py-3" style={{ borderTop: '1px solid var(--app-border-default)' }}>
                    <button
                      onClick={() => handleUseTemplate(template.id)}
                      disabled={isForkingThis}
                      className="w-full px-4 py-2 rounded-lg text-sm text-white font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-2 hover:opacity-90"
                      style={{
                        background: 'var(--app-gradient-primary)',
                        boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)',
                      }}
                    >
                      {isForkingThis ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          Creating...
                        </>
                      ) : (
                        'Use Template'
                      )}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
