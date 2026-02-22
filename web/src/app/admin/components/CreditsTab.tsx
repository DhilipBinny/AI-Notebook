'use client'

import { useState, useEffect, useCallback } from 'react'
import { admin, credits } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { LLMModel } from '@/types'

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

  const user = useAuthStore((state) => state.user)

  const fetchModels = useCallback(async () => {
    try {
      setIsLoadingModels(true)
      const data = await credits.getPricing()
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

  const handleDeleteModel = async (row: LLMModel) => {
    if (!confirm(`Delete model "${row.display_name}" (${row.provider}/${row.model_id})?`)) return
    try {
      await admin.models.delete(row.id)
      setModelsSuccess(row.is_custom ? 'Model deleted' : 'Model deactivated')
      fetchModels()
      fetchWarnings()
      setTimeout(() => setModelsSuccess(''), 3000)
    } catch {
      setModelsError('Failed to delete model')
    }
  }

  // --- Edit Model ---
  const startEditing = (row: LLMModel) => {
    setEditingId(row.id)
    setEditForm({
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

  const inputStyle = {
    backgroundColor: 'var(--app-bg-input)',
    border: '1px solid var(--app-border-default)',
    color: 'var(--app-text-primary)',
  }

  return (
    <div>
      {/* $0 Pricing Warning */}
      {warnings.length > 0 && (
        <div className="mb-6 p-4 rounded-xl text-sm" style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#f59e0b' }}>
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

        {/* Messages */}
        {modelsError && (
          <div className="mx-6 mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'var(--app-accent-error)' }}>
            {modelsError}
            <button onClick={() => setModelsError('')} className="ml-2 underline">dismiss</button>
          </div>
        )}
        {modelsSuccess && (
          <div className="mx-6 mt-4 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Provider</label>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Model ID</label>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Display Name</label>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Context Window</label>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Max Output Tokens</label>
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
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Input Cost/1M (cents)</label>
                  <input
                    type="number"
                    value={createModelForm.input_cost_per_1m_cents}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, input_cost_per_1m_cents: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Output Cost/1M (cents)</label>
                  <input
                    type="number"
                    value={createModelForm.output_cost_per_1m_cents}
                    onChange={(e) => setCreateModelForm({ ...createModelForm, output_cost_per_1m_cents: e.target.value })}
                    className="w-full px-2 py-1.5 rounded text-sm focus:outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-xs mb-1" style={{ color: 'var(--app-text-muted)' }}>Margin Multiplier</label>
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Provider</th>
                  <th className="text-left px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Model</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Capabilities</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Input/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Output/1M</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Margin</th>
                  <th className="text-center px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Active</th>
                  <th className="text-right px-4 py-3 font-medium" style={{ color: 'var(--app-text-secondary)' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {modelRegistry.map((row) => (
                  <tr key={row.id} style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    {editingId === row.id ? (
                      <>
                        <td className="px-4 py-3" style={{ color: 'var(--app-text-primary)' }}>{row.provider}</td>
                        <td className="px-4 py-3">
                          <input
                            type="text"
                            value={editForm.display_name}
                            onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                            className="w-full px-2 py-1 rounded text-sm focus:outline-none mb-1"
                            style={inputStyle}
                          />
                          <div className="font-mono text-xs" style={{ color: 'var(--app-text-muted)' }}>{row.model_id}</div>
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
                              <label className="flex items-center gap-1 text-[10px] cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
                                <input
                                  type="checkbox"
                                  checked={editForm.supports_vision}
                                  onChange={(e) => setEditForm({ ...editForm, supports_vision: e.target.checked })}
                                  className="rounded"
                                />
                                vision
                              </label>
                              <label className="flex items-center gap-1 text-[10px] cursor-pointer" style={{ color: 'var(--app-text-secondary)' }}>
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
                          <input
                            type="checkbox"
                            checked={editForm.is_active}
                            onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                            className="rounded"
                          />
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
                          <div style={{ color: 'var(--app-text-primary)' }}>{row.display_name}</div>
                          <div className="font-mono text-xs" style={{ color: 'var(--app-text-muted)' }}>{row.model_id}</div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="flex flex-wrap gap-1 justify-center">
                            {row.context_window && (
                              <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'rgba(99, 102, 241, 0.15)', color: '#818cf8' }}>
                                {formatContextWindow(row.context_window)}
                              </span>
                            )}
                            {row.max_output_tokens && (
                              <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
                                out:{formatContextWindow(row.max_output_tokens)}
                              </span>
                            )}
                            {row.supports_vision && (
                              <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
                                vision
                              </span>
                            )}
                            {row.supports_function_calling && (
                              <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                                tools
                              </span>
                            )}
                            {row.is_custom && (
                              <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ backgroundColor: 'rgba(139, 92, 246, 0.15)', color: '#a78bfa' }}>
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
                          <span
                            className="px-2 py-0.5 rounded text-xs font-medium"
                            style={{ color: row.is_active ? '#10b981' : 'var(--app-text-muted)' }}
                          >
                            {row.is_active ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex gap-2 justify-end">
                            <button
                              onClick={() => startEditing(row)}
                              className="px-2 py-1 rounded text-xs transition-colors"
                              style={{
                                backgroundColor: 'var(--app-bg-tertiary)',
                                color: 'var(--app-text-secondary)',
                                border: '1px solid var(--app-border-default)',
                              }}
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteModel(row)}
                              className="px-2 py-1 rounded text-xs transition-colors"
                              style={{ color: 'var(--app-accent-error)' }}
                            >
                              {row.is_custom ? 'Delete' : 'Deactivate'}
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
        )}
      </div>
    </div>
  )
}
