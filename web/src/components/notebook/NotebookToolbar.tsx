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
  isExporting: boolean
  contextCount: number
  totalCells: number
  onSelectAllContext: () => void
  onDeselectAllContext: () => void
  isDirty: boolean
  isSaving: boolean
  kernelStatus: 'connected' | 'connecting' | 'disconnected'
  onRestartKernel: () => void
  showChat: boolean
  onToggleChat: () => void
}

const themeOptions: { value: NotebookTheme; label: string; icon: string }[] = [
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'monokai', label: 'Monokai', icon: '🎨' },
]

// Theme-aware button colors
const buttonColors = {
  primary: { // Run All
    dark: { bg: '#3DF2A6', hover: '#5FF4B8', text: '#000' },
    light: { bg: '#00B86E', hover: '#00D47F', text: '#fff' },
    monokai: { bg: '#A6E22E', hover: '#B8E850', text: '#000' },
  },
  danger: { // Restart / Delete
    dark: { bg: '#FF5F72', hover: '#FF7A8A', text: '#fff' },
    light: { bg: '#E63946', hover: '#EF525E', text: '#fff' },
    monokai: { bg: '#F92672', hover: '#FA4D8A', text: '#fff' },
  },
  warning: { // Clear Outputs
    dark: { bg: '#FF9E4A', hover: '#FFB06A', text: '#000' },
    light: { bg: '#F48C06', hover: '#F9A825', text: '#000' },
    monokai: { bg: '#FD971F', hover: '#FDAB4A', text: '#000' },
  },
  code: { // Code button
    dark: { bg: '#5BA8FF', hover: '#7CBBFF', text: '#000' },
    light: { bg: '#1D6FE4', hover: '#3D85EA', text: '#fff' },
    monokai: { bg: '#66D9EF', hover: '#8AE3F3', text: '#000' },
  },
  markdown: { // Markdown button
    dark: { bg: '#BF7BFF', hover: '#CC99FF', text: '#000' },
    light: { bg: '#7B4DFF', hover: '#9570FF', text: '#fff' },
    monokai: { bg: '#AE81FF', hover: '#C29FFF', text: '#000' },
  },
  saved: { // Saved badge
    dark: { bg: '#2EC8C8', hover: '#4DD4D4', text: '#000' },
    light: { bg: '#0FB6A0', hover: '#2DC8B4', text: '#fff' },
    monokai: { bg: '#A6E22E', hover: '#B8E850', text: '#000' },
  },
}

export default function NotebookToolbar({
  onAddCode,
  onAddMarkdown,
  onRunAll,
  onClearOutputs,
  onDeleteAllCells,
  onSave,
  onExport,
  isExporting,
  contextCount,
  totalCells,
  onSelectAllContext,
  onDeselectAllContext,
  isDirty,
  isSaving,
  kernelStatus,
  onRestartKernel,
  showChat,
  onToggleChat,
}: NotebookToolbarProps) {
  const { theme, setTheme } = useTheme()

  // Get colors for current theme
  const getColors = (type: keyof typeof buttonColors) => buttonColors[type][theme]

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
          className="px-3 py-1.5 text-sm rounded-md transition-all flex items-center gap-1 hover:brightness-110"
          style={{ backgroundColor: getColors('code').bg, color: getColors('code').text }}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          Code
        </button>
        <button
          onClick={onAddMarkdown}
          className="px-3 py-1.5 text-sm rounded-md transition-all flex items-center gap-1 hover:brightness-110"
          style={{ backgroundColor: getColors('markdown').bg, color: getColors('markdown').text }}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Markdown
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Run controls - icon only */}
        <button
          onClick={onRunAll}
          className="p-1.5 rounded-md transition-all hover:brightness-110"
          style={{ backgroundColor: getColors('primary').bg, color: getColors('primary').text }}
          title="Run all cells"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
        <button
          onClick={onClearOutputs}
          className="p-1.5 rounded-md transition-all hover:brightness-110"
          style={{ backgroundColor: getColors('warning').bg, color: getColors('warning').text }}
          title="Clear all outputs"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" />
          </svg>
        </button>
        <button
          onClick={onDeleteAllCells}
          className="p-1.5 rounded-md transition-all hover:brightness-110"
          style={{ backgroundColor: getColors('danger').bg, color: getColors('danger').text }}
          title="Delete all cells"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Context count with select/deselect - moved to left side near cell controls */}
        <div className="flex items-center gap-2">
          <div className="text-sm" style={{ color: 'var(--nb-text-muted)' }}>
            <span className="text-green-400 font-medium">{contextCount}</span>
            <span className="text-gray-500">/{totalCells}</span> in context
          </div>
          {contextCount < totalCells ? (
            <button
              onClick={onSelectAllContext}
              className="px-2 py-1 text-xs rounded border border-green-500/50 text-green-400 hover:bg-green-500/20 transition-colors"
              title="Select all cells for AI context"
            >
              Select All
            </button>
          ) : (
            <button
              onClick={onDeselectAllContext}
              className="px-2 py-1 text-xs rounded border border-gray-500/50 text-gray-400 hover:bg-gray-500/20 transition-colors"
              title="Deselect all cells from AI context"
            >
              Deselect All
            </button>
          )}
        </div>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Kernel controls - icon only */}
        <button
          onClick={onRestartKernel}
          className="p-1.5 rounded-md transition-all hover:brightness-110"
          style={{ backgroundColor: getColors('danger').bg, color: getColors('danger').text }}
          title="Restart kernel (clears all variables)"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
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
          className={`px-3 py-1.5 text-sm rounded-md transition-all flex items-center gap-1.5 hover:brightness-110 ${
            isSaving ? 'cursor-not-allowed opacity-70' : ''
          }`}
          style={{
            backgroundColor: isSaving
              ? '#666'
              : isDirty
              ? getColors('code').bg
              : getColors('saved').bg,
            color: isSaving
              ? '#ccc'
              : isDirty
              ? getColors('code').text
              : getColors('saved').text,
          }}
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

        {/* Chat toggle button */}
        <button
          onClick={onToggleChat}
          className={`p-2 rounded-md transition-colors flex items-center justify-center ${
            showChat
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
              : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
          }`}
          title={showChat ? 'Hide AI Chat' : 'Show AI Chat'}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      </div>
    </div>
  )
}
