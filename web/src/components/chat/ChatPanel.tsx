'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import type { ChatMessage, LLMStep } from '@/types'

interface PendingToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

interface ChatPanelProps {
  messages: ChatMessage[]
  isLoading: boolean
  pendingTools: PendingToolCall[]
  onSendMessage: (message: string) => void
  onApproveTools: (tools: PendingToolCall[]) => void
  onRejectTools: () => void
  llmProvider: string
  onProviderChange: (provider: string) => void
  toolMode: 'auto' | 'manual' | 'ai_decide'
  onToolModeChange: (mode: 'auto' | 'manual' | 'ai_decide') => void
  onDeleteMessage: (index: number) => void
  onEditMessage: (index: number, newContent: string) => void
  onRerunMessage: (index: number) => void
  onClearHistory: () => void
  onSummarize: () => void
  isSummarizing: boolean
  onScrollToCell?: (cellId: string) => void
  onPanelClick?: () => void
}

// Theme-aware colors for chat panel
const themeColors = {
  dark: {
    panelBg: '#1a1a2e',
    headerBg: 'linear-gradient(to right, rgba(30, 41, 59, 0.5), rgba(15, 23, 42, 0.5))',
    messagesBg: '#1a1a2e',
    inputBg: 'rgba(30, 41, 59, 0.5)',
    assistantBubble: 'rgba(31, 41, 55, 0.8)',
    border: 'rgba(75, 85, 99, 0.5)',
  },
  light: {
    panelBg: '#f8fafc',
    headerBg: 'linear-gradient(to right, rgba(241, 245, 249, 0.9), rgba(226, 232, 240, 0.9))',
    messagesBg: '#f1f5f9',
    inputBg: 'rgba(241, 245, 249, 0.8)',
    assistantBubble: '#ffffff',
    border: 'rgba(203, 213, 225, 0.8)',
  },
  monokai: {
    panelBg: '#272822',
    headerBg: 'linear-gradient(to right, rgba(39, 40, 34, 0.9), rgba(30, 31, 28, 0.9))',
    messagesBg: '#272822',
    inputBg: 'rgba(39, 40, 34, 0.8)',
    assistantBubble: 'rgba(39, 40, 34, 0.9)',
    border: 'rgba(117, 113, 94, 0.5)',
  },
}

export default function ChatPanel({
  messages,
  isLoading,
  pendingTools,
  onSendMessage,
  onApproveTools,
  onRejectTools,
  llmProvider,
  onProviderChange,
  toolMode,
  onToolModeChange,
  onDeleteMessage,
  onEditMessage,
  onRerunMessage,
  onClearHistory,
  onSummarize,
  isSummarizing,
  onScrollToCell,
  onPanelClick,
}: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const editTextareaRef = useRef<HTMLTextAreaElement>(null)
  const { theme } = useTheme()
  const colors = themeColors[theme]

  // Auto-resize textarea based on content
  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      const newHeight = Math.min(Math.max(textarea.scrollHeight, 80), 300)
      textarea.style.height = `${newHeight}px`
    }
  }

  // Auto-resize edit textarea based on content
  const adjustEditTextareaHeight = () => {
    const textarea = editTextareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${textarea.scrollHeight}px`
    }
  }

  useEffect(() => {
    adjustTextareaHeight()
  }, [input])

  // Auto-resize edit textarea when content changes or editing starts
  useEffect(() => {
    if (editingIndex !== null) {
      // Small delay to ensure textarea is mounted
      setTimeout(adjustEditTextareaHeight, 0)
    }
  }, [editingIndex, editContent])

  // Initialize selected tools when pending tools change
  useEffect(() => {
    if (pendingTools.length > 0) {
      setSelectedTools(new Set(pendingTools.map((t) => t.id)))
    }
  }, [pendingTools])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    onSendMessage(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleApprove = () => {
    const approved = pendingTools.filter((t) => selectedTools.has(t.id))
    if (approved.length > 0) {
      onApproveTools(approved)
    }
  }

  const toggleTool = (id: string) => {
    const newSelected = new Set(selectedTools)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedTools(newSelected)
  }

  const startEditing = (index: number, content: string) => {
    setEditingIndex(index)
    setEditContent(content)
  }

  const cancelEditing = () => {
    setEditingIndex(null)
    setEditContent('')
  }

  const saveEdit = () => {
    if (editingIndex !== null && editContent.trim()) {
      onEditMessage(editingIndex, editContent.trim())
      cancelEditing()
    }
  }

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      cancelEditing()
    } else if (e.key === 'Enter' && e.ctrlKey) {
      saveEdit()
    }
  }

  // Find the last user message index
  const lastUserMessageIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return i
    }
    return -1
  })()

  const renderSteps = (steps: LLMStep[]) => {
    if (!steps || steps.length === 0) return null

    const toolNames = [...new Set(steps.filter(s => s.name).map(s => s.name))]
    const summaryText = toolNames.length > 0
      ? `Used ${toolNames.length} tool${toolNames.length > 1 ? 's' : ''}: ${toolNames.join(', ')}`
      : `${steps.length} step${steps.length > 1 ? 's' : ''}`

    return (
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer flex items-center gap-1.5 text-gray-400 hover:text-gray-300 transition-colors">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {summaryText}
        </summary>
        <div className="mt-2 space-y-2 ml-2 pl-3 border-l-2 border-gray-600/50">
          {steps.map((step, idx) => (
            <div key={idx} className="text-gray-400">
              <span className="font-medium text-gray-300 flex items-center gap-1.5">
                {step.type === 'tool_call' && (
                  <span className="w-5 h-5 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center text-[10px]">⚡</span>
                )}
                {step.type === 'tool_result' && (
                  <span className="w-5 h-5 rounded bg-green-500/20 text-green-400 flex items-center justify-center text-[10px]">✓</span>
                )}
                {step.type === 'text' && (
                  <span className="w-5 h-5 rounded bg-purple-500/20 text-purple-400 flex items-center justify-center text-[10px]">💭</span>
                )}
                {step.name || step.type}
              </span>
              <pre className="mt-1.5 text-[11px] rounded-md p-2 whitespace-pre-wrap break-words overflow-hidden bg-black/20 text-gray-300 font-mono">
                {step.content.slice(0, 500)}
                {step.content.length > 500 && '...'}
              </pre>
            </div>
          ))}
        </div>
      </details>
    )
  }

  // Copy message content to clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  // Process cell-xxx references into clickable spans
  const processCellReferences = (text: string): React.ReactNode[] => {
    // Match cell ID patterns: @cell-xxx, `cell-xxx`, or plain cell-xxx in backticks
    // Cell ID formats: cell-14d6c2b447d1 or cell-1764863866351-wq1kuzp8k
    const cellRefRegex = /(?:@|`)(cell-[a-zA-Z0-9-]+)`?/g
    const parts: React.ReactNode[] = []
    let lastIndex = 0
    let match

    while ((match = cellRefRegex.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }
      // Add clickable cell reference
      const cellId = match[1]
      parts.push(
        <button
          key={`${cellId}-${match.index}`}
          onClick={(e) => {
            e.stopPropagation()
            if (onScrollToCell) {
              onScrollToCell(cellId)
            }
          }}
          className="text-purple-400 underline cursor-pointer hover:text-purple-300 transition-colors bg-transparent border-none p-0 font-inherit"
          style={{ font: 'inherit' }}
        >
          @{cellId}
        </button>
      )
      lastIndex = match.index + match[0].length
    }
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }
    return parts.length > 0 ? parts : [text]
  }

  // Render message content with clickable cell references
  const renderMessageContent = useCallback((content: string) => {
    // Split by newlines to preserve whitespace formatting
    const lines = content.split('\n')
    return lines.map((line, lineIdx) => (
      <span key={lineIdx}>
        {processCellReferences(line)}
        {lineIdx < lines.length - 1 && '\n'}
      </span>
    ))
  }, [onScrollToCell])

  // Text colors based on theme
  const textPrimary = theme === 'light' ? '#1e293b' : '#ffffff'
  const textSecondary = theme === 'light' ? '#475569' : '#9ca3af'
  const textMuted = theme === 'light' ? '#64748b' : '#6b7280'

  return (
    <div
      className="flex flex-col h-full"
      style={{
        backgroundColor: colors.panelBg,
        borderLeft: `1px solid ${colors.border}`,
      }}
      onClick={onPanelClick}
    >
      {/* Header */}
      <div className="p-4 backdrop-blur-sm" style={{ background: colors.headerBg, borderBottom: `1px solid ${colors.border}` }}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h2 className="text-base font-semibold" style={{ color: textPrimary }}>AI Assistant</h2>
          </div>
          <div className="flex items-center gap-2">
            {/* Summarize button */}
            <button
              onClick={onSummarize}
              disabled={isSummarizing}
              className="text-xs px-2.5 py-1.5 rounded-md flex items-center gap-1.5 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400 text-white disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
              title="Generate AI summary of notebook"
            >
              {isSummarizing ? (
                <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                </svg>
              )}
              Summarize
            </button>
            <select
              value={llmProvider}
              onChange={(e) => onProviderChange(e.target.value)}
              className="text-xs rounded-md px-2.5 py-1.5 border focus:outline-none focus:border-blue-500/50 transition-colors cursor-pointer"
              style={{ backgroundColor: theme === 'light' ? '#fff' : 'rgba(255,255,255,0.05)', borderColor: colors.border, color: textSecondary }}
            >
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <button
              onClick={onClearHistory}
              className="text-xs px-2.5 py-1.5 rounded-md hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all"
              style={{ color: textMuted }}
              title="Clear chat history"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Tool mode */}
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-500">Tools:</span>
          <div className="flex items-center gap-1 bg-white/5 rounded-lg p-0.5">
            {(['auto', 'manual', 'ai_decide'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => onToolModeChange(mode)}
                className={`px-2.5 py-1 rounded-md transition-all ${
                  toolMode === mode
                    ? 'bg-blue-500/20 text-blue-400 shadow-sm'
                    : 'text-gray-400 hover:text-gray-300 hover:bg-white/5'
                }`}
              >
                {mode === 'auto' ? 'Auto' : mode === 'manual' ? 'Approval' : 'AI Decides'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" style={{ backgroundColor: colors.messagesBg }}>
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500/20 to-teal-500/20 border border-blue-500/20 flex items-center justify-center">
              <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium mb-2" style={{ color: textPrimary }}>Welcome!</h3>
            <p className="mb-4" style={{ color: textSecondary }}>I can help with your notebook:</p>
            <div className="inline-flex flex-col items-start text-sm space-y-2 rounded-xl p-4" style={{ backgroundColor: theme === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.05)', border: `1px solid ${colors.border}`, color: textSecondary }}>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs">?</span>
                <span>Answer questions about selected cells</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded bg-green-500/20 text-green-400 flex items-center justify-center text-xs">⌘</span>
                <span>Write and edit code</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded bg-purple-500/20 text-purple-400 flex items-center justify-center text-xs">▶</span>
                <span>Execute cells automatically</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded bg-amber-500/20 text-amber-400 flex items-center justify-center text-xs">📝</span>
                <span>Create documentation</span>
              </div>
            </div>
            <p className="text-xs mt-6" style={{ color: textMuted }}>
              All notebook cells are automatically included as context.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`group flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}
          >
            <div className={`flex items-start gap-2.5 ${editingIndex === idx ? 'w-[85%]' : 'max-w-[85%]'} ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {/* Avatar */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center shadow-lg ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-500 to-blue-600 shadow-blue-500/20'
                  : 'bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/20'
              }`}>
                {msg.role === 'user' ? (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                )}
              </div>

              {/* Message content */}
              <div className={`flex flex-col gap-1 ${editingIndex === idx ? 'flex-1' : ''}`}>
                <div
                  className={`rounded-2xl px-4 py-2.5 shadow-lg ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-tr-md'
                      : 'rounded-tl-md'
                  } ${editingIndex === idx ? 'w-full' : ''}`}
                  style={msg.role === 'assistant' ? {
                    backgroundColor: colors.assistantBubble,
                    border: `1px solid ${colors.border}`,
                    color: textPrimary,
                  } : undefined}
                >
                  {editingIndex === idx ? (
                    <>
                      <textarea
                        ref={editTextareaRef}
                        value={editContent}
                        onChange={(e) => {
                          setEditContent(e.target.value)
                        }}
                        onKeyDown={handleEditKeyDown}
                        className="text-sm resize-none focus:outline-none bg-transparent overflow-hidden whitespace-pre-wrap leading-relaxed"
                        style={{ color: 'inherit', width: '100%' }}
                        autoFocus
                      />
                      <div className="flex gap-2 mt-2 pt-2 border-t border-white/10">
                        <button
                          onClick={saveEdit}
                          className="text-xs px-3 py-1.5 bg-green-500 hover:bg-green-400 text-white rounded-lg transition-colors"
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="text-xs px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="text-sm whitespace-pre-wrap leading-relaxed">
                        {msg.role === 'assistant' ? renderMessageContent(msg.content) : msg.content}
                      </div>
                      {msg.role === 'assistant' && msg.steps && renderSteps(msg.steps)}
                    </>
                  )}
                </div>

                {/* Action buttons */}
                {editingIndex !== idx && (
                  <div className={`flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {/* Copy button */}
                    <button
                      onClick={() => copyToClipboard(msg.content)}
                      className="text-[10px] p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-white/10 transition-all"
                      title="Copy message"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    </button>
                    {/* Re-run button - only for last user message */}
                    {msg.role === 'user' && idx === lastUserMessageIndex && (
                      <button
                        onClick={() => onRerunMessage(idx)}
                        className="text-[10px] p-1.5 rounded-md text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 transition-all"
                        title="Re-run this message"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      </button>
                    )}
                    {/* Edit button */}
                    <button
                      onClick={() => startEditing(idx, msg.content)}
                      className="text-[10px] p-1.5 rounded-md text-gray-500 hover:text-amber-400 hover:bg-amber-500/10 transition-all"
                      title="Edit message"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    {/* Delete button - only for user messages */}
                    {msg.role === 'user' && (
                      <button
                        onClick={() => onDeleteMessage(idx)}
                        className="text-[10px] p-1.5 rounded-md text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Delete message and responses"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Tool approval UI */}
        {pendingTools.length > 0 && (
          <div className="rounded-xl p-4 bg-amber-500/10 border border-amber-500/30 shadow-lg shadow-amber-500/5 animate-fadeIn">
            <div className="flex items-center gap-2 text-sm font-medium mb-3 text-amber-400">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              The assistant wants to use these tools:
            </div>
            <div className="space-y-2 mb-4">
              {pendingTools.map((tool) => (
                <label
                  key={tool.id}
                  className={`flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all ${
                    selectedTools.has(tool.id)
                      ? 'bg-white/10 border border-white/20'
                      : 'bg-white/5 border border-transparent hover:bg-white/10'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedTools.has(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                    className="mt-0.5 w-4 h-4 rounded border-gray-500 text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-white text-sm">{tool.name}</div>
                    <details className="text-xs text-gray-400 mt-1">
                      <summary className="cursor-pointer hover:text-gray-300">View arguments</summary>
                      <pre className="mt-2 rounded-lg p-2 whitespace-pre-wrap break-words overflow-hidden bg-black/30 text-gray-300 text-[11px] font-mono">
                        {JSON.stringify(tool.arguments, null, 2)}
                      </pre>
                    </details>
                  </div>
                </label>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                disabled={selectedTools.size === 0}
                className="flex-1 px-4 py-2 text-sm bg-green-500 hover:bg-green-400 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium shadow-lg shadow-green-500/20"
              >
                Approve ({selectedTools.size})
              </button>
              <button
                onClick={onRejectTools}
                className="flex-1 px-4 py-2 text-sm bg-red-500/80 hover:bg-red-500 text-white rounded-lg transition-colors font-medium"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start animate-fadeIn">
            <div className="flex items-start gap-2.5">
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <div className="rounded-2xl rounded-tl-md px-4 py-3 bg-gray-800/80 border border-gray-700/50 shadow-lg">
                <div className="flex items-center gap-2 text-gray-400">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4" style={{ background: colors.inputBg, borderTop: `1px solid ${colors.border}` }}>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask AI for help... (Enter to send, Shift+Enter for new line)"
              className="w-full rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
              style={{
                minHeight: '80px',
                maxHeight: '300px',
                backgroundColor: theme === 'light' ? '#fff' : 'rgba(31, 41, 55, 0.5)',
                border: `1px solid ${colors.border}`,
                color: textPrimary,
              }}
              disabled={isLoading}
            />
          </div>
          <div className="flex items-end pb-1">
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="p-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 disabled:from-gray-600 disabled:to-gray-600 disabled:cursor-not-allowed text-white rounded-xl transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 disabled:shadow-none"
              title="Send message"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </form>

      {/* Add fade-in animation style */}
      <style jsx>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  )
}
