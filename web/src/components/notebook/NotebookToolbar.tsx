'use client'

import { useState, useEffect, useRef } from 'react'
import { useTheme, densityOptions, DensityMode } from '@/contexts/ThemeContext'
import {
  Code,
  FileText,
  Lightbulb,
  Play,
  Eraser,
  Trash2,
  RefreshCw,
  Square,
  Monitor,
  Save,
  Check,
  Download,
  ChevronDown,
  MessageSquare,
  Terminal,
  Sparkles,
  Bot,
  FileCode,
  Type,
  FileDown,
  FolderOpen,
  ExternalLink,
  PanelRight,
} from 'lucide-react'

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
  onExportPDF: () => void
  isExportingPDF: boolean
  totalCells: number
  isDirty: boolean
  isSaving: boolean
  playgroundStatus: 'connected' | 'connecting' | 'disconnected'
  kernelStatus: 'idle' | 'busy' | 'stopped' | 'error' | 'unknown'
  onStartKernel: () => void
  onStopKernel: () => void
  onRestartKernel: () => void
  onRestartPlayground: () => void
  rightPanel: 'chat' | 'logs' | null
  onToggleChat: () => void
  onOpenLogsPanel: () => void
  onOpenLogsWindow: () => void
  onOpenTerminal: () => void
  // AI Settings
  llmProvider: string
  onProviderChange: (provider: string) => void
  availableProviders?: { provider: string; display_name: string }[]
  contextFormat: 'xml' | 'json' | 'plain'
  onContextFormatChange: (format: 'xml' | 'json' | 'plain') => void
  aiCellMode: string
  onAICellModeChange: (mode: string) => void
  availableModes?: { mode_name: string; label: string }[]
  showFiles?: boolean
  onToggleFiles?: () => void
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
  onExportPDF,
  isExportingPDF,
  totalCells,
  isDirty,
  isSaving,
  playgroundStatus,
  kernelStatus,
  onStartKernel,
  onStopKernel,
  onRestartKernel,
  onRestartPlayground,
  rightPanel,
  onToggleChat,
  onOpenLogsPanel,
  onOpenLogsWindow,
  onOpenTerminal,
  llmProvider,
  onProviderChange,
  availableProviders,
  contextFormat,
  onContextFormatChange,
  aiCellMode,
  onAICellModeChange,
  availableModes,
  showFiles,
  onToggleFiles,
}: NotebookToolbarProps) {
  const { density, setDensity } = useTheme()
  const showChat = rightPanel === 'chat'
  const showLogs = rightPanel === 'logs'
  const [justSaved, setJustSaved] = useState(false)
  const [prevIsDirty, setPrevIsDirty] = useState(isDirty)
  const [showAISettings, setShowAISettings] = useState(false)
  const [showDensityDropdown, setShowDensityDropdown] = useState(false)
  const [showLogsDropdown, setShowLogsDropdown] = useState(false)
  const aiSettingsRef = useRef<HTMLDivElement>(null)
  const densityDropdownRef = useRef<HTMLDivElement>(null)
  const logsDropdownRef = useRef<HTMLDivElement>(null)

  // Flash green when save completes (isDirty goes from true to false)
  useEffect(() => {
    if (prevIsDirty && !isDirty && !isSaving) {
      setJustSaved(true)
      const timer = setTimeout(() => setJustSaved(false), 2000)
      return () => clearTimeout(timer)
    }
    setPrevIsDirty(isDirty)
  }, [isDirty, isSaving, prevIsDirty])

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (aiSettingsRef.current && !aiSettingsRef.current.contains(event.target as Node)) {
        setShowAISettings(false)
      }
      if (densityDropdownRef.current && !densityDropdownRef.current.contains(event.target as Node)) {
        setShowDensityDropdown(false)
      }
      if (logsDropdownRef.current && !logsDropdownRef.current.contains(event.target as Node)) {
        setShowLogsDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div
      className="flex items-center justify-between px-4 py-2"
      style={{
        backgroundColor: 'var(--nb-bg-header)',
        borderBottom: '1px solid var(--nb-border-default)',
      }}
    >
      <div className="flex items-center gap-1.5">
        {/* Add cell buttons - ghost/outline style */}
        <button
          onClick={onAddCode}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-blue-500/10 border border-transparent hover:border-blue-500/30"
          style={{ color: 'var(--nb-accent-code)' }}
        >
          <Code className="w-[18px] h-[18px]" />
          Code
        </button>
        <button
          onClick={onAddMarkdown}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-purple-500/10 border border-transparent hover:border-purple-500/30"
          style={{ color: 'var(--nb-accent-markdown)' }}
        >
          <FileText className="w-[18px] h-[18px]" />
          Markdown
        </button>
        <button
          onClick={onAddAI}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-stone-500/10 border border-transparent hover:border-stone-400/30"
          style={{ color: 'var(--nb-accent-ai)' }}
        >
          <Lightbulb className="w-[18px] h-[18px]" />
          AI
        </button>
        <div className="w-px h-6 mx-1.5" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Run controls - ghost buttons with labels */}
        <button
          onClick={onRunAll}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-emerald-500/10 border border-transparent hover:border-emerald-500/30"
          style={{ color: 'var(--nb-accent-success)' }}
          title="Run all cells"
        >
          <Play className="w-[18px] h-[18px]" fill="currentColor" />
          Run
        </button>
        <button
          onClick={onClearOutputs}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-amber-500/10 border border-transparent hover:border-amber-500/30"
          style={{ color: 'var(--app-accent-warning)' }}
          title="Clear all outputs"
        >
          <Eraser className="w-[18px] h-[18px]" />
          Clear
        </button>
        <button
          onClick={onDeleteAllCells}
          className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-red-500/10 border border-transparent hover:border-red-500/30"
          style={{ color: 'var(--nb-accent-error)' }}
          title="Delete all cells"
        >
          <Trash2 className="w-[18px] h-[18px]" />
          Delete
        </button>

        <div className="w-px h-6 mx-1.5" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Cell count indicator */}
        <div className="text-sm px-2" style={{ color: 'var(--nb-text-muted)' }}>
          <span className="font-medium" style={{ color: 'var(--nb-accent-success)' }}>{totalCells}</span> cells
        </div>

        <div className="w-px h-6 mx-1.5" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Kernel control - unified button with state */}
        {kernelStatus === 'stopped' || kernelStatus === 'unknown' ? (
          // Start Kernel button - ghost style with green accent
          <button
            onClick={onStartKernel}
            className="px-3 py-2 text-sm rounded-md transition-all flex items-center gap-2 hover:bg-emerald-500/15 border border-emerald-500/30"
            style={{ color: 'var(--nb-accent-success)' }}
            title="Start kernel"
          >
            <Play className="w-[18px] h-[18px]" fill="currentColor" />
            Start Kernel
          </button>
        ) : (
          // Kernel running - show status with dropdown menu
          <div className="relative group">
            <div
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
              style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--nb-border-default)' }}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  kernelStatus === 'idle'
                    ? 'bg-green-500'
                    : kernelStatus === 'busy'
                    ? 'bg-yellow-500 animate-pulse'
                    : 'bg-red-500'
                }`}
              />
              <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
                Kernel: {kernelStatus === 'idle' ? 'Idle' : kernelStatus === 'busy' ? 'Busy' : 'Error'}
              </span>
              <ChevronDown className="w-4 h-4" style={{ color: 'var(--nb-text-muted)' }} />
            </div>

            {/* Dropdown menu */}
            <div
              className="absolute top-full left-0 mt-1 w-40 py-1 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50"
              style={{
                backgroundColor: 'var(--nb-bg-secondary)',
                border: '1px solid var(--nb-border-default)',
              }}
            >
              <button
                onClick={onRestartKernel}
                className="w-full px-3 py-2 text-xs text-left flex items-center gap-2 hover:bg-amber-500/20 transition-colors"
                style={{ color: 'var(--nb-text-secondary)' }}
              >
                <RefreshCw className="w-4 h-4 text-amber-500" />
                Restart Kernel
              </button>
              <button
                onClick={onStopKernel}
                className="w-full px-3 py-2 text-xs text-left flex items-center gap-2 hover:bg-red-500/20 transition-colors"
                style={{ color: 'var(--nb-text-secondary)' }}
              >
                <Square className="w-4 h-4 text-red-500" fill="currentColor" />
                Stop Kernel
              </button>
            </div>
          </div>
        )}

        <div className="w-px h-5 mx-1" style={{ backgroundColor: 'var(--nb-border-default)' }} />

        {/* Playground restart button - ghost style */}
        <button
          onClick={onRestartPlayground}
          className="p-2 rounded-md transition-all hover:bg-red-500/15 border border-transparent hover:border-red-500/30"
          style={{ color: 'var(--nb-accent-error)' }}
          title="Restart playground container"
        >
          <RefreshCw className="w-5 h-5" />
        </button>

        {/* Playground connection status indicator */}
        <div className="flex items-center gap-2 ml-1 px-2 py-1 rounded-lg" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--nb-border-default)' }}>
          <span
            className={`w-2 h-2 rounded-full ${
              playgroundStatus === 'connected'
                ? 'bg-green-500'
                : playgroundStatus === 'connecting'
                ? 'bg-yellow-500 animate-pulse'
                : 'bg-red-500'
            }`}
          />
          <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
            Playground: {playgroundStatus === 'connected' ? 'Connected' : playgroundStatus === 'connecting' ? 'Connecting...' : 'Disconnected'}
          </span>
        </div>

        <div className="w-px h-6 mx-2" style={{ backgroundColor: 'var(--nb-border-default)' }} />

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
            <Monitor className="w-[18px] h-[18px]" style={{ color: 'var(--nb-text-muted)' }} />
            <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>Shortcuts</span>
          </button>

          {/* Dropdown on hover - Two column layout */}
          <div
            className="absolute top-full left-0 mt-1 w-[520px] p-3 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50"
            style={{
              backgroundColor: 'var(--app-glass-bg)',
              border: '1px solid var(--app-glass-border)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
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
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>⇧</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↵</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Save notebook</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Ctrl</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>S</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Enter edit mode</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↵</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Exit edit mode</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Esc</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Navigate cells</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↑</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>↓</kbd>
                    </div>
                  </div>
                </div>

                <div className="text-xs font-medium pb-1 mb-2 mt-3" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Cell Type</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>To code</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Y</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>To markdown</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>M</kbd>
                  </div>
                </div>

                <div className="text-xs font-medium pb-1 mb-2 mt-3" style={{ color: 'var(--nb-text-muted)', borderBottom: '1px solid var(--nb-border-default)' }}>Code Editing</div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Toggle comment</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Ctrl</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>/</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Indent</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Tab</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Outdent</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>⇧</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Tab</kbd>
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
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>A</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Insert below</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>B</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Delete cell</span>
                    <div className="flex items-center gap-0.5">
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>D</kbd>
                      <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>D</kbd>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Cut cell</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>X</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Copy cell</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>C</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Paste below</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>V</kbd>
                  </div>
                  <div className="flex items-center justify-between text-xs py-1 px-1 rounded" style={{ color: 'var(--nb-text-secondary)' }}>
                    <span>Undo delete</span>
                    <kbd className="px-1 py-0.5 text-[10px] font-mono rounded" style={{ backgroundColor: 'var(--nb-bg-primary)', border: '1px solid var(--nb-border-default)', color: 'var(--nb-text-secondary)' }}>Z</kbd>
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

        {/* Save status button - ghost style, primary color when dirty */}
        <button
          onClick={onSave}
          disabled={isSaving || !isDirty}
          className={`px-2.5 py-1.5 text-xs rounded-md transition-all duration-300 flex items-center gap-1.5 border ${
            isSaving
              ? 'cursor-not-allowed opacity-70'
              : isDirty
              ? 'border-blue-500/40 hover:bg-blue-500/15'
              : 'border-transparent'
          }`}
          style={{
            color: isSaving ? 'var(--nb-text-muted)' : isDirty ? 'var(--app-accent-primary)' : justSaved ? 'var(--nb-accent-success)' : 'var(--nb-text-muted)',
          }}
          title={isSaving ? 'Saving...' : isDirty ? 'Save notebook (Ctrl+S)' : 'Notebook saved'}
        >
          {isSaving ? (
            <div className="w-[18px] h-[18px] border-2 border-current/30 border-t-current rounded-full animate-spin" />
          ) : isDirty ? (
            <Save className="w-[18px] h-[18px]" />
          ) : (
            <Check className="w-[18px] h-[18px]" />
          )}
          {isSaving ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
        </button>
      </div>

      <div className="flex items-center gap-2">
        {/* Density dropdown - typography mode selector */}
        <div className="relative" ref={densityDropdownRef}>
          <button
            onClick={() => setShowDensityDropdown(!showDensityDropdown)}
            className={`px-2.5 py-2 rounded-md transition-all flex items-center gap-2 border ${showDensityDropdown ? 'border-cyan-500/40 bg-cyan-500/10' : 'border-transparent hover:border-cyan-500/30 hover:bg-cyan-500/10'}`}
            style={{ color: 'var(--nb-text-muted)' }}
            title="Typography density"
          >
            <Type className="w-5 h-5" />
            <ChevronDown className={`w-4 h-4 transition-transform ${showDensityDropdown ? 'rotate-180' : ''}`} />
          </button>

          {/* Dropdown panel */}
          {showDensityDropdown && (
            <div
              className="absolute right-0 top-full mt-2 w-52 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200"
              style={{
                backgroundColor: 'var(--nb-bg-secondary)',
                border: '1px solid var(--nb-border-default)',
              }}
            >
              {/* Header */}
              <div
                className="px-4 py-3 flex items-center gap-2"
                style={{ borderBottom: '1px solid var(--nb-border-default)', background: 'linear-gradient(135deg, rgba(34, 211, 238, 0.1), rgba(59, 130, 246, 0.1))' }}
              >
                <Type className="w-[18px] h-[18px]" style={{ color: 'var(--app-accent-info)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--nb-text-primary)' }}>Density</span>
              </div>

              {/* Density options */}
              <div className="py-1">
                {densityOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setDensity(option.value)
                      setShowDensityDropdown(false)
                    }}
                    className={`w-full px-4 py-2.5 text-left flex items-center gap-3 transition-colors ${
                      density === option.value
                        ? 'bg-cyan-500/15'
                        : 'hover:bg-cyan-500/10'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium" style={{ color: density === option.value ? 'var(--app-accent-info)' : 'var(--nb-text-primary)' }}>
                        {option.label}
                      </div>
                      <div className="text-xs truncate" style={{ color: 'var(--nb-text-muted)' }}>
                        {option.description}
                      </div>
                    </div>
                    {density === option.value && (
                      <Check className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--app-accent-info)' }} />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Export buttons - ghost style */}
        <button
          onClick={onExport}
          disabled={isExporting}
          className="p-2 rounded-md transition-all flex items-center justify-center border border-transparent hover:border-cyan-500/30 hover:bg-cyan-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ color: 'var(--app-accent-info)' }}
          title="Export as .ipynb"
        >
          {isExporting ? (
            <div className="w-5 h-5 border-2 border-current/30 border-t-current rounded-full animate-spin" />
          ) : (
            <Download className="w-5 h-5" />
          )}
        </button>
        <button
          onClick={onExportPDF}
          disabled={isExportingPDF}
          className="p-2 rounded-md transition-all flex items-center justify-center border border-transparent hover:border-rose-500/30 hover:bg-rose-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ color: 'var(--app-accent-error)' }}
          title="Export as PDF"
        >
          {isExportingPDF ? (
            <div className="w-5 h-5 border-2 border-current/30 border-t-current rounded-full animate-spin" />
          ) : (
            <FileDown className="w-5 h-5" />
          )}
        </button>

        {/* Logs dropdown */}
        <div className="relative" ref={logsDropdownRef}>
          <button
            onClick={() => setShowLogsDropdown(!showLogsDropdown)}
            className={`p-2 rounded-md transition-all flex items-center justify-center border ${
              showLogs
                ? 'border-emerald-500/40 bg-emerald-500/15'
                : 'border-transparent hover:border-current/20 hover:bg-gray-500/10'
            }`}
            style={{ color: showLogs ? '#34d399' : 'var(--nb-text-muted)' }}
            title="Logs"
          >
            <FileText className="w-5 h-5" />
            <ChevronDown className="w-3 h-3 ml-0.5" />
          </button>

          {showLogsDropdown && (
            <div
              className="absolute right-0 top-full mt-2 w-52 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200"
              style={{
                backgroundColor: 'var(--nb-bg-secondary)',
                border: '1px solid var(--nb-border-default)',
              }}
            >
              <button
                onClick={() => { onOpenLogsPanel(); setShowLogsDropdown(false) }}
                className="w-full px-4 py-2.5 text-sm text-left flex items-center gap-2.5 transition-colors"
                style={{ color: 'var(--nb-text-primary)' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <PanelRight className="w-4 h-4" style={{ color: 'var(--nb-text-muted)' }} />
                Open in Panel
              </button>
              <button
                onClick={() => { onOpenLogsWindow(); setShowLogsDropdown(false) }}
                className="w-full px-4 py-2.5 text-sm text-left flex items-center gap-2.5 transition-colors"
                style={{ color: 'var(--nb-text-primary)', borderTop: '1px solid var(--nb-border-default)' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <ExternalLink className="w-4 h-4" style={{ color: 'var(--nb-text-muted)' }} />
                Open in New Window
              </button>
            </div>
          )}
        </div>

        {/* Terminal button - ghost style */}
        <button
          onClick={onOpenTerminal}
          className="p-2 rounded-md transition-all flex items-center justify-center border border-transparent hover:border-current/20 hover:bg-gray-500/10"
          style={{ color: 'var(--nb-text-muted)' }}
          title="Open Terminal (new tab)"
        >
          <Terminal className="w-5 h-5" />
        </button>

        {/* AI Settings dropdown - ghost style */}
        <div className="relative" ref={aiSettingsRef}>
          <button
            onClick={() => setShowAISettings(!showAISettings)}
            className={`px-2.5 py-2 rounded-md transition-all flex items-center gap-2 border ${showAISettings ? 'border-stone-400/40 bg-stone-500/10' : 'border-transparent hover:border-stone-400/30 hover:bg-stone-500/10'}`}
            style={{
              color: 'var(--nb-accent-ai)',
            }}
            title="AI Settings"
          >
            <Sparkles className="w-[18px] h-[18px]" />
            <span className="text-sm">{llmProvider.charAt(0).toUpperCase() + llmProvider.slice(1)}</span>
            <ChevronDown className={`w-4 h-4 transition-transform ${showAISettings ? 'rotate-180' : ''}`} />
          </button>

          {/* Dropdown panel */}
          {showAISettings && (
            <div
              className="absolute right-0 top-full mt-2 w-72 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200"
              style={{
                backgroundColor: 'var(--nb-bg-secondary)',
                border: '1px solid var(--nb-border-default)',
              }}
            >
              {/* Header */}
              <div
                className="px-4 py-3 flex items-center gap-2"
                style={{ borderBottom: '1px solid var(--nb-border-default)', background: 'linear-gradient(135deg, rgba(168, 162, 158, 0.12), rgba(120, 113, 108, 0.08))' }}
              >
                <Sparkles className="w-[18px] h-[18px]" style={{ color: 'var(--nb-accent-ai)' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--nb-text-primary)' }}>AI Settings</span>
              </div>

              {/* Settings */}
              <div className="p-3 space-y-3">
                {/* Model */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--nb-text-muted)' }}>
                    <Bot className="w-4 h-4" />
                    Model Provider
                  </label>
                  <select
                    value={llmProvider}
                    onChange={(e) => onProviderChange(e.target.value)}
                    className="w-full text-sm rounded-lg px-3 py-2 border focus:outline-none focus:ring-2 focus:ring-stone-400/50 transition-all cursor-pointer"
                    style={{
                      backgroundColor: 'var(--nb-bg-primary)',
                      borderColor: 'var(--nb-border-default)',
                      color: 'var(--nb-text-primary)',
                    }}
                  >
                    {availableProviders && availableProviders.length > 0 ? (
                      availableProviders.map(p => (
                        <option key={p.provider} value={p.provider}>{p.display_name}</option>
                      ))
                    ) : (
                      <>
                        <option value="gemini">Google Gemini</option>
                        <option value="openai">OpenAI</option>
                        <option value="anthropic">Anthropic Claude</option>
                        <option value="openai_compatible">OpenAI Compatible</option>
                      </>
                    )}
                  </select>
                </div>

                {/* Context Format */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--nb-text-muted)' }}>
                    <FileCode className="w-4 h-4" />
                    Context Format
                  </label>
                  <select
                    value={contextFormat}
                    onChange={(e) => onContextFormatChange(e.target.value as 'xml' | 'json' | 'plain')}
                    className="w-full text-sm rounded-lg px-3 py-2 border focus:outline-none focus:ring-2 focus:ring-stone-400/50 transition-all cursor-pointer"
                    style={{
                      backgroundColor: 'var(--nb-bg-primary)',
                      borderColor: 'var(--nb-border-default)',
                      color: 'var(--nb-text-primary)',
                    }}
                  >
                    <option value="xml">XML (Claude)</option>
                    <option value="json">JSON (OpenAI, Gemini)</option>
                    <option value="plain">Plain text (Ollama)</option>
                  </select>
                </div>

                {/* AI Cell Mode */}
                <div className="space-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--nb-text-muted)' }}>
                    <Lightbulb className="w-4 h-4" />
                    AI Cell Mode
                  </label>
                  <select
                    value={aiCellMode}
                    onChange={(e) => onAICellModeChange(e.target.value)}
                    className="w-full text-sm rounded-lg px-3 py-2 border focus:outline-none focus:ring-2 focus:ring-stone-400/50 transition-all cursor-pointer"
                    style={{
                      backgroundColor: 'var(--nb-bg-primary)',
                      borderColor: 'var(--nb-border-default)',
                      color: 'var(--nb-text-primary)',
                    }}
                  >
                    {availableModes && availableModes.length > 0 ? (
                      availableModes.map(m => (
                        <option key={m.mode_name} value={m.mode_name}>{m.label}</option>
                      ))
                    ) : (
                      <>
                        <option value="crisp">Crisp Mode</option>
                        <option value="standard">Standard Mode</option>
                        <option value="power">Power Mode</option>
                      </>
                    )}
                  </select>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Files toggle button - ghost style */}
        {onToggleFiles && (
          <button
            onClick={onToggleFiles}
            className={`p-2 rounded-md transition-all flex items-center justify-center border ${showFiles ? 'border-amber-500/40 bg-amber-500/15' : 'border-transparent hover:border-amber-500/30 hover:bg-amber-500/10'}`}
            style={{
              color: showFiles ? 'var(--app-accent-warning)' : 'var(--nb-text-muted)',
            }}
            title={showFiles ? 'Hide Files' : 'Show Files'}
          >
            <FolderOpen className="w-5 h-5" />
          </button>
        )}

        {/* Chat toggle button - ghost style with primary accent when active */}
        <button
          onClick={onToggleChat}
          className={`p-2 rounded-md transition-all flex items-center justify-center border ${showChat ? 'border-blue-500/40 bg-blue-500/15' : 'border-transparent hover:border-blue-500/30 hover:bg-blue-500/10'}`}
          style={{
            color: showChat ? 'var(--app-accent-primary)' : 'var(--nb-text-muted)',
          }}
          title={showChat ? 'Hide AI Chat' : 'Show AI Chat'}
        >
          <MessageSquare className="w-5 h-5" />
        </button>
      </div>
    </div>
  )
}
