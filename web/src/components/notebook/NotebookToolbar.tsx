'use client'

import { useTheme, type NotebookTheme } from '@/contexts/ThemeContext'

interface NotebookToolbarProps {
  onAddCode: () => void
  onAddMarkdown: () => void
  onRunAll: () => void
  onClearOutputs: () => void
  onSave: () => void
  onExport: () => void
  isExporting: boolean
  contextCount: number
  isDirty: boolean
  isSaving: boolean
  kernelStatus: 'connected' | 'connecting' | 'disconnected'
  onRestartKernel: () => void
}

const themeOptions: { value: NotebookTheme; label: string; icon: string }[] = [
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'monokai', label: 'Monokai', icon: '🎨' },
]

export default function NotebookToolbar({
  onAddCode,
  onAddMarkdown,
  onRunAll,
  onClearOutputs,
  onSave,
  onExport,
  isExporting,
  contextCount,
  isDirty,
  isSaving,
  kernelStatus,
  onRestartKernel,
}: NotebookToolbarProps) {
  const { theme, setTheme } = useTheme()

  return (
    <div
      className="flex items-center justify-between px-4 py-2"
      style={{
        backgroundColor: 'var(--nb-bg-header)',
        borderBottom: '1px solid var(--nb-border-default)',
      }}
    >
      <div className="flex items-center gap-2">
        {/* Add cell buttons */}
        <button
          onClick={onAddCode}
          className="px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1 bg-blue-600 hover:bg-blue-500 text-white"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          Code
        </button>
        <button
          onClick={onAddMarkdown}
          className="px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1 bg-purple-600 hover:bg-purple-500 text-white"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Markdown
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Run controls */}
        <button
          onClick={onRunAll}
          className="px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1 bg-green-600 hover:bg-green-500 text-white"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          Run All
        </button>
        <button
          onClick={onClearOutputs}
          className="px-3 py-1.5 text-sm rounded-md transition-colors bg-gray-600 hover:bg-gray-500 text-white"
        >
          Clear Outputs
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Kernel controls */}
        <button
          onClick={onRestartKernel}
          className="px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1 bg-orange-600 hover:bg-orange-500 text-white"
          title="Restart kernel (clears all variables)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Restart
        </button>

        {/* Kernel status */}
        <div className="flex items-center gap-2 ml-2">
          <span
            className={`w-2 h-2 rounded-full ${
              kernelStatus === 'connected'
                ? 'bg-green-500'
                : kernelStatus === 'connecting'
                ? 'bg-yellow-500 animate-pulse'
                : 'bg-red-500'
            }`}
          />
          <span className="text-xs capitalize" style={{ color: 'var(--nb-text-muted)' }}>{kernelStatus}</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Theme selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>Theme:</span>
          <div className="flex rounded-md overflow-hidden border border-gray-600">
            {themeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setTheme(option.value)}
                className={`px-2 py-1 text-xs transition-colors ${
                  theme === option.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
                title={option.label}
              >
                {option.icon} {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="w-px h-6 bg-gray-600" />

        {/* Context count */}
        <div className="text-sm" style={{ color: 'var(--nb-text-muted)' }}>
          <span className="text-green-400 font-medium">{contextCount}</span> cells in AI context
        </div>

        {/* Save button */}
        <button
          onClick={onSave}
          disabled={isSaving}
          className={`p-2 rounded-md transition-colors flex items-center justify-center ${
            isDirty
              ? 'bg-blue-600 hover:bg-blue-500 text-white'
              : 'bg-gray-600 text-gray-300'
          } ${isSaving ? 'opacity-50 cursor-not-allowed' : ''}`}
          title={isSaving ? 'Saving...' : isDirty ? 'Save notebook (Ctrl+S)' : 'Notebook saved'}
        >
          {isSaving ? (
            <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          )}
        </button>

        {/* Export button */}
        <button
          onClick={onExport}
          disabled={isExporting}
          className="p-2 rounded-md transition-colors flex items-center justify-center bg-cyan-600 hover:bg-cyan-500 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          title="Export as .ipynb"
        >
          {isExporting ? (
            <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
