'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import {
  MessageSquare,
  Sparkles,
  User,
  Lightbulb,
  Copy,
  RefreshCw,
  Edit3,
  Trash2,
  AlertTriangle,
  Image,
  Send,
  ChevronDown,
  ChevronUp,
  Wrench,
} from 'lucide-react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessage, LLMStep, ImageInput } from '@/types'

interface PendingToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

interface ChatPanelProps {
  messages: ChatMessage[]
  isLoading: boolean
  pendingTools: PendingToolCall[]
  onSendMessage: (message: string, images?: ImageInput[]) => void
  onApproveTools: (tools: PendingToolCall[]) => void
  onRejectTools: () => void
  llmProvider: string
  onProviderChange: (provider: string) => void
  toolMode: 'auto' | 'manual' | 'ai_decide'
  onToolModeChange: (mode: 'auto' | 'manual' | 'ai_decide') => void
  contextFormat: 'xml' | 'json' | 'plain'
  onContextFormatChange: (format: 'xml' | 'json' | 'plain') => void
  onDeleteMessage: (index: number) => void
  onEditMessage: (index: number, newContent: string) => void
  onRerunMessage: (index: number) => void
  onClearHistory: () => void
  onSummarize: () => void
  isSummarizing: boolean
  onScrollToCell?: (cellId: string) => void
  onPanelClick?: () => void
  streamStatus?: string | null  // Real-time SSE status (e.g., "Analyzing...", "Running tool: X...")
}

// Theme-aware colors for chat panel - uses CSS variables
const themeColors = {
  dark: {
    panelBg: 'var(--nb-bg-primary)',
    headerBg: 'var(--nb-bg-secondary)',
    messagesBg: 'var(--nb-bg-primary)',
    inputBg: 'var(--nb-bg-secondary)',
    assistantBubble: 'var(--nb-bg-secondary)',
    border: 'var(--nb-border-default)',
  },
  light: {
    panelBg: 'var(--nb-bg-primary)',
    headerBg: 'var(--nb-bg-secondary)',
    messagesBg: 'var(--nb-bg-primary)',
    inputBg: 'var(--nb-bg-secondary)',
    assistantBubble: 'var(--nb-bg-code-cell)',
    border: 'var(--nb-border-default)',
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
  contextFormat,
  onContextFormatChange,
  onDeleteMessage,
  onEditMessage,
  onRerunMessage,
  onClearHistory,
  onSummarize,
  isSummarizing,
  onScrollToCell,
  onPanelClick,
  streamStatus,
}: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const [images, setImages] = useState<ImageInput[]>([])
  const [enlargedImage, setEnlargedImage] = useState<ImageInput | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const editTextareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
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

  // Handle Escape key to close enlarged image
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && enlargedImage) {
        setEnlargedImage(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enlargedImage])

  // Process image file to base64
  const processImageFile = (file: File): Promise<ImageInput> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const result = e.target?.result as string
        const base64Data = result.split(',')[1]
        resolve({
          data: base64Data,
          mime_type: file.type || 'image/png',
          filename: file.name
        })
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(file)
    })
  }

  // Handle paste event for images
  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) {
          try {
            const imageInput = await processImageFile(file)
            setImages(prev => [...prev, imageInput])
          } catch (error) {
            console.error('Failed to process pasted image:', error)
          }
        }
        break
      }
    }
  }

  // Handle drag events
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    for (const file of files) {
      if (file.type.startsWith('image/')) {
        try {
          const imageInput = await processImageFile(file)
          setImages(prev => [...prev, imageInput])
        } catch (error) {
          console.error('Failed to process dropped image:', error)
        }
      }
    }
  }

  // Handle file input change
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    for (const file of files) {
      if (file.type.startsWith('image/')) {
        try {
          const imageInput = await processImageFile(file)
          setImages(prev => [...prev, imageInput])
        } catch (error) {
          console.error('Failed to process selected image:', error)
        }
      }
    }
    // Reset input so same file can be selected again
    e.target.value = ''
  }

  // Remove an image
  const removeImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if ((!input.trim() && images.length === 0) || isLoading) return
    onSendMessage(input.trim(), images.length > 0 ? images : undefined)
    setInput('')
    setImages([])
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
        <summary className="cursor-pointer flex items-center gap-1.5 transition-colors" style={{ color: 'var(--nb-text-muted)' }}>
          <Wrench className="w-3.5 h-3.5" />
          {summaryText}
        </summary>
        <div className="mt-2 space-y-2 ml-2 pl-3" style={{ borderLeft: '2px solid var(--nb-border-default)' }}>
          {steps.map((step, idx) => (
            <div key={idx} style={{ color: 'var(--nb-text-muted)' }}>
              <span className="font-medium flex items-center gap-1.5" style={{ color: 'var(--nb-text-secondary)' }}>
                {step.type === 'tool_call' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'color-mix(in srgb, var(--nb-accent-code) 20%, transparent)', color: 'var(--nb-accent-code)' }}>⚡</span>
                )}
                {step.type === 'tool_result' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'color-mix(in srgb, var(--nb-accent-success) 20%, transparent)', color: 'var(--nb-accent-success)' }}>✓</span>
                )}
                {step.type === 'text' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'color-mix(in srgb, var(--nb-accent-markdown) 20%, transparent)', color: 'var(--nb-accent-markdown)' }}>💭</span>
                )}
                {step.name || step.type}
              </span>
              <pre className="mt-1.5 text-[11px] rounded-md p-2 whitespace-pre-wrap break-words overflow-hidden font-mono" style={{ backgroundColor: 'var(--nb-bg-output)', color: 'var(--nb-text-secondary)' }}>
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
          className="cell-reference"
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

  // Detect if content is an error message (JSON or common error patterns)
  const parseErrorMessage = useCallback((content: string): { isError: boolean; title: string; details: string } | null => {
    // Check for JSON error format
    try {
      const parsed = JSON.parse(content)
      if (parsed.error || parsed.message || parsed.detail) {
        const errorMsg = parsed.error?.message || parsed.message || parsed.detail || 'Unknown error'
        const errorType = parsed.error?.type || parsed.error?.code || parsed.status || 'Error'
        return {
          isError: true,
          title: typeof errorType === 'string' ? errorType.replace(/_/g, ' ') : 'Error',
          details: typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg, null, 2)
        }
      }
    } catch {
      // Not JSON, check for common error patterns
    }

    // Check for common error patterns in text
    const errorPatterns = [
      /^Error:\s*(.+)/i,
      /^(Resource Exhausted|Rate Limited|Quota Exceeded|API Error|Connection Failed|Timeout)[\s:]*(.*)$/i,
      /^(429|500|502|503|504)\s*[-:]\s*(.+)/i,
    ]

    for (const pattern of errorPatterns) {
      const match = content.match(pattern)
      if (match) {
        return {
          isError: true,
          title: match[1] || 'Error',
          details: match[2] || content
        }
      }
    }

    return null
  }, [])

  // Render message content with clickable cell references
  const renderMessageContent = useCallback((content: string) => {
    // Parse markdown and sanitize HTML (same approach as AICell)
    const html = marked.parse(content) as string

    // Process cell references in multiple formats:
    // 1. [cell:xxx] format
    // 2. `cell-xxx` format (backticks)
    // 3. **`cell-xxx`** format (bold backticks)
    // Note: Using data-cellid (no hyphen) because DOMPurify normalizes attribute names
    let processedHtml = html
      // Format 1: [cell:xxx]
      .replace(
        /\[cell:([a-f0-9-]+)\]/gi,
        (match, cellId) => {
          return `<button class="cell-ref-btn" data-cellid="cell-${cellId}">📍 cell-${cellId}</button>`
        }
      )
      // Format 2 & 3: `cell-xxx` or <code>cell-xxx</code> (after markdown parsing)
      .replace(
        /<code>(cell-[a-zA-Z0-9_-]+)<\/code>/gi,
        (match, cellId) => {
          return `<button class="cell-ref-btn" data-cellid="${cellId}">📍 ${cellId}</button>`
        }
      )

    const sanitizedHtml = DOMPurify.sanitize(processedHtml, {
      ADD_TAGS: ['button'],
      ADD_ATTR: ['data-cellid', 'class', 'style']
    })
    return sanitizedHtml
  }, [])

  // Handle clicks on cell reference buttons in messages
  const handleMessageClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    console.log('[ChatPanel] Click on:', target.tagName, target.className)
    if (target.classList.contains('cell-ref-btn')) {
      const cellId = target.dataset.cellid  // lowercase because HTML attributes are case-insensitive
      console.log('[ChatPanel] Cell ref clicked, cellId:', cellId)
      if (cellId && onScrollToCell) {
        console.log('[ChatPanel] Calling onScrollToCell with:', cellId)
        onScrollToCell(cellId)
      }
    }
  }, [onScrollToCell])

  // Text colors based on theme - use CSS variables
  const textPrimary = 'var(--nb-text-primary)'
  const textSecondary = 'var(--nb-text-secondary)'
  const textMuted = 'var(--nb-text-muted)'

  return (
    <div
      className="chat-panel flex flex-col h-full"
      style={{
        backgroundColor: colors.panelBg,
        borderLeft: `1px solid ${colors.border}`,
      }}
      onClick={onPanelClick}
    >
      {/* Header */}
      <div className="px-3 py-2 backdrop-blur-sm" style={{ background: colors.headerBg, borderBottom: `1px solid ${colors.border}` }}>
        {/* Main header row - Clean */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(to bottom right, var(--app-accent-primary), var(--nb-accent-context))', boxShadow: '0 10px 15px -3px color-mix(in srgb, var(--app-accent-primary) 20%, transparent)' }}>
              <MessageSquare className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-base font-semibold" style={{ color: textPrimary }}>AI Assistant</h2>
          </div>
          <div className="flex items-center gap-2">
            {/* Tool Mode Selector */}
            <div className="flex items-center gap-1.5">
              <Wrench className="w-3.5 h-3.5" style={{ color: textMuted }} />
              <select
                value={toolMode}
                onChange={(e) => onToolModeChange(e.target.value as 'auto' | 'manual' | 'ai_decide')}
                className="text-xs rounded-md px-2 py-1 border focus:outline-none transition-all cursor-pointer"
                style={{
                  backgroundColor: colors.inputBg,
                  borderColor: colors.border,
                  color: textPrimary,
                }}
                title="Tool Execution Mode"
              >
                <option value="auto">Auto</option>
                <option value="manual">Manual</option>
                <option value="ai_decide">AI Decide</option>
              </select>
            </div>
            {/* Summarize button */}
            <button
              onClick={onSummarize}
              disabled={isSummarizing}
              className="p-1.5 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
              style={{ backgroundColor: 'color-mix(in srgb, var(--nb-accent-ai) 20%, transparent)', color: 'var(--nb-accent-ai)' }}
              title="Generate AI summary of notebook"
            >
              {isSummarizing ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
            </button>
            {/* Clear button */}
            <button
              onClick={onClearHistory}
              className="p-1.5 rounded-lg transition-all hover:opacity-80"
              style={{ color: textMuted }}
              title="Clear chat history"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3" style={{ backgroundColor: colors.messagesBg }}>
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(to bottom right, color-mix(in srgb, var(--app-accent-primary) 20%, transparent), color-mix(in srgb, var(--nb-accent-context) 20%, transparent))', border: '1px solid color-mix(in srgb, var(--app-accent-primary) 20%, transparent)' }}>
              <MessageSquare className="w-8 h-8" style={{ color: 'var(--app-accent-primary)' }} strokeWidth={1.5} />
            </div>
            <h3 className="text-lg font-medium mb-2" style={{ color: textPrimary }}>Welcome!</h3>
            <p className="mb-4" style={{ color: textSecondary }}>I can help with your notebook:</p>
            <div className="inline-flex flex-col items-start text-sm space-y-2 rounded-xl p-4" style={{ backgroundColor: theme === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.05)', border: `1px solid ${colors.border}`, color: textSecondary }}>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded flex items-center justify-center text-xs" style={{ backgroundColor: 'color-mix(in srgb, var(--app-accent-primary) 20%, transparent)', color: 'var(--app-accent-primary)' }}>?</span>
                <span>Answer questions about selected cells</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded flex items-center justify-center text-xs" style={{ backgroundColor: 'color-mix(in srgb, var(--app-accent-success) 20%, transparent)', color: 'var(--app-accent-success)' }}>⌘</span>
                <span>Write and edit code</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded flex items-center justify-center text-xs" style={{ backgroundColor: 'color-mix(in srgb, var(--app-accent-secondary) 20%, transparent)', color: 'var(--app-accent-secondary)' }}>▶</span>
                <span>Execute cells automatically</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded flex items-center justify-center text-xs" style={{ backgroundColor: 'color-mix(in srgb, var(--app-accent-warning) 20%, transparent)', color: 'var(--app-accent-warning)' }}>📝</span>
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
              <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center shadow-lg" style={msg.role === 'user'
                ? { background: 'linear-gradient(to bottom right, var(--app-accent-primary), color-mix(in srgb, var(--app-accent-primary) 85%, black))', boxShadow: '0 10px 15px -3px color-mix(in srgb, var(--app-accent-primary) 20%, transparent)' }
                : { background: 'linear-gradient(to bottom right, var(--app-accent-success), var(--nb-accent-context))', boxShadow: '0 10px 15px -3px color-mix(in srgb, var(--app-accent-success) 20%, transparent)' }
              }>
                {msg.role === 'user' ? (
                  <User className="w-4 h-4 text-white" />
                ) : (
                  <Lightbulb className="w-4 h-4 text-white" />
                )}
              </div>

              {/* Message content */}
              <div className={`flex flex-col gap-1 ${editingIndex === idx ? 'flex-1' : ''}`}>
                <div
                  className={`rounded-2xl px-4 py-2.5 shadow-lg ${
                    msg.role === 'user'
                      ? 'text-white rounded-tr-md'
                      : 'rounded-tl-md'
                  } ${editingIndex === idx ? 'w-full' : ''}`}
                  style={msg.role === 'user' ? {
                    background: 'linear-gradient(to bottom right, var(--app-accent-primary), color-mix(in srgb, var(--app-accent-primary) 85%, black))',
                  } : msg.role === 'assistant' ? {
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
                          className="text-xs px-3 py-1.5 text-white rounded-lg transition-colors hover:opacity-80"
                          style={{ backgroundColor: 'var(--app-accent-success)' }}
                        >
                          Save
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="text-xs px-3 py-1.5 text-white rounded-lg transition-colors hover:opacity-80"
                          style={{ backgroundColor: 'var(--app-bg-tertiary)' }}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      {msg.role === 'assistant' ? (
                        // Check if message is an error
                        (() => {
                          const errorInfo = parseErrorMessage(msg.content)
                          if (errorInfo) {
                            return (
                              <div
                                className="rounded-lg overflow-hidden"
                                style={{
                                  backgroundColor: 'color-mix(in srgb, var(--app-accent-error) 10%, transparent)',
                                  border: '1px solid color-mix(in srgb, var(--app-accent-error) 30%, transparent)',
                                }}
                              >
                                {/* Error header */}
                                <div
                                  className="flex items-center gap-2 px-3 py-2"
                                  style={{
                                    backgroundColor: 'color-mix(in srgb, var(--app-accent-error) 15%, transparent)',
                                    borderBottom: '1px solid color-mix(in srgb, var(--app-accent-error) 20%, transparent)',
                                  }}
                                >
                                  <AlertTriangle className="w-4 h-4" style={{ color: 'var(--nb-accent-error)' }} />
                                  <span className="text-sm font-medium" style={{ color: 'var(--nb-accent-error)' }}>
                                    {errorInfo.title}
                                  </span>
                                </div>
                                {/* Error message */}
                                <div className="px-3 py-2">
                                  <p className="text-sm" style={{ color: 'var(--nb-text-secondary)' }}>
                                    {errorInfo.details}
                                  </p>
                                </div>
                                {/* Raw details toggle */}
                                {msg.content.includes('{') && (
                                  <details className="px-3 pb-2">
                                    <summary
                                      className="text-xs cursor-pointer"
                                      style={{ color: 'var(--nb-text-muted)' }}
                                    >
                                      Show raw details
                                    </summary>
                                    <pre
                                      className="mt-2 text-xs p-2 rounded overflow-x-auto"
                                      style={{
                                        backgroundColor: 'rgba(0, 0, 0, 0.2)',
                                        color: 'var(--nb-text-muted)',
                                      }}
                                    >
                                      {msg.content}
                                    </pre>
                                  </details>
                                )}
                              </div>
                            )
                          }
                          // Normal message rendering
                          return (
                            <div
                              className="prose prose-sm max-w-none prose-invert"
                              style={{ color: 'var(--nb-text-primary)' }}
                              dangerouslySetInnerHTML={{ __html: renderMessageContent(msg.content) }}
                              onClick={handleMessageClick}
                            />
                          )
                        })()
                      ) : (
                        <div className="text-sm whitespace-pre-wrap leading-relaxed">
                          {msg.content}
                        </div>
                      )}
                      {/* Show images attached to user messages */}
                      {msg.role === 'user' && msg.images && msg.images.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {msg.images.map((img, imgIdx) => (
                            <img
                              key={imgIdx}
                              src={`data:${img.mime_type};base64,${img.data}`}
                              alt={img.filename || `Image ${imgIdx + 1}`}
                              className="w-16 h-16 object-cover rounded-lg border border-white/20 cursor-pointer hover:opacity-80 transition-opacity"
                              onClick={() => setEnlargedImage(img)}
                            />
                          ))}
                        </div>
                      )}
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
                      className="text-[10px] p-1.5 rounded-md transition-all hover:opacity-80"
                      style={{ color: 'var(--nb-text-muted)' }}
                      title="Copy message"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                    {/* Re-run button - only for last user message */}
                    {msg.role === 'user' && idx === lastUserMessageIndex && (
                      <button
                        onClick={() => onRerunMessage(idx)}
                        className="text-[10px] p-1.5 rounded-md transition-all hover:opacity-80"
                        style={{ color: 'var(--nb-accent-code)' }}
                        title="Re-run this message"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    )}
                    {/* Edit button */}
                    <button
                      onClick={() => startEditing(idx, msg.content)}
                      className="text-[10px] p-1.5 rounded-md transition-all hover:opacity-80"
                      style={{ color: 'var(--nb-accent-warning)' }}
                      title="Edit message"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    {/* Delete button - only for user messages */}
                    {msg.role === 'user' && (
                      <button
                        onClick={() => onDeleteMessage(idx)}
                        className="text-[10px] p-1.5 rounded-md transition-all hover:opacity-80"
                        style={{ color: 'var(--nb-accent-error)' }}
                        title="Delete message and responses"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
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
          <div className="rounded-xl p-4 shadow-lg animate-fadeIn" style={{ backgroundColor: 'color-mix(in srgb, var(--app-accent-warning) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--app-accent-warning) 30%, transparent)', boxShadow: '0 10px 15px -3px color-mix(in srgb, var(--app-accent-warning) 5%, transparent)' }}>
            <div className="flex items-center gap-2 text-sm font-medium mb-3" style={{ color: 'var(--app-accent-warning)' }}>
              <AlertTriangle className="w-5 h-5" />
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
                    className="mt-0.5 w-4 h-4 rounded focus:ring-offset-0"
                    style={{ borderColor: 'var(--app-text-muted)', accentColor: 'var(--app-accent-primary)' }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-white text-sm">{tool.name}</div>
                    <details className="text-xs mt-1" style={{ color: 'var(--app-text-muted)' }}>
                      <summary className="cursor-pointer" style={{ color: 'var(--app-text-muted)' }}>View arguments</summary>
                      <pre className="mt-2 rounded-lg p-2 whitespace-pre-wrap break-words overflow-hidden text-[11px] font-mono" style={{ backgroundColor: 'rgba(0, 0, 0, 0.3)', color: 'var(--nb-text-secondary)' }}>
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
                className="flex-1 px-4 py-2 text-sm disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium hover:opacity-80"
                style={{ backgroundColor: selectedTools.size === 0 ? 'var(--app-bg-tertiary)' : 'var(--app-accent-success)', boxShadow: selectedTools.size > 0 ? '0 10px 15px -3px color-mix(in srgb, var(--app-accent-success) 20%, transparent)' : 'none' }}
              >
                Approve ({selectedTools.size})
              </button>
              <button
                onClick={onRejectTools}
                className="flex-1 px-4 py-2 text-sm text-white rounded-lg transition-colors font-medium hover:opacity-80"
                style={{ backgroundColor: 'var(--app-accent-error)' }}
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {/* Loading indicator with real-time SSE status */}
        {isLoading && (
          <div className="flex justify-start animate-fadeIn">
            <div className="flex items-start gap-2.5">
              <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, var(--nb-accent-success), var(--nb-accent-context))' }}>
                <Lightbulb className="w-4 h-4 text-white" />
              </div>
              <div className="rounded-2xl rounded-tl-md px-4 py-3 shadow-lg" style={{ backgroundColor: 'var(--nb-bg-secondary)', border: '1px solid var(--nb-border-default)' }}>
                <div className="flex items-center gap-2" style={{ color: 'var(--nb-text-muted)' }}>
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--nb-accent-code)', animationDelay: '0ms' }}></span>
                    <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--nb-accent-code)', animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 rounded-full animate-bounce" style={{ backgroundColor: 'var(--nb-accent-code)', animationDelay: '300ms' }}></span>
                  </div>
                  <span className="text-sm">{streamStatus || 'Thinking...'}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div
        className="p-2"
        style={{
          background: colors.inputBg,
          borderTop: `1px solid ${colors.border}`,
        }}
      >
        <form
          onSubmit={handleSubmit}
          className="rounded-lg p-2"
          style={{
            backgroundColor: theme === 'light' ? 'rgba(0,0,0,0.02)' : 'rgba(255,255,255,0.03)',
            border: `1px solid ${colors.border}`,
          }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Image previews */}
          {images.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {images.map((img, idx) => (
                <div key={idx} className="relative group">
                  <img
                    src={`data:${img.mime_type};base64,${img.data}`}
                    alt={img.filename || `Image ${idx + 1}`}
                    className="w-16 h-16 object-cover rounded-lg border cursor-pointer hover:opacity-80 transition-opacity"
                    style={{ borderColor: colors.border }}
                    onClick={() => setEnlargedImage(img)}
                  />
                  <button
                    type="button"
                    onClick={() => removeImage(idx)}
                    className="absolute -top-2 -right-2 w-5 h-5 text-white rounded-full text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ backgroundColor: 'var(--app-accent-error)' }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className={`flex gap-2 relative ${isDragging ? 'opacity-50' : ''}`}>
            {/* Drag overlay */}
            {isDragging && (
              <div className="absolute inset-0 flex items-center justify-center rounded-xl border-2 border-dashed z-10" style={{ borderColor: 'var(--app-accent-primary)', backgroundColor: 'color-mix(in srgb, var(--app-accent-primary) 10%, transparent)' }}>
                <span className="text-sm font-medium" style={{ color: 'var(--app-accent-primary)' }}>Drop image here</span>
              </div>
            )}

            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Ask AI for help... (Enter to send, Shift+Enter for new line)"
                className="w-full rounded-lg px-3 py-2 text-sm resize-none focus:outline-none transition-all"
                style={{
                  minHeight: '56px',
                  maxHeight: '150px',
                  backgroundColor: 'var(--nb-bg-primary)',
                  border: `1px solid var(--nb-border-default)`,
                  color: textPrimary,
                  outline: 'none',
                }}
                disabled={isLoading}
              />
            </div>
            <div className="flex flex-col items-center gap-2 justify-end">
              {/* Image upload button */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                onChange={handleFileSelect}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="p-2 rounded-lg transition-all border border-transparent hover:opacity-80"
                style={{ color: textMuted }}
                title="Attach image (paste or drop also works)"
              >
                <Image className="w-5 h-5" />
              </button>
              <button
                type="submit"
                disabled={(!input.trim() && images.length === 0) || isLoading}
                className="p-2.5 disabled:cursor-not-allowed text-white rounded-lg transition-all hover:opacity-80"
                style={{
                  background: (!input.trim() && images.length === 0) || isLoading
                    ? 'var(--app-bg-tertiary)'
                    : 'linear-gradient(to right, var(--app-accent-primary), color-mix(in srgb, var(--app-accent-primary) 85%, black))',
                  boxShadow: (!input.trim() && images.length === 0) || isLoading
                    ? 'none'
                    : '0 4px 6px -1px color-mix(in srgb, var(--app-accent-primary) 20%, transparent)',
                }}
                title="Send message (Enter)"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Helper text */}
          <div className="flex items-center justify-between mt-2 px-1">
            <span className="text-[10px]" style={{ color: textMuted }}>
              Enter to send • Shift+Enter for new line • Paste/drop images
            </span>
          </div>
        </form>
      </div>

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

      {/* Enlarged image modal */}
      {enlargedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setEnlargedImage(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            <img
              src={`data:${enlargedImage.mime_type};base64,${enlargedImage.data}`}
              alt={enlargedImage.filename || 'Enlarged image'}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
            />
            <button
              onClick={() => setEnlargedImage(null)}
              className="absolute top-2 right-2 w-8 h-8 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center transition-colors"
            >
              ×
            </button>
            {enlargedImage.filename && (
              <div className="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
                {enlargedImage.filename}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
