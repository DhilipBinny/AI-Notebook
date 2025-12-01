'use client'

import { useTheme, type NotebookTheme } from '@/contexts/ThemeContext'

interface NotebookToolbarProps {
  onAddCode: () => void
  onAddMarkdown: () => void
  onRunAll: () => void
  onClearOutputs: () => void
  onDeleteAllCells: () => void
  onSave: () => void
  onExport: () => void
  onSummarize: () => void
  isExporting: boolean
  isSummarizing: boolean
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
  onDeleteAllCells,
  onSave,
  onExport,
  onSummarize,
  isExporting,
  isSummarizing,
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
          title="Clear all cell outputs"
        >
          Clear Outputs
        </button>
        <button
          onClick={onDeleteAllCells}
          className="p-1.5 rounded-md transition-colors bg-red-600/80 hover:bg-red-500 text-white"
          title="Delete all cells"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
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

        {/* Keyboard shortcuts button with hover tooltip */}
        <div className="relative group ml-2">
          <button
            className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-white/5 border border-white/10 hover:bg-white/10 transition-colors"
            title="Keyboard shortcuts"
          >
            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span className="text-xs text-gray-400">Shortcuts</span>
          </button>

          {/* Dropdown on hover */}
          <div className="absolute top-full left-0 mt-1 w-56 py-2 rounded-lg bg-gray-800 border border-gray-700 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-700 mb-1">Keyboard Shortcuts</div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Run cell</span>
              <div className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Shift</kbd>
                <span className="text-[10px] text-gray-500">+</span>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Enter</kbd>
              </div>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Save notebook</span>
              <div className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Ctrl</kbd>
                <span className="text-[10px] text-gray-500">+</span>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">S</kbd>
              </div>
            </div>
          </div>
        </div>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Save status button */}
        <button
          onClick={onSave}
          disabled={isSaving}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors flex items-center gap-1.5 ${
            isSaving
              ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
              : isDirty
              ? 'bg-blue-600 hover:bg-blue-500 text-white'
              : 'bg-gray-700 text-green-400'
          }`}
          title={isSaving ? 'Saving...' : isDirty ? 'Save notebook (Ctrl+S)' : 'Notebook saved'}
        >
          {isSaving ? (
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : isDirty ? (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          {isSaving ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
        </button>
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

        {/* Summarize button - AI Sparkles icon */}
        <button
          onClick={onSummarize}
          disabled={isSummarizing}
          className="px-3 py-1.5 rounded-md transition-colors flex items-center gap-1.5 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-500 hover:to-pink-400 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          title="Generate AI summary of notebook"
        >
          {isSummarizing ? (
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
            </svg>
          )}
          <span className="text-sm font-medium">Summarize</span>
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
