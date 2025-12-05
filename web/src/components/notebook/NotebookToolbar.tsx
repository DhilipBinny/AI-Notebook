'use client'

import { useTheme } from '@/contexts/ThemeContext'

interface NotebookToolbarProps {
  onAddCode: () => void
  onAddMarkdown: () => void
  onAddAI: () => void
  onRunAll: () => void
  onClearOutputs: () => void
  onDeleteAllCells: () => void
  onSave: () => void
  onExport: () => void
  isExporting: boolean
  totalCells: number
  isDirty: boolean
  isSaving: boolean
  kernelStatus: 'connected' | 'connecting' | 'disconnected'
  onRestartKernel: () => void
  showChat: boolean
  onToggleChat: () => void
  onOpenLogs: () => void
  onOpenTerminal: () => void
}


export default function NotebookToolbar({
  onAddCode,
  onAddMarkdown,
  onAddAI,
  onRunAll,
  onClearOutputs,
  onDeleteAllCells,
  onSave,
  onExport,
  isExporting,
  totalCells,
  isDirty,
  isSaving,
  kernelStatus,
  onRestartKernel,
  showChat,
  onToggleChat,
  onOpenLogs,
  onOpenTerminal,
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
          onClick={onAddAI}
          className="px-3 py-1.5 text-sm rounded-lg transition-all flex items-center gap-1.5 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 text-white shadow-md shadow-violet-500/20 hover:shadow-violet-500/30"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          AI
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

        {/* Cell count indicator */}
        <div className="text-sm" style={{ color: 'var(--nb-text-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--nb-accent-success)' }}>{totalCells}</span> cells
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
            className="flex items-center gap-1.5 px-2 py-1.5 rounded transition-colors"
            style={{
              backgroundColor: 'var(--app-bg-card)',
              border: '1px solid var(--nb-border-default)',
            }}
            title="Keyboard shortcuts"
          >
            <svg className="w-4 h-4" style={{ color: 'var(--nb-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>Shortcuts</span>
          </button>

          {/* Dropdown on hover - Two column layout */}
          <div
            className="absolute top-full left-0 mt-1 w-[520px] p-3 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50"
            style={{
              backgroundColor: 'var(--nb-bg-secondary)',
              border: '1px solid var(--nb-border-default)',
            }}
          >
            <div className="grid grid-cols-2 gap-4">
              {/* Left Column */}
              <div>
                <div className="text-xs font-medium pb-1 mb-2" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Navigation & Execution</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Run cell & advance</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>⇧</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↵</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Save notebook</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Ctrl</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>S</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Enter edit mode</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↵</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Exit edit mode</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Esc</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Navigate cells</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↑</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↓</kbd>
                    </div>
                  </div>
                </div>

                <div className="text-xs font-medium pb-1 mb-2 mt-3" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Cell Type</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>To code</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Y</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>To markdown</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>M</kbd>
                  </div>
                </div>

                <div className="text-xs font-medium pb-1 mb-2 mt-3" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Code Editing</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Toggle comment</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Ctrl</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>/</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Indent</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Tab</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Outdent</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>⇧</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Tab</kbd>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column */}
              <div>
                <div className="text-xs font-medium pb-1 mb-2" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Cell Manipulation</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Insert above</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>A</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Insert below</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>B</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Delete cell</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>D</kbd>
                      <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>D</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Cut cell</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>X</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Copy cell</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>C</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Paste below</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>V</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Undo delete</span>
                    <kbd className="px-1 py-0.5 text-[9px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Z</kbd>
                  </div>
                </div>

                <div className="text-xs font-medium pb-1 mb-2 mt-3" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Mouse Actions</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Resize width</span>
                    <span className="text-[9px]" style={{ color: 'var(--nb-text-muted)' }}>Drag edges</span>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Insert cell</span>
                    <span className="text-[9px]" style={{ color: 'var(--nb-text-muted)' }}>Hover between</span>
                  </div>
                </div>
              </div>
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
        {/* Theme toggle - Sun/Moon button */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="relative p-2 rounded-xl transition-all duration-300 ease-in-out group"
          style={{
            backgroundColor: theme === 'dark' ? 'rgba(30, 41, 59, 0.8)' : 'rgba(251, 191, 36, 0.15)',
            border: `1px solid ${theme === 'dark' ? 'rgba(71, 85, 105, 0.5)' : 'rgba(251, 191, 36, 0.4)'}`,
            boxShadow: theme === 'dark'
              ? '0 0 10px rgba(99, 102, 241, 0.1)'
              : '0 0 15px rgba(251, 191, 36, 0.3)',
          }}
          title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          <div className="relative w-5 h-5">
            {/* Sun icon */}
            <svg
              className={`absolute inset-0 w-5 h-5 transition-all duration-300 ${
                theme === 'dark'
                  ? 'opacity-0 rotate-90 scale-50'
                  : 'opacity-100 rotate-0 scale-100'
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              style={{ color: '#f59e0b' }}
            >
              <circle cx="12" cy="12" r="4" fill="currentColor" />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"
              />
            </svg>
            {/* Moon icon */}
            <svg
              className={`absolute inset-0 w-5 h-5 transition-all duration-300 ${
                theme === 'dark'
                  ? 'opacity-100 rotate-0 scale-100'
                  : 'opacity-0 -rotate-90 scale-50'
              }`}
              fill="currentColor"
              viewBox="0 0 24 24"
              style={{ color: '#a5b4fc' }}
            >
              <path d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
            </svg>
          </div>
        </button>

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

        {/* Logs button - opens in new tab */}
        <button
          onClick={onOpenLogs}
          className="p-2 rounded-lg transition-all flex items-center justify-center shadow-md hover:opacity-80"
          style={{
            backgroundColor: 'var(--app-bg-card)',
            border: '1px solid var(--nb-border-default)',
            color: 'var(--nb-text-muted)',
          }}
          title="Open Logs (new tab)"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </button>

        {/* Terminal button - opens in new tab */}
        <button
          onClick={onOpenTerminal}
          className="p-2 rounded-lg transition-all flex items-center justify-center shadow-md hover:opacity-80"
          style={{
            backgroundColor: 'var(--app-bg-card)',
            border: '1px solid var(--nb-border-default)',
            color: 'var(--nb-text-muted)',
          }}
          title="Open Terminal (new tab)"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </button>

        {/* Chat toggle button - gradient when active */}
        <button
          onClick={onToggleChat}
          className="p-2 rounded-lg transition-all flex items-center justify-center shadow-md"
          style={showChat ? {
            background: 'var(--app-gradient-primary)',
            color: '#ffffff',
          } : {
            backgroundColor: 'var(--app-bg-card)',
            border: '1px solid var(--nb-border-default)',
            color: 'var(--nb-text-muted)',
          }}
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
