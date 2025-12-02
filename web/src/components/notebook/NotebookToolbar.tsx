'use client'

import { useTheme, type NotebookTheme } from '@/contexts/ThemeContext'

interface NotebookToolbarProps {
  onAddCode: () => void
  onAddMarkdown: () => void
  onAddNotes: () => void
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
  showLogs: boolean
  onToggleLogs: () => void
  logsConnected: boolean
}

const themeOptions: { value: NotebookTheme; label: string; icon: string }[] = [
  { value: 'dark', label: 'Dark', icon: '🌙' },
  { value: 'light', label: 'Light', icon: '☀️' },
  { value: 'monokai', label: 'Monokai', icon: '🎨' },
]

export default function NotebookToolbar({
  onAddCode,
  onAddMarkdown,
  onAddNotes,
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
  showLogs,
  onToggleLogs,
  logsConnected,
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
        {/* Add cell buttons - gradient style */}
        <button
          onClick={onAddCode}
          className="px-3 py-1.5 text-sm rounded-lg transition-all flex items-center gap-1.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white shadow-md shadow-blue-500/20 hover:shadow-blue-500/30"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          Code
        </button>
        <button
          onClick={onAddMarkdown}
          className="px-3 py-1.5 text-sm rounded-lg transition-all flex items-center gap-1.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white shadow-md shadow-purple-500/20 hover:shadow-purple-500/30"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Markdown
        </button>
        <button
          onClick={onAddNotes}
          className="px-3 py-1.5 text-sm rounded-lg transition-all flex items-center gap-1.5 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white shadow-md shadow-amber-500/20 hover:shadow-amber-500/30"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Notes
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Run controls - gradient icon buttons */}
        <button
          onClick={onRunAll}
          className="p-2 rounded-lg transition-all bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-md shadow-emerald-500/20 hover:shadow-emerald-500/30"
          title="Run all cells"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
        </button>
        <button
          onClick={onClearOutputs}
          className="p-2 rounded-lg transition-all bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 text-white shadow-md shadow-amber-500/20 hover:shadow-amber-500/30"
          title="Clear all outputs"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M3 12l6.414 6.414a2 2 0 001.414.586H19a2 2 0 002-2V7a2 2 0 00-2-2h-8.172a2 2 0 00-1.414.586L3 12z" />
          </svg>
        </button>
        <button
          onClick={onDeleteAllCells}
          className="p-2 rounded-lg transition-all bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white shadow-md shadow-red-500/20 hover:shadow-red-500/30"
          title="Delete all cells"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Context count with select/deselect */}
        <div className="flex items-center gap-2">
          <div className="text-sm" style={{ color: 'var(--nb-text-muted)' }}>
            <span className="text-emerald-400 font-medium">{contextCount}</span>
            <span className="text-gray-500">/{totalCells}</span> in context
          </div>
          {contextCount < totalCells ? (
            <button
              onClick={onSelectAllContext}
              className="px-2.5 py-1 text-xs rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 transition-all"
              title="Select all cells for AI context"
            >
              Select All
            </button>
          ) : (
            <button
              onClick={onDeselectAllContext}
              className="px-2.5 py-1 text-xs rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 border border-white/10 transition-all"
              title="Deselect all cells from AI context"
            >
              Deselect All
            </button>
          )}
        </div>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Kernel restart - gradient */}
        <button
          onClick={onRestartKernel}
          className="p-2 rounded-lg transition-all bg-gradient-to-r from-red-600 to-pink-600 hover:from-red-500 hover:to-pink-500 text-white shadow-md shadow-red-500/20 hover:shadow-red-500/30"
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
          <div className="absolute top-full left-0 mt-1 w-72 py-2 rounded-lg bg-gray-800 border border-gray-700 shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-700 mb-1">Keyboard Shortcuts</div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Run cell & advance</span>
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

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Enter edit mode</span>
              <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Enter</kbd>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Exit edit mode</span>
              <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Esc</kbd>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Navigate cells</span>
              <div className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">↑</kbd>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">↓</kbd>
              </div>
            </div>

            <div className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-700 border-t mt-2 pt-2 mb-1">Code Editing</div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Toggle comment</span>
              <div className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Ctrl</kbd>
                <span className="text-[10px] text-gray-500">+</span>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">/</kbd>
              </div>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Indent</span>
              <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Tab</kbd>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Outdent</span>
              <div className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Shift</kbd>
                <span className="text-[10px] text-gray-500">+</span>
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-700 text-gray-300 border border-gray-600">Tab</kbd>
              </div>
            </div>

            <div className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-700 border-t mt-2 pt-2 mb-1">Mouse Actions</div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Resize notebook width</span>
              <span className="text-[10px] text-gray-400">Drag edges</span>
            </div>

            <div className="px-3 py-2 flex items-center justify-between hover:bg-white/5">
              <span className="text-sm text-gray-300">Insert cell</span>
              <span className="text-[10px] text-gray-400">Hover between cells</span>
            </div>
          </div>
        </div>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Save status button - gradient style */}
        <button
          onClick={onSave}
          disabled={isSaving}
          className={`px-3 py-1.5 text-sm rounded-lg transition-all flex items-center gap-1.5 text-white shadow-md ${
            isSaving
              ? 'bg-gray-600 cursor-not-allowed opacity-70'
              : isDirty
              ? 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 shadow-blue-500/20 hover:shadow-blue-500/30'
              : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20 hover:shadow-emerald-500/30'
          }`}
          title={isSaving ? 'Saving...' : isDirty ? 'Save notebook (Ctrl+S)' : 'Notebook saved'}
        >
          {isSaving ? (
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
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

        {/* Export button - gradient style */}
        <button
          onClick={onExport}
          disabled={isExporting}
          className="p-2 rounded-lg transition-all flex items-center justify-center bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white shadow-md shadow-cyan-500/20 hover:shadow-cyan-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Export as .ipynb"
        >
          {isExporting ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          )}
        </button>

        {/* Logs toggle button */}
        <button
          onClick={onToggleLogs}
          className={`p-2 rounded-lg transition-all flex items-center justify-center shadow-md relative ${
            showLogs
              ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-500/20 hover:shadow-emerald-500/30'
              : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10 shadow-none'
          }`}
          title={showLogs ? 'Hide Logs' : 'Show Logs'}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {/* Live indicator */}
          {showLogs && (
            <span className={`absolute -top-1 -right-1 w-2 h-2 rounded-full ${logsConnected ? 'bg-emerald-400' : 'bg-gray-500'}`} />
          )}
        </button>

        {/* Chat toggle button - gradient when active */}
        <button
          onClick={onToggleChat}
          className={`p-2 rounded-lg transition-all flex items-center justify-center shadow-md ${
            showChat
              ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-500/20 hover:shadow-blue-500/30'
              : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10 shadow-none'
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
