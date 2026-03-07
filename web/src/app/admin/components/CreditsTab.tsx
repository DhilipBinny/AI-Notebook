'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { Edit3, Trash2, Search } from 'lucide-react'
import { AlertTriangle } from 'lucide-react'
import type { LLMModel, PlatformKey } from '@/types'

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'openai_compatible'] as const

export default function CreditsTab() {
  // Model registry table
  const [modelRegistry, setModelRegistry] = useState<LLMModel[]>([])
  const [isLoadingModels, setIsLoadingModels] = useState(true)
  const [modelsError, setModelsError] = useState('')
  const [modelsSuccess, setModelsSuccess] = useState('')

  // $0 pricing warnings
  const [warnings, setWarnings] = useState<{ provider: string; model_id: string; display_name: string }[]>([])

  // Create model form
  const [showCreateModel, setShowCreateModel] = useState(false)
  const [createModelForm, setCreateModelForm] = useState({
    provider: 'openai_compatible' as string,
    model_id: '',
    display_name: '',
    context_window: '',
    max_output_tokens: '',
    supports_vision: false,
    supports_function_calling: false,
    input_cost_per_1m_cents: '0',
    output_cost_per_1m_cents: '0',
    margin_multiplier: '1.30',
  })
  const [isCreatingModel, setIsCreatingModel] = useState(false)

  // Inline editing
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState({
    model_id: '',
    display_name: '',
    context_window: '' as string,
    max_output_tokens: '' as string,
    supports_vision: false,
    supports_function_calling: false,
    input_cost_per_1m_cents: 0,
    output_cost_per_1m_cents: 0,
    margin_multiplier: 1,
    is_active: true,
  })
  const [isSavingModel, setIsSavingModel] = useState(false)

  // Search
  const [searchQuery, setSearchQuery] = useState('')

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize] = useState(15)

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<LLMModel | null>(null)
  const [affectedKeys, setAffectedKeys] = useState<PlatformKey[]>([])

  const openDeleteModal = async (row: LLMModel) => {
    setDeleteTarget(row)
    try {
      const allKeys = await admin.platformKeys.list()
      const affected = allKeys.filter(k => k.provider === row.provider && k.model_name === row.model_id && k.is_active)
      setAffectedKeys(affected)
    } catch {
      setAffectedKeys([])
    }
  }

  const user = useAuthStore((state) => state.user)

  const fetchModels = useCallback(async () => {
    try {
      setIsLoadingModels(true)
      const data = await admin.models.list()
      setModelRegistry(data)
    } catch {
      setModelsError('Failed to load model registry')
    } finally {
      setIsLoadingModels(false)
    }
  }, [])

  const fetchWarnings = useCallback(async () => {
    try {
      const data = await admin.models.getWarnings()
      setWarnings(data.warnings)
    } catch {
      // Non-critical, silently ignore
    }
  }, [])

  useEffect(() => {
    if (user?.is_admin) {
      fetchModels()
      fetchWarnings()
    }
  }, [user, fetchModels, fetchWarnings])

  // --- Create Model ---
  const handleCreateModel = async (e: React.FormEvent) => {
    e.preventDefault()
    setModelsError('')

    if (!createModelForm.model_id.trim() || !createModelForm.display_name.trim()) {
      setModelsError('Model ID and Display Name are required')
      return
    }

    try {
      setIsCreatingModel(true)
      await admin.models.create({
        provider: createModelForm.provider,
        model_id: createModelForm.model_id.trim(),
        display_name: createModelForm.display_name.trim(),
        context_window: createModelForm.context_window ? parseInt(createModelForm.context_window) : undefined,
        max_output_tokens: createModelForm.max_output_tokens ? parseInt(createModelForm.max_output_tokens) : undefined,
        supports_vision: createModelForm.supports_vision,
        supports_function_calling: createModelForm.supports_function_calling,
        input_cost_per_1m_cents: parseInt(createModelForm.input_cost_per_1m_cents) || 0,
        output_cost_per_1m_cents: parseInt(createModelForm.output_cost_per_1m_cents) || 0,
        margin_multiplier: parseFloat(createModelForm.margin_multiplier) || 1.30,
        is_custom: true,
      })
      setCreateModelForm({
        provider: 'openai_compatible',
        model_id: '',
        display_name: '',
        context_window: '',
        max_output_tokens: '',
        supports_vision: false,
        supports_function_calling: false,
        input_cost_per_1m_cents: '0',
        output_cost_per_1m_cents: '0',
        margin_multiplier: '1.30',
      })
      setShowCreateModel(false)
      setModelsSuccess('Model created')
      fetchModels()
      fetchWarnings()
      setTimeout(() => setModelsSuccess(''), 3000)
    } catch (err: unknown) {
      const errorMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create model'
      setModelsError(errorMsg)
    } finally {
      setIsCreatingModel(false)
    }
  }

  const confirmDeleteModel = async () => {
    if (!deleteTarget) return
    try {
      await admin.models.delete(deleteTarget.id)
      setModelsSuccess('Model deactivated')
      setDeleteTarget(null)
      setAffectedKeys([])
      fetchModels()
      fetchWarnings()
      setTimeout(() => setModelsSuccess(''), 3000)
    } catch {
      setModelsError('Failed to delete model')
      setDeleteTarget(null)
      setAffectedKeys([])
    }
  }

  // --- Edit Model ---
  const startEditing = (row: LLMModel) => {
    setEditingId(row.id)
    setEditForm({
      model_id: row.model_id,
      display_name: row.display_name,
      context_window: row.context_window?.toString() || '',
      max_output_tokens: row.max_output_tokens?.toString() || '',
      supports_vision: row.supports_vision,
      supports_function_calling: row.supports_function_calling,
      input_cost_per_1m_cents: row.input_cost_per_1m_cents,
      output_cost_per_1m_cents: row.output_cost_per_1m_cents,
      margin_multiplier: row.margin_multiplier,
      is_active: row.is_active,
    })
  }

  const cancelEditing = () => {
    setEditingId(null)
  }

  const handleSaveModel = async (row: LLMModel) => {
    try {
      setIsSavingModel(true)
      await admin.models.update(row.id, {
        model_id: editForm.model_id || undefined,
        display_name: editForm.display_name || undefined,
        context_window: editForm.context_window ? parseInt(editForm.context_window) : undefined,
        max_output_tokens: editForm.max_output_tokens ? parseInt(editForm.max_output_tokens) : undefined,
        supports_vision: editForm.supports_vision,
        supports_function_calling: editForm.supports_function_calling,
        input_cost_per_1m_cents: editForm.input_cost_per_1m_cents,
        output_cost_per_1m_cents: editForm.output_cost_per_1m_cents,
        margin_multiplier: editForm.margin_multiplier,
        is_active: editForm.is_active,
      })
      setEditingId(null)
      setModelsSuccess('Model updated')
      fetchModels()
      fetchWarnings()
      setTimeout(() => setModelsSuccess(''), 3000)
    } catch {
      setModelsError('Failed to update model')
    } finally {
      setIsSavingModel(false)
    }
  }

  const formatContextWindow = (ctx?: number) => {
    if (!ctx) return '-'
    if (ctx >= 1000000) return `${(ctx / 1000000).toFixed(1)}M`
    return `${Math.round(ctx / 1000)}K`
  }

  const filteredModels = searchQuery.trim()
    ? modelRegistry.filter(m => {
        const q = searchQuery.toLowerCase()
        return m.model_id.toLowerCase().includes(q) || m.display_name.toLowerCase().includes(q) || m.provider.toLowerCase().includes(q)
      })
    : modelRegistry
  const totalModels = filteredModels.length
  const totalPages = Math.ceil(totalModels / pageSize)
  const startIdx = (page - 1) * pageSize
  const endIdx = Math.min(startIdx + pageSize, totalModels)
  const paginatedModels = filteredModels.slice(startIdx, endIdx)

  const inputStyle = {
    backgroundColor: 'var(--app-bg-input)',
    border: '1px solid var(--app-border-default)',
    color: 'var(--app-text-primary)',
  }

  return (
    <div>
      {/* $0 Pricing Warning */}
      {warnings.length > 0 && (
        <div className="mb-6 p-4 rounded-xl text-sm" style={{ backgroundColor: 'var(--app-alert-warning-bg)', border: '1px solid var(--app-alert-warning-border)', color: 'var(--app-accent-warning)' }}>
          <div className="font-medium mb-1">Models with $0 pricing (users won&apos;t be charged):</div>
          <ul className="list-disc list-inside">
            {warnings.map((w) => (
              <li key={`${w.provider}/${w.model_id}`}>
                {w.display_name} <span className="font-mono text-xs opacity-75">({w.provider}/{w.model_id})</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Model Registry & Pricing */}
      <div className="rounded-xl overflow-hidden" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-default)' }}>
        <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
          <div>
            <h2 className="text-lg font-medium" style={{ color: 'var(--app-text-primary)' }}>
              Model Registry &amp; Pricing
            </h2>
            <p className="mt-1 text-sm" style={{ color: 'var(--app-text-muted)' }}>
              All LLM models with capabilities and pricing. Add new models or edit existing ones.
            </p>
          </div>
          <button
            onClick={() => setShowCreateModel(!showCreateModel)}
            className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
            style={{ background: 'var(--app-gradient-primary)' }}
          >
            {showCreateModel ? 'Cancel' : 'Add Model'}
          </button>
        </div>

        {/* Search */}
        <div className="mx-6 mt-4 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--app-text-muted)' }} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setPage(1) }}
            placeholder="Search by model ID, display name, or provider..."
            className="w-full pl-9 pr-3 py-2 rounded-lg text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-border-focus)]"
            style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
          />
        </div>

        {/* Messages */}
        {modelsError && (
          <div className="mx-6 mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-error-bg)', color: 'var(--app-accent-error)' }}>
            {modelsError}
            <button onClick={() => setModelsError('')} className="ml-2 underline">dismiss</button>
          </div>
        )}
        {modelsSuccess && (
          <div className="mx-6 mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'var(--app-alert-success-bg)', border: '1px solid var(--app-alert-success-border)', color: 'var(--app-accent-success)' }}>
            {modelsSuccess}
          </div>
        )}

        {/* Create Model Form */}
        {showCreateModel && (
          <div className="mx-6 mt-4 mb-2 p-5 rounded-xl" style={{ backgroundColor: 'var(--app-bg-tertiary)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--app-text-primary)' }}>Add New Model</h3>
            <form onSubmit={handleCreateModel} className="space-y-3">
              {/* Row 1: Provider, Model ID, Display Name */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Provider</label>
                  <select
                    value={createModelForm.provider}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, provider: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  >
                    {PROVIDERS.map(p => (
                      <option key={p} value={p}>{p === 'openai_compatible' ? 'OpenAI Compatible' : p.charAt(0).toUpperCase() + p.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Model ID</label>
                  <input
                    type="text"
                    value={createModelForm.model_id}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, model_id: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                    placeholder="e.g., deepseek-r1:7b"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Display Name</label>
                  <input
                    type="text"
                    value={createModelForm.display_name}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, display_name: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                    placeholder="e.g., DeepSeek R1 7B"
                    required
                  />
                </div>
              </div>

              {/* Row 2: Capabilities */}
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Context Window</label>
                  <input
                    type="number"
                    value={createModelForm.context_window}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, context_window: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                    placeholder="e.g., 128000"
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Max Output Tokens</label>
                  <input
                    type="number"
                    value={createModelForm.max_output_tokens}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, max_output_tokens: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                    placeholder="e.g., 16384"
                  />
                </div>
                <div className="flex items-end gap-4 pb-1">
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
                    <input
                      type="checkbox"
                      checked={createModelForm.supports_vision}
                      onChange={(e) => setCreateModelForm({ ...createModelForm, supports_vision: e.target.checked })}
                      className="rounded"
                    />
                    Vision
                  </label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
                    <input
                      type="checkbox"
                      checked={createModelForm.supports_function_calling}
                      onChange={(e) => setCreateModelForm({ ...createModelForm, supports_function_calling: e.target.checked })}
                      className="rounded"
                    />
                    Tools
                  </label>
                </div>
              </div>

              {/* Row 3: Pricing */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Input Cost/1M (cents)</label>
                  <input
                    type="number"
                    value={createModelForm.input_cost_per_1m_cents}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, input_cost_per_1m_cents: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Output Cost/1M (cents)</label>
                  <input
                    type="number"
                    value={createModelForm.output_cost_per_1m_cents}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, output_cost_per_1m_cents: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1" style={{ color: 'var(--app-text-muted)' }}>Margin Multiplier</label>
                  <input
                    type="number"
                    step="0.01"
                    value={createModelForm.margin_multiplier}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, margin_multiplier: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isCreatingModel}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors disabled:opacity-50"
                style={{ background: 'var(--app-gradient-primary)' }}
              >
                {isCreatingModel ? 'Creating...' : 'Create Model'}
              </button>
            </form>
          </div>
        )}

        {/* Table */}
        {isLoadingModels ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>Loading...</div>
        ) : modelRegistry.length === 0 ? (
          <div className="p-8 text-center" style={{ color: 'var(--app-text-muted)' }}>No models in registry. Click &quot;Add Model&quot; to get started.</div>
        ) : (
          <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Provider</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Model ID</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Display Name</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Capabilities</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Input/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Output/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Margin</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Active</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedModels.map((row) => (
                  <tr key={row.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    {editingId === row.id ? (
                      <>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.provider}</td>
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            value={editForm.model_id}
                            onChange={(e) => setEditForm({ ...editForm, model_id: e.target.value })}
                            className="w-full px-2 py-1 rounded text-sm font-mono focus:outline-none"
                            style={inputStyle}
                            placeholder="model_id"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            value={editForm.display_name}
                            onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                            className="w-full px-2 py-1 rounded text-sm focus:outline-none"
                            style={inputStyle}
                            placeholder="Display name"
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-1.5">
                            <div className="flex gap-2">
                              <input
                                type="number"
                                value={editForm.context_window}
                                onChange={(e) => setEditForm({ ...editForm, context_window: e.target.value })}
                                className="w-24 px-2 py-1 rounded text-xs focus:outline-none"
                                style={inputStyle}
                                placeholder="ctx"
                                title="Context window"
                              />
                              <input
                                type="number"
                                value={editForm.max_output_tokens}
                                onChange={(e) => setEditForm({ ...editForm, max_output_tokens: e.target.value })}
                                className="w-24 px-2 py-1 rounded text-xs focus:outline-none"
                                style={inputStyle}
                                placeholder="out"
                                title="Max output tokens"
                              />
                            </div>
                            <div className="flex gap-3">
                              <label className="flex items-center gap-1 text-xs cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
                                <input
                                  type="checkbox"
                                  checked={editForm.supports_vision}
                                  onChange={(e) => setEditForm({ ...editForm, supports_vision: e.target.checked })}
                                  className="rounded"
                                />
                                vision
                              </label>
                              <label className="flex items-center gap-1 text-xs cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
                                <input
                                  type="checkbox"
                                  checked={editForm.supports_function_calling}
                                  onChange={(e) => setEditForm({ ...editForm, supports_function_calling: e.target.checked })}
                                  className="rounded"
                                />
                                tools
                              </label>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="1"
                            value={editForm.input_cost_per_1m_cents}
                            onChange={(e) => setEditForm({ ...editForm, input_cost_per_1m_cents: parseInt(e.target.value) || 0 })}
                            className="w-24 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={inputStyle}
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="1"
                            value={editForm.output_cost_per_1m_cents}
                            onChange={(e) => setEditForm({ ...editForm, output_cost_per_1m_cents: parseInt(e.target.value) || 0 })}
                            className="w-24 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={inputStyle}
                          />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <input
                            type="number"
                            step="0.01"
                            value={editForm.margin_multiplier}
                            onChange={(e) => setEditForm({ ...editForm, margin_multiplier: parseFloat(e.target.value) || 1 })}
                            className="w-20 px-2 py-1 rounded text-sm text-right focus:outline-none"
                            style={inputStyle}
                          />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            type="button"
                            className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
                            style={{ backgroundColor: editForm.is_active ? 'var(--app-accent-success)' : 'var(--app-text-muted)', opacity: 0.85 }}
                            onClick={() => setEditForm({ ...editForm, is_active: !editForm.is_active })}
                          >
                            <span
                              className="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform"
                              style={{ transform: editForm.is_active ? 'translateX(18px)' : 'translateX(3px)' }}
                            />
                          </button>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => handleSaveModel(row)}
                              disabled={isSavingModel}
                              className="px-2 py-1 rounded text-xs text-white transition-colors disabled:opacity-50"
                              style={{ background: 'var(--app-gradient-primary)' }}
                            >
                              {isSavingModel ? 'Saving...' : 'Save'}
                            </button>
                            <button
                              onClick={cancelEditing}
                              className="px-2 py-1 rounded text-xs transition-colors"
                              style={{ color: 'var(--app-text-muted)' }}
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.provider}</td>
                        <td className="px-4 py-3">
                          <div className="font-mono text-sm" style={{ color: 'var(--app-text-primary)' }}>{row.model_id}</div>
                        </td>
                        <td className="px-4 py-3">
                          <div style={{ color: 'var(--app-text-primary)' }}>{row.display_name}</div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="flex flex-wrap gap-1 justify-center">
                            {row.context_window && (
                              <span className="px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--app-alert-indigo-bg)', color: 'var(--app-accent-indigo)' }}>
                                {formatContextWindow(row.context_window)}
                              </span>
                            )}
                            {row.max_output_tokens && (
                              <span className="px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--app-alert-info-bg)', color: 'var(--app-accent-info)' }}>
                                out:{formatContextWindow(row.max_output_tokens)}
                              </span>
                            )}
                            {row.supports_vision && (
                              <span className="px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--app-alert-success-bg)', color: 'var(--app-accent-success)' }}>
                                vision
                              </span>
                            )}
                            {row.supports_function_calling && (
                              <span className="px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: 'var(--app-alert-warning-bg)', color: 'var(--app-accent-warning)' }}>
                                tools
                              </span>
                            )}
                            {row.is_custom && (
                              <span className="px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: 'rgba(139, 92, 246, 0.15)', color: 'var(--app-accent-indigo)' }}>
                                custom
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: row.input_cost_per_1m_cents === 0 && row.output_cost_per_1m_cents === 0 ? '#f59e0b' : 'var(--app-text-secondary)' }}>
                          {row.input_cost_per_1m_cents}
                        </td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: row.input_cost_per_1m_cents === 0 && row.output_cost_per_1m_cents === 0 ? '#f59e0b' : 'var(--app-text-secondary)' }}>
                          {row.output_cost_per_1m_cents}
                        </td>
                        <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--app-text-secondary)' }}>
                          {row.margin_multiplier.toFixed(2)}x
                        </td>
                        <td className="px-4 py-3 text-center">
                          <button
                            className="relative inline-flex h-5 w-9 items-center rounded-full transition-colors"
                            style={{ backgroundColor: row.is_active ? 'var(--app-accent-success)' : 'var(--app-text-muted)', opacity: 0.85 }}
                            title={row.is_active ? 'Active' : 'Inactive'}
                            onClick={() => {
                              admin.models.update(row.id, { is_active: !row.is_active }).then(() => {
                                fetchModels()
                                fetchWarnings()
                              })
                            }}
                          >
                            <span
                              className="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform"
                              style={{ transform: row.is_active ? 'translateX(18px)' : 'translateX(3px)' }}
                            />
                          </button>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-1.5 justify-end">
                            <button
                              onClick={() => startEditing(row)}
                              className="p-1.5 rounded-lg transition-colors"
                              style={{ color: 'var(--app-text-muted)' }}
                              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'; e.currentTarget.style.color = 'var(--app-text-primary)' }}
                              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--app-text-muted)' }}
                              title="Edit"
                            >
                              <Edit3 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => openDeleteModal(row)}
                              className="p-1.5 rounded-lg transition-colors"
                              style={{ color: 'var(--app-text-muted)' }}
                              onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-alert-error-bg)'; e.currentTarget.style.color = 'var(--app-accent-error)' }}
                              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--app-text-muted)' }}
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalModels > 0 && (
            <div className="px-4 py-3 flex items-center justify-between" style={{ borderTop: '1px solid var(--app-border-default)' }}>
              <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                Showing {startIdx + 1}-{endIdx} of {totalModels}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 rounded-lg text-xs disabled:opacity-30"
                  style={{
                    backgroundColor: 'var(--app-bg-tertiary)',
                    color: 'var(--app-text-secondary)',
                    border: '1px solid var(--app-border-default)',
                  }}
                >
                  Prev
                </button>
                <span className="px-3 py-1.5 text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page >= totalPages}
                  className="px-3 py-1.5 rounded-lg text-xs disabled:opacity-30"
                  style={{
                    backgroundColor: 'var(--app-bg-tertiary)',
                    color: 'var(--app-text-secondary)',
                    border: '1px solid var(--app-border-default)',
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          )}
          </>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)' }}>
          <div
            className="w-full max-w-md rounded-xl p-6 shadow-2xl"
            style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg" style={{ backgroundColor: 'var(--app-alert-error-bg)' }}>
                <Trash2 className="w-5 h-5" style={{ color: 'var(--app-accent-error)' }} />
              </div>
              <h3 className="text-lg font-medium" style={{ color: 'var(--app-text-primary)' }}>
                Deactivate Model
              </h3>
            </div>
            <p className="text-sm mb-1" style={{ color: 'var(--app-text-secondary)' }}>
              Are you sure you want to deactivate this model?
            </p>
            <p className="text-sm font-medium mb-1" style={{ color: 'var(--app-text-primary)' }}>
              {deleteTarget.display_name}
            </p>
            <p className="text-xs font-mono mb-4" style={{ color: 'var(--app-text-muted)' }}>
              {deleteTarget.provider} / {deleteTarget.model_id}
            </p>
            {affectedKeys.length > 0 && (
              <div
                className="mb-5 p-3 rounded-lg text-sm"
                style={{ backgroundColor: 'var(--app-alert-warning-bg)', border: '1px solid var(--app-alert-warning-border)' }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4" style={{ color: 'var(--app-accent-warning)' }} />
                  <span className="font-medium" style={{ color: 'var(--app-accent-warning)' }}>
                    {affectedKeys.length} active platform key{affectedKeys.length !== 1 ? 's' : ''} use{affectedKeys.length === 1 ? 's' : ''} this model
                  </span>
                </div>
                <ul className="space-y-1 ml-6">
                  {affectedKeys.map(k => (
                    <li key={k.id} className="text-xs" style={{ color: 'var(--app-text-secondary)' }}>
                      <span className="font-medium" style={{ color: 'var(--app-text-primary)' }}>{k.label}</span>
                      {k.is_default && (
                        <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs font-medium" style={{ backgroundColor: 'var(--app-alert-indigo-bg)', color: 'var(--app-accent-indigo)' }}>
                          DEFAULT
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="text-xs mt-2" style={{ color: 'var(--app-text-muted)' }}>
                  Deactivating will make {affectedKeys.length === 1 ? 'this key' : 'these keys'} non-functional.
                </p>
              </div>
            )}
            {affectedKeys.length === 0 && <div className="mb-5" />}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setDeleteTarget(null); setAffectedKeys([]) }}
                className="px-4 py-2 rounded-lg text-sm transition-colors"
                style={{
                  backgroundColor: 'var(--app-bg-tertiary)',
                  color: 'var(--app-text-secondary)',
                  border: '1px solid var(--app-border-default)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteModel}
                className="px-4 py-2 rounded-lg text-sm text-white transition-colors"
                style={{ backgroundColor: 'var(--app-accent-error)' }}
              >
                Deactivate
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
