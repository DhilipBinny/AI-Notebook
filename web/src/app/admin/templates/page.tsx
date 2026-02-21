'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { admin, templates } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { NotebookTemplate } from '@/types'

const DIFFICULTY_OPTIONS = ['beginner', 'intermediate', 'advanced'] as const
const DIFFICULTY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  beginner: { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)' },
  intermediate: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
  advanced: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444', border: 'rgba(239, 68, 68, 0.3)' },
}

interface TemplateFormState {
  name: string
  description: string
  category: string
  difficulty_level: 'beginner' | 'intermediate' | 'advanced'
  tags: string
  is_public: boolean
}

const defaultFormState: TemplateFormState = {
  name: '',
  description: '',
  category: '',
  difficulty_level: 'beginner',
  tags: '',
  is_public: true,
}

export default function AdminTemplatesPage() {
  const router = useRouter()
  const user = useAuthStore((state) => state.user)

  const [templateList, setTemplateList] = useState<NotebookTemplate[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [creating, setCreating] = useState(false)

  // Create from project form
  const [showCreateFromProject, setShowCreateFromProject] = useState(false)
  const [projectId, setProjectId] = useState('')
  const [fromProjectForm, setFromProjectForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [creatingFromProject, setCreatingFromProject] = useState(false)

  // Edit state
  const [editingTemplate, setEditingTemplate] = useState<NotebookTemplate | null>(null)
  const [editForm, setEditForm] = useState<TemplateFormState>({ ...defaultFormState })
  const [updating, setUpdating] = useState(false)

  // Delete state
  const [deleteConfirm, setDeleteConfirm] = useState<NotebookTemplate | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])

  // Redirect non-admin users
  useEffect(() => {
    if (user && !user.is_admin) {
      router.push('/dashboard')
    }
  }, [user, router])

  const fetchTemplates = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await templates.list()
      setTemplateList(data)
    } catch {
      setError('Failed to load templates')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchTemplates()
    }
  }, [user, fetchTemplates])

  const showSuccess = (msg: string) => {
    setSuccessMessage(msg)
    setTimeout(() => setSuccessMessage(''), 4000)
  }

  const parseTags = (tagsStr: string): string[] => {
    return tagsStr
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.name.trim()) return

    try {
      setCreating(true)
      setError('')
      await admin.templates.create({
        name: createForm.name.trim(),
        description: createForm.description.trim() || undefined,
        category: createForm.category.trim() || undefined,
        difficulty_level: createForm.difficulty_level,
        tags: parseTags(createForm.tags).length > 0 ? parseTags(createForm.tags) : undefined,
        is_public: createForm.is_public,
      })
      setShowCreate(false)
      setCreateForm({ ...defaultFormState })
      showSuccess('Template created successfully')
      fetchTemplates()
    } catch {
      setError('Failed to create template')
    } finally {
      setCreating(false)
    }
  }

  const handleCreateFromProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!projectId.trim() || !fromProjectForm.name.trim()) return

    try {
      setCreatingFromProject(true)
      setError('')
      await admin.templates.createFromProject(projectId.trim(), {
        name: fromProjectForm.name.trim(),
        description: fromProjectForm.description.trim() || undefined,
        category: fromProjectForm.category.trim() || undefined,
        difficulty_level: fromProjectForm.difficulty_level,
        tags: parseTags(fromProjectForm.tags).length > 0 ? parseTags(fromProjectForm.tags) : undefined,
        is_public: fromProjectForm.is_public,
      })
      setShowCreateFromProject(false)
      setProjectId('')
      setFromProjectForm({ ...defaultFormState })
      showSuccess('Template created from project successfully')
      fetchTemplates()
    } catch {
      setError('Failed to create template from project. Check the project ID.')
    } finally {
      setCreatingFromProject(false)
    }
  }

  const handleEditClick = (template: NotebookTemplate) => {
    setEditingTemplate(template)
    setEditForm({
      name: template.name,
      description: template.description || '',
      category: template.category || '',
      difficulty_level: template.difficulty_level,
      tags: template.tags?.join(', ') || '',
      is_public: template.is_public,
    })
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingTemplate || !editForm.name.trim()) return

    try {
      setUpdating(true)
      setError('')
      await admin.templates.update(editingTemplate.id, {
        name: editForm.name.trim(),
        description: editForm.description.trim() || undefined,
        category: editForm.category.trim() || undefined,
        difficulty_level: editForm.difficulty_level,
        tags: parseTags(editForm.tags).length > 0 ? parseTags(editForm.tags) : undefined,
        is_public: editForm.is_public,
      })
      setEditingTemplate(null)
      showSuccess('Template updated successfully')
      fetchTemplates()
    } catch {
      setError('Failed to update template')
    } finally {
      setUpdating(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteConfirm) return

    try {
      setDeleting(true)
      setError('')
      await admin.templates.delete(deleteConfirm.id)
      setDeleteConfirm(null)
      showSuccess('Template deleted successfully')
      fetchTemplates()
    } catch {
      setError('Failed to delete template')
    } finally {
      setDeleting(false)
    }
  }

  // Reusable form fields renderer
  const renderFormFields = (
    form: TemplateFormState,
    setForm: (updater: (prev: TemplateFormState) => TemplateFormState) => void
  ) => (
    <>
      <div>
        <label className="block text-sm mb-1 text-gray-400">Name *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500"
          placeholder="Template name"
          required
        />
      </div>
      <div>
        <label className="block text-sm mb-1 text-gray-400">Description</label>
        <textarea
          value={form.description}
          onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500 resize-y"
          placeholder="Brief description of the template"
          rows={2}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm mb-1 text-gray-400">Category</label>
          <input
            type="text"
            value={form.category}
            onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500"
            placeholder="e.g., Data Science"
          />
        </div>
        <div>
          <label className="block text-sm mb-1 text-gray-400">Difficulty</label>
          <select
            value={form.difficulty_level}
            onChange={(e) =>
              setForm((prev) => ({
                ...prev,
                difficulty_level: e.target.value as TemplateFormState['difficulty_level'],
              }))
            }
            className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500 cursor-pointer"
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-sm mb-1 text-gray-400">Tags (comma-separated)</label>
        <input
          type="text"
          value={form.tags}
          onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
          className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500"
          placeholder="python, pandas, visualization"
        />
      </div>
      <div className="flex items-center gap-3">
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={form.is_public}
            onChange={(e) => setForm((prev) => ({ ...prev, is_public: e.target.checked }))}
            className="sr-only peer"
          />
          <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
        </label>
        <span className="text-sm text-gray-300">Public</span>
      </div>
    </>
  )

  if (!user?.is_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <p className="text-gray-500">Access denied</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">
              Template Management
            </h1>
            <p className="mt-1 text-sm text-gray-400">
              Create, edit, and manage notebook templates
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push('/dashboard')}
              className="px-4 py-2 rounded-lg text-sm transition-colors bg-gray-800 text-gray-300 border border-gray-700 hover:bg-gray-700"
            >
              Back to Dashboard
            </button>
            <button
              onClick={() => {
                setShowCreateFromProject(true)
                setShowCreate(false)
                setEditingTemplate(null)
              }}
              className="px-4 py-2 rounded-lg text-sm transition-colors bg-gray-800 text-white border border-gray-700 hover:bg-gray-700"
            >
              Create from Project
            </button>
            <button
              onClick={() => {
                setShowCreate(true)
                setShowCreateFromProject(false)
                setEditingTemplate(null)
              }}
              className="px-4 py-2 rounded-lg text-sm text-white transition-colors bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400"
            >
              Create Template
            </button>
          </div>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="mb-4 p-3 rounded-lg text-sm bg-green-500/15 text-green-400 border border-green-500/30 flex items-center justify-between">
            {successMessage}
            <button onClick={() => setSuccessMessage('')} className="ml-2 text-green-400 hover:text-green-300">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-lg text-sm bg-red-500/15 text-red-400 border border-red-500/30">
            {error}
            <button onClick={() => setError('')} className="ml-2 underline">
              dismiss
            </button>
          </div>
        )}

        {/* Create Template Form */}
        {showCreate && (
          <div className="mb-6 p-6 rounded-xl bg-gray-800 border border-gray-700">
            <h3 className="text-lg font-medium text-white mb-4">Create Template</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              {renderFormFields(createForm, setCreateForm)}
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50 flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500"
                >
                  {creating && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreate(false)
                    setCreateForm({ ...defaultFormState })
                  }}
                  className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-300"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Create from Project Form */}
        {showCreateFromProject && (
          <div className="mb-6 p-6 rounded-xl bg-gray-800 border border-gray-700">
            <h3 className="text-lg font-medium text-white mb-4">Create Template from Project</h3>
            <form onSubmit={handleCreateFromProject} className="space-y-4">
              <div>
                <label className="block text-sm mb-1 text-gray-400">Project ID *</label>
                <input
                  type="text"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg text-sm bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500 font-mono"
                  placeholder="e.g., abc123-def456-..."
                  required
                />
              </div>
              {renderFormFields(fromProjectForm, setFromProjectForm)}
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={creatingFromProject}
                  className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50 flex items-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500"
                >
                  {creatingFromProject && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  Create from Project
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateFromProject(false)
                    setProjectId('')
                    setFromProjectForm({ ...defaultFormState })
                  }}
                  className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-300"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Edit Template Modal */}
        {editingTemplate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setEditingTemplate(null)}
            />
            <div className="relative w-full max-w-lg rounded-2xl shadow-2xl p-6 bg-gray-800 border border-gray-700">
              <h3 className="text-lg font-bold text-white mb-4">Edit Template</h3>
              <form onSubmit={handleUpdate} className="space-y-4">
                {renderFormFields(editForm, setEditForm)}
                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setEditingTemplate(null)}
                    className="flex-1 px-4 py-2.5 rounded-xl border border-gray-700 text-gray-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updating}
                    className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-blue-500"
                  >
                    {updating && (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    )}
                    Save Changes
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Delete Confirm Modal */}
        {deleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => !deleting && setDeleteConfirm(null)}
            />
            <div className="relative w-full max-w-sm rounded-2xl shadow-2xl p-6 bg-gray-800 border border-red-500/30">
              <h3 className="text-base font-bold text-white mb-2">Delete Template</h3>
              <p className="mb-4 text-gray-400">
                Delete &quot;{deleteConfirm.name}&quot;? This cannot be undone.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  disabled={deleting}
                  className="flex-1 px-4 py-2.5 rounded-xl border border-gray-700 text-gray-300 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium bg-red-600 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {deleting && (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Templates Table */}
        <div className="rounded-xl overflow-hidden bg-gray-800 border border-gray-700">
          {isLoading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : templateList.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No templates yet. Create one above.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Name</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Category</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Difficulty</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Tags</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Visibility</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-400">Created</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {templateList.map((template) => {
                  const diffStyle =
                    DIFFICULTY_COLORS[template.difficulty_level] || DIFFICULTY_COLORS.beginner

                  return (
                    <tr key={template.id} className="border-b border-gray-700/50">
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-white font-medium">{template.name}</p>
                          {template.description && (
                            <p className="text-xs text-gray-500 truncate max-w-xs">
                              {template.description}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-400">
                        {template.category || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className="px-2 py-0.5 rounded text-xs font-medium"
                          style={{
                            backgroundColor: diffStyle.bg,
                            color: diffStyle.text,
                            border: `1px solid ${diffStyle.border}`,
                          }}
                        >
                          {template.difficulty_level}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {template.tags && template.tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {template.tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="px-1.5 py-0.5 rounded text-xs bg-gray-700/60 text-gray-400"
                              >
                                {tag}
                              </span>
                            ))}
                            {template.tags.length > 3 && (
                              <span className="text-xs text-gray-500">
                                +{template.tags.length - 3}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            template.is_public
                              ? 'bg-green-500/15 text-green-400'
                              : 'bg-gray-700/50 text-gray-500'
                          }`}
                        >
                          {template.is_public ? 'Public' : 'Private'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {new Date(template.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => handleEditClick(template)}
                            className="px-2.5 py-1 rounded text-xs transition-colors bg-gray-700 text-gray-300 hover:bg-gray-600 border border-gray-600"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(template)}
                            className="px-2.5 py-1 rounded text-xs transition-colors text-red-400 hover:bg-red-500/15 border border-red-500/30"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
