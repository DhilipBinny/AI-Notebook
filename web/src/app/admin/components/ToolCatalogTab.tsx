'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { admin } from '@/lib/api'
import { Pencil, Trash2, Plus, X, Check } from 'lucide-react'

interface ToolItem {
  name: string
  category: string
  description?: string
  is_active: boolean
}

interface ToolGroup {
  category: string
  tools: ToolItem[]
}

export default function ToolCatalogTab() {
  const [toolGroups, setToolGroups] = useState<ToolGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  // Add form
  const [showAddTool, setShowAddTool] = useState(false)
  const [addToolForm, setAddToolForm] = useState({ name: '', category: '', description: '' })
  const [isAddingTool, setIsAddingTool] = useState(false)

  // Edit state
  const [editingToolName, setEditingToolName] = useState<string | null>(null)
  const [editToolForm, setEditToolForm] = useState({ category: '', description: '', is_active: true })

  const existingCategories = useMemo(() => [...new Set(toolGroups.map(g => g.category))], [toolGroups])
  const totalTools = useMemo(() => toolGroups.reduce((sum, g) => sum + g.tools.length, 0), [toolGroups])
  const activeTools = useMemo(() => toolGroups.reduce((sum, g) => sum + g.tools.filter(t => t.is_active).length, 0), [toolGroups])

  const fetchToolCatalog = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await admin.systemPrompts.getToolCatalog()
      setToolGroups(data)
    } catch {
      setError('Failed to load tool catalog')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchToolCatalog()
  }, [fetchToolCatalog])

  const handleAddTool = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      setIsAddingTool(true)
      await admin.systemPrompts.addTool({
        name: addToolForm.name.trim(),
        category: addToolForm.category.trim(),
        description: addToolForm.description.trim() || undefined,
      })
      setAddToolForm({ name: '', category: '', description: '' })
      setShowAddTool(false)
      setSuccessMsg('Tool added to catalog')
      fetchToolCatalog()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to add tool'
      setError(errorMsg)
    } finally {
      setIsAddingTool(false)
    }
  }

  const startEditingTool = (tool: ToolItem) => {
    setEditingToolName(tool.name)
    setEditToolForm({ category: tool.category, description: tool.description || '', is_active: tool.is_active })
  }

  const handleSaveTool = async (toolName: string) => {
    setError('')
    try {
      await admin.systemPrompts.updateTool(toolName, {
        category: editToolForm.category,
        description: editToolForm.description || undefined,
        is_active: editToolForm.is_active,
      })
      setEditingToolName(null)
      setSuccessMsg('Tool updated')
      fetchToolCatalog()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update tool'
      setError(errorMsg)
    }
  }

  const handleDeleteTool = async (toolName: string) => {
    if (!confirm(`Remove "${toolName}" from the tool catalog?`)) return
    setError('')
    try {
      await admin.systemPrompts.deleteTool(toolName)
      setSuccessMsg('Tool removed from catalog')
      if (editingToolName === toolName) setEditingToolName(null)
      fetchToolCatalog()
      setTimeout(() => setSuccessMsg(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete tool'
      setError(errorMsg)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-6 h-6 border-2 border-t-transparent rounded-full animate-spin"
          style={{ borderColor: 'var(--app-accent-primary)', borderTopColor: 'transparent' }} />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
            Master list of AI Cell tools. Add new entries here when tools are implemented in the playground.
          </p>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
              {totalTools} total
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--app-accent-success)' }}>
              {activeTools} active
            </span>
            {totalTools !== activeTools && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171' }}>
                {totalTools - activeTools} disabled
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowAddTool(!showAddTool)}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm text-white transition-colors"
          style={{ background: 'var(--app-gradient-primary)' }}
        >
          {showAddTool ? <X size={14} /> : <Plus size={14} />}
          {showAddTool ? 'Cancel' : 'Add Tool'}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: 'var(--app-accent-success)' }}>
          {successMsg}
        </div>
      )}

      {/* Add tool form */}
      {showAddTool && (
        <div className="mb-6 p-6 rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
          <h2 className="text-lg font-medium mb-4" style={{ color: 'var(--app-text-primary)' }}>
            Add Tool to Catalog
          </h2>
          <form onSubmit={handleAddTool} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Function Name</label>
                <input
                  type="text"
                  value={addToolForm.name}
                  onChange={(e) => setAddToolForm({ ...addToolForm, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., execute_terminal_command"
                  required
                />
                <p className="text-[11px] mt-1" style={{ color: 'var(--app-text-muted)' }}>Must match the Python function name in the playground</p>
              </div>
              <div>
                <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Category</label>
                <input
                  type="text"
                  value={addToolForm.category}
                  onChange={(e) => setAddToolForm({ ...addToolForm, category: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="e.g., Terminal"
                  list="tool-categories"
                  required
                />
                <datalist id="tool-categories">
                  {existingCategories.map(c => <option key={c} value={c} />)}
                </datalist>
              </div>
            </div>
            <div>
              <label className="block text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>Description</label>
              <input
                type="text"
                value={addToolForm.description}
                onChange={(e) => setAddToolForm({ ...addToolForm, description: e.target.value })}
                className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none"
                style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                placeholder="Short description of what this tool does"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAddTool(false)}
                className="px-4 py-2 rounded-lg text-sm transition-colors"
                style={{ backgroundColor: 'var(--app-bg-tertiary)', color: 'var(--app-text-secondary)' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isAddingTool}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isAddingTool ? 'Adding...' : 'Add Tool'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tool list by category */}
      {toolGroups.length === 0 ? (
        <div className="py-6 text-center text-sm rounded-xl" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-muted)' }}>
          No tools in catalog. Click &quot;Add Tool&quot; to register a playground tool.
        </div>
      ) : (
        <div className="space-y-4">
          {toolGroups.map(group => (
            <div key={group.category} className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
              <div className="px-4 py-2.5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                <span className="text-sm font-semibold" style={{ color: 'var(--app-text-secondary)' }}>{group.category}</span>
                <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{group.tools.length} tools</span>
              </div>
              <div className="divide-y" style={{ borderColor: 'var(--app-border-default)' }}>
                {group.tools.map(tool => (
                  <div key={tool.name} className="px-4 py-2.5">
                    {editingToolName === tool.name ? (
                      <div className="grid grid-cols-4 gap-3 items-center">
                        <div>
                          <span className="text-xs font-mono font-medium" style={{ color: 'var(--app-text-primary)' }}>{tool.name}</span>
                        </div>
                        <div>
                          <input
                            type="text"
                            value={editToolForm.category}
                            onChange={(e) => setEditToolForm({ ...editToolForm, category: e.target.value })}
                            className="w-full px-2 py-1 rounded text-xs focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                            list="tool-categories-edit"
                          />
                          <datalist id="tool-categories-edit">
                            {existingCategories.map(c => <option key={c} value={c} />)}
                          </datalist>
                        </div>
                        <div>
                          <input
                            type="text"
                            value={editToolForm.description}
                            onChange={(e) => setEditToolForm({ ...editToolForm, description: e.target.value })}
                            className="w-full px-2 py-1 rounded text-xs focus:outline-none"
                            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                            placeholder="Description"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <label className="flex items-center gap-1 cursor-pointer text-xs" style={{ color: 'var(--app-text-muted)' }}>
                            <input
                              type="checkbox"
                              checked={editToolForm.is_active}
                              onChange={(e) => setEditToolForm({ ...editToolForm, is_active: e.target.checked })}
                            />
                            Active
                          </label>
                          <button onClick={() => handleSaveTool(tool.name)} className="p-1 rounded transition-colors" style={{ color: 'var(--app-accent-success)' }} title="Save">
                            <Check size={14} />
                          </button>
                          <button onClick={() => setEditingToolName(null)} className="p-1 rounded transition-colors" style={{ color: 'var(--app-text-muted)' }} title="Cancel">
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono font-medium" style={{ color: tool.is_active ? 'var(--app-text-primary)' : 'var(--app-text-muted)', textDecoration: tool.is_active ? 'none' : 'line-through' }}>
                            {tool.name}
                          </span>
                          {tool.description && (
                            <span className="text-[11px]" style={{ color: 'var(--app-text-muted)' }}>{tool.description}</span>
                          )}
                          {!tool.is_active && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171' }}>disabled</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => startEditingTool(tool)}
                            className="p-1 rounded-md transition-colors"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Edit tool"
                            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--app-text-primary)')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--app-text-muted)')}
                          >
                            <Pencil size={12} />
                          </button>
                          <button
                            onClick={() => handleDeleteTool(tool.name)}
                            className="p-1 rounded-md transition-colors"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Remove from catalog"
                            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--app-accent-error)')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--app-text-muted)')}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
