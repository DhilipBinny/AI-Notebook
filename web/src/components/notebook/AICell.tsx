'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Copy,
  Check,
  ChevronUp,
  ChevronDown,
  Play,
  X,
  Lightbulb,
  Plus,
  Settings,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Cell as CellType, AICellData, ImageInput, LLMStep, ThinkingStep } from '@/types'

// Configure marked
marked.setOptions({
  gfm: true,
  breaks: true,
})

interface AICellProps {
  cell: CellType
  index: number
  isSelected: boolean
  onSelect: () => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onUpdate: (updates: Partial<CellType>) => void
  onRunAICell: (cellId: string, prompt: string, images?: ImageInput[]) => Promise<void>
  onCancelAICell?: (cellId: string) => Promise<void>
  onInsertCodeCells: (afterCellId: string, codeBlocks: string[]) => void
  onScrollToCell?: (cellId: string) => void
}

export default function AICell({
  cell,
  index,
  isSelected,
  onSelect,
  onDelete,
  onMoveUp,
  onMoveDown,
  onUpdate,
  onRunAICell,
  onCancelAICell,
  onInsertCodeCells,
  onScrollToCell,
}: AICellProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const responseRef = useRef<HTMLDivElement>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [localPrompt, setLocalPrompt] = useState(cell.ai_data?.user_prompt || '')
  const [images, setImages] = useState<ImageInput[]>(cell.ai_data?.images || [])
  const [imagesLoading, setImagesLoading] = useState(0) // Count of images currently being processed

  // Image modal state
  const [enlargedImage, setEnlargedImage] = useState<ImageInput | null>(null)

  // Copy feedback state
  const [copiedPrompt, setCopiedPrompt] = useState(false)
  const [copiedResponse, setCopiedResponse] = useState(false)

  // Copy to clipboard with feedback
  const copyToClipboard = useCallback((text: string, type: 'prompt' | 'response') => {
    navigator.clipboard.writeText(text)
    if (type === 'prompt') {
      setCopiedPrompt(true)
      setTimeout(() => setCopiedPrompt(false), 2000)
    } else {
      setCopiedResponse(true)
      setTimeout(() => setCopiedResponse(false), 2000)
    }
  }, [])

  const aiData = cell.ai_data || {
    user_prompt: '',
    llm_response: '',
    status: 'idle' as const,
  }

  // Update local prompt when cell changes
  useEffect(() => {
    setLocalPrompt(cell.ai_data?.user_prompt || '')
  }, [cell.ai_data?.user_prompt])

  // Update images when cell changes (e.g., on page reload)
  useEffect(() => {
    setImages(cell.ai_data?.images || [])
  }, [cell.ai_data?.images])

  // Debug: log thinkingSteps changes during streaming
  useEffect(() => {
    if (aiData.status === 'running' && aiData.streamState?.thinkingSteps) {
      console.log('[AICell UI] thinkingSteps count:', aiData.streamState.thinkingSteps.length)
    }
  }, [aiData.status, aiData.streamState?.thinkingSteps])

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px'
    }
  }, [])

  useEffect(() => {
    adjustTextareaHeight()
  }, [localPrompt, adjustTextareaHeight])

  // Focus textarea when editing
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isEditing])

  // Close enlarged image on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && enlargedImage) {
        setEnlargedImage(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enlargedImage])

  // Process a file and add it as an image
  const addImageFile = useCallback((file: File) => {
    // Increment loading counter before starting async operation
    setImagesLoading(prev => prev + 1)

    const reader = new FileReader()

    reader.onload = () => {
      try {
        const dataUrl = reader.result as string

        // Validate DataURL format
        if (!dataUrl || !dataUrl.includes(',') || !dataUrl.includes(':') || !dataUrl.includes(';')) {
          console.error('[AICell] Invalid DataURL format')
          setImagesLoading(prev => Math.max(0, prev - 1))
          return
        }

        // Extract base64 data (remove "data:image/png;base64," prefix)
        const base64 = dataUrl.split(',')[1]
        const mimeType = dataUrl.split(';')[0].split(':')[1]

        // Validate extracted data
        if (!base64 || base64.length === 0) {
          console.error('[AICell] Empty base64 data')
          setImagesLoading(prev => Math.max(0, prev - 1))
          return
        }

        if (!mimeType || !mimeType.startsWith('image/')) {
          console.error('[AICell] Invalid mime type:', mimeType)
          setImagesLoading(prev => Math.max(0, prev - 1))
          return
        }

        const filename = file.name || `image-${Date.now()}.${mimeType.split('/')[1]}`

        const newImage: ImageInput = {
          data: base64,
          mime_type: mimeType,
          filename: filename
        }

        setImages(prev => [...prev, newImage])
      } catch (err) {
        console.error('[AICell] Error processing image:', err)
      } finally {
        // Decrement loading counter when done (success or failure)
        setImagesLoading(prev => Math.max(0, prev - 1))
      }
    }

    reader.onerror = () => {
      console.error('[AICell] FileReader error')
      setImagesLoading(prev => Math.max(0, prev - 1))
    }

    reader.readAsDataURL(file)
  }, [])

  // Handle paste event for images (supports multiple images)
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    let hasImage = false
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        hasImage = true
        const file = item.getAsFile()
        if (file) {
          addImageFile(file)
        }
      }
    }

    // Only prevent default if we handled images
    if (hasImage) {
      e.preventDefault()
    }
  }, [addImageFile])

  // Handle drag and drop for images
  const [isDragging, setIsDragging] = useState(false)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer?.files
    if (!files) return

    let hasImage = false
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      if (file.type.startsWith('image/')) {
        addImageFile(file)
        hasImage = true
      }
    }

    // Enter edit mode when images are dropped
    if (hasImage) {
      setIsEditing(true)
    }
  }, [addImageFile])

  // Remove image
  const removeImage = useCallback((index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index))
  }, [])

  // Handle run
  const handleRun = async () => {
    // Don't run if no content
    if (!localPrompt.trim() && images.length === 0) return

    // Don't run if images are still loading
    if (imagesLoading > 0) {
      console.log('[AICell] Waiting for images to finish loading...')
      return
    }

    // Update cell with prompt, images, and running status
    onUpdate({
      ai_data: {
        ...aiData,
        user_prompt: localPrompt,
        images: images.length > 0 ? images : undefined,
        status: 'running',
      },
    })

    setIsEditing(false)
    await onRunAICell(cell.id, localPrompt, images.length > 0 ? images : undefined)
  }

  // Handle cancel
  const handleCancel = async () => {
    if (onCancelAICell && aiData.status === 'running') {
      await onCancelAICell(cell.id)
    }
  }

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault()
      handleRun()
    }
    if (e.key === 'Escape') {
      setIsEditing(false)
    }
  }

  // Extract code blocks from response
  const extractCodeBlocks = (markdown: string): { code: string; language: string }[] => {
    const blocks: { code: string; language: string }[] = []
    const regex = /```(\w*)\n([\s\S]*?)```/g
    let match
    while ((match = regex.exec(markdown)) !== null) {
      blocks.push({
        language: match[1] || 'python',
        code: match[2].trim(),
      })
    }
    return blocks
  }

  // Process cell-xxx references into clickable links
  const processeCellReferences = (html: string): string => {
    // Match cell ID patterns: @cell-xxx, `cell-xxx`, or plain cell-xxx
    // Cell ID formats: cell-14d6c2b447d1 or cell-1764863866351-wq1kuzp8k
    const cellRefRegex = /(?:@|`)(cell-[a-zA-Z0-9-]+)`?/g
    return html.replace(cellRefRegex, (match, cellId) => {
      return `<button class="cell-reference" data-cell-id="${cellId}">${match}</button>`
    })
  }

  // Handle click on cell references
  const handleResponseClick = useCallback((e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    console.log('[AICell] Click detected on:', target.tagName, target.classList.toString())
    if (target.classList.contains('cell-reference')) {
      const cellId = target.getAttribute('data-cell-id')
      console.log('[AICell] Cell reference clicked, cellId:', cellId, 'onScrollToCell:', !!onScrollToCell)
      if (cellId && onScrollToCell) {
        e.stopPropagation()
        e.preventDefault()
        onScrollToCell(cellId)
      }
    }
  }, [onScrollToCell])

  // Render LLM steps (tool calls and results)
  const renderSteps = (steps: LLMStep[]) => {
    if (!steps || steps.length === 0) return null

    const toolNames = [...new Set(steps.filter(s => s.name).map(s => s.name))]
    const summaryText = toolNames.length > 0
      ? `Used ${toolNames.length} tool${toolNames.length > 1 ? 's' : ''}: ${toolNames.join(', ')}`
      : `${steps.length} step${steps.length > 1 ? 's' : ''}`

    return (
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer flex items-center gap-1.5 transition-colors" style={{ color: 'var(--nb-text-muted)' }}>
          <Settings className="w-3.5 h-3.5" />
          {summaryText}
        </summary>
        <div className="mt-2 space-y-2 ml-2 pl-3" style={{ borderLeft: '2px solid var(--nb-border-default)' }}>
          {steps.map((step, idx) => (
            <div key={idx} style={{ color: 'var(--nb-text-muted)' }}>
              <span className="font-medium flex items-center gap-1.5" style={{ color: 'var(--nb-text-secondary)' }}>
                {step.type === 'tool_call' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'rgba(168, 85, 247, 0.2)', color: '#a855f7' }}>⚡</span>
                )}
                {step.type === 'tool_result' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'rgba(166, 227, 161, 0.2)', color: 'var(--nb-accent-success)' }}>✓</span>
                )}
                {step.type === 'text' && (
                  <span className="w-5 h-5 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'rgba(203, 166, 247, 0.2)', color: 'var(--nb-accent-markdown)' }}>💭</span>
                )}
                {step.name || step.type}
              </span>
              <pre className="mt-1.5 text-[11px] rounded-md p-2 whitespace-pre-wrap break-words overflow-hidden font-mono" style={{ backgroundColor: 'var(--nb-bg-ai-cell)', color: 'var(--nb-text-secondary)' }}>
                {step.content.slice(0, 500)}
                {step.content.length > 500 && '...'}
              </pre>
            </div>
          ))}
        </div>
      </details>
    )
  }

  // Render LLM thinking/reasoning steps (collapsible)
  const renderThinking = (thinkingSteps: ThinkingStep[]) => {
    if (!thinkingSteps || thinkingSteps.length === 0) return null

    // Group by iteration and create summary
    const iterations = [...new Set(thinkingSteps.map(s => s.iteration))].sort((a, b) => a - b)
    const totalChars = thinkingSteps.reduce((sum, s) => sum + s.content.length, 0)
    const summaryText = `Thinking: ${iterations.length} iteration${iterations.length > 1 ? 's' : ''} (${Math.round(totalChars / 1000)}k chars)`

    return (
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer flex items-center gap-1.5 transition-colors" style={{ color: 'var(--nb-text-muted)' }}>
          <span className="w-4 h-4 rounded flex items-center justify-center text-[10px]" style={{ backgroundColor: 'rgba(147, 51, 234, 0.2)', color: '#9333ea' }}>💭</span>
          {summaryText}
        </summary>
        <div className="mt-2 space-y-3 ml-2 pl-3" style={{ borderLeft: '2px solid rgba(147, 51, 234, 0.3)' }}>
          {iterations.map(iteration => {
            const iterSteps = thinkingSteps.filter(s => s.iteration === iteration)
            const combinedContent = iterSteps.map(s => s.content).join('\n\n')
            return (
              <div key={iteration}>
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold" style={{ backgroundColor: '#9333ea', color: '#fff' }}>
                    {iteration}
                  </span>
                  <span className="font-medium" style={{ color: '#9333ea' }}>Iteration {iteration}</span>
                  <span style={{ color: 'var(--nb-text-muted)' }}>({Math.round(combinedContent.length / 1000)}k chars)</span>
                </div>
                <div
                  className="text-[11px] rounded-md p-2 whitespace-pre-wrap break-words overflow-hidden font-mono max-h-[300px] overflow-y-auto"
                  style={{ backgroundColor: 'rgba(147, 51, 234, 0.05)', color: 'var(--nb-text-secondary)', border: '1px solid rgba(147, 51, 234, 0.2)' }}
                >
                  {combinedContent.slice(0, 5000)}
                  {combinedContent.length > 5000 && '\n\n... (truncated)'}
                </div>
              </div>
            )
          })}
        </div>
      </details>
    )
  }

  // Render response with code block actions
  const renderResponse = () => {
    if (!aiData.llm_response) return null

    const html = marked.parse(aiData.llm_response) as string
    // Process cell references before sanitizing
    const processedHtml = processeCellReferences(html)
    // Allow button elements and data attributes in sanitized HTML
    const sanitizedHtml = DOMPurify.sanitize(processedHtml, {
      ADD_TAGS: ['button'],
      ADD_ATTR: ['data-cell-id', 'class', 'style']
    })
    const codeBlocks = extractCodeBlocks(aiData.llm_response)

    return (
      <div className="space-y-2">
        <div
          ref={responseRef}
          className="prose prose-sm max-w-none prose-invert ai-response-prose"
          style={{ color: 'var(--nb-text-primary)' }}
          dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
          onClick={handleResponseClick}
        />

        {/* Code block actions */}
        {codeBlocks.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t" style={{ borderColor: 'var(--nb-border-default)' }}>
            <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
              {codeBlocks.length} code block{codeBlocks.length > 1 ? 's' : ''}
            </span>
            <button
              onClick={() => onInsertCodeCells(cell.id, codeBlocks.map(b => b.code))}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded hover:opacity-80 transition-opacity font-medium"
              style={{
                backgroundColor: 'var(--nb-accent-code)',
                color: '#11111b',
              }}
              title={codeBlocks.length > 1
                ? `Insert all ${codeBlocks.length} code blocks as new cells`
                : 'Insert code as new cell'}
            >
              <Plus className="w-3.5 h-3.5" />
              Insert {codeBlocks.length > 1 ? `All ${codeBlocks.length} Cells` : 'Code'}
            </button>
          </div>
        )}

        {/* Model info */}
        {aiData.model && (
          <div className="text-xs pt-1" style={{ color: 'var(--nb-text-muted)' }}>
            Model: {aiData.model}
          </div>
        )}
      </div>
    )
  }

  // Get selection style
  const getSelectionStyle = () => {
    if (!isSelected) {
      return {
        borderLeft: '3px solid transparent',
        boxShadow: 'none',
      }
    }
    return {
      borderLeft: '3px solid #a855f7', // purple for AI cells
      boxShadow: '0 0 12px rgba(168, 85, 247, 0.3), inset 0 0 0 1px rgba(168, 85, 247, 0.1)',
    }
  }

  // Cell ID already includes 'cell-' prefix (e.g., 'cell-1764683711390-swbvvzf58')
  // Use it directly as the DOM element ID
  return (
    <div
      id={cell.id}
      className="group rounded-lg transition-all overflow-hidden cell-wrapper cell-ai relative"
      onClick={onSelect}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        backgroundColor: 'var(--nb-bg-ai-cell, #2a1f4e)',
        borderColor: 'var(--nb-border-default)',
        ...getSelectionStyle(),
      }}
    >
      {/* Drag overlay - shown when dragging anywhere on the cell */}
      {isDragging && (
        <div
          className="absolute inset-0 z-20 flex items-center justify-center rounded-lg"
          style={{
            backgroundColor: 'rgba(168, 85, 247, 0.2)',
            border: '2px dashed #a855f7',
          }}
        >
          <div className="text-sm font-medium" style={{ color: '#a855f7' }}>
            Drop images here
          </div>
        </div>
      )}
      {/* Cell Header - minimal design */}
      <div
        className="flex items-center justify-between px-3 py-1 cell-ai-header"
      >
        <div className="flex items-center gap-2">
          {/* Running indicator */}
          {aiData.status === 'running' && (
            <div
              className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: '#a855f7', borderTopColor: 'transparent' }}
            />
          )}

          {/* Minimal cell type icon */}
          <span
            className="opacity-50 group-hover:opacity-80 transition-opacity"
            style={{ color: '#a855f7' }}
          >
            <Lightbulb className="w-3.5 h-3.5" />
          </span>

          {/* Status indicator - small text */}
          {aiData.status === 'completed' && (
            <span className="text-[10px]" style={{ color: 'var(--nb-accent-success)' }}>
              Done
            </span>
          )}
          {aiData.status === 'error' && (
            <span className="text-[10px]" style={{ color: 'var(--nb-accent-error)' }}>
              Error
            </span>
          )}

          {/* Cell ID - always visible but subtle */}
          <span
            className="text-[10px] font-mono opacity-40 hover:opacity-80 cursor-pointer transition-opacity"
            style={{ color: 'var(--nb-text-muted)' }}
            title="Click to copy cell ID"
            onClick={(e) => {
              e.stopPropagation()
              navigator.clipboard.writeText(cell.id)
            }}
          >
            [{index + 1}] {cell.id}
          </span>
        </div>

        {/* Cell actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => { e.stopPropagation(); onMoveUp() }}
            className="p-1 rounded hover:opacity-80"
            style={{ color: 'var(--nb-text-muted)' }}
            title="Move up"
          >
            <ChevronUp className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onMoveDown() }}
            className="p-1 rounded hover:opacity-80"
            style={{ color: 'var(--nb-text-muted)' }}
            title="Move down"
          >
            <ChevronDown className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleRun()
            }}
            disabled={aiData.status === 'running' || imagesLoading > 0 || (!localPrompt.trim() && images.length === 0)}
            className="p-1 rounded hover:opacity-80 disabled:opacity-30"
            style={{ color: 'var(--nb-accent-success)' }}
            title={imagesLoading > 0 ? 'Loading images...' : 'Run AI Cell (Shift+Enter)'}
          >
            {imagesLoading > 0 ? (
              <div
                className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'var(--nb-accent-success)', borderTopColor: 'transparent' }}
              />
            ) : (
              <Play className="w-4 h-4" fill="currentColor" />
            )}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="p-1 rounded hover:opacity-80"
            style={{ color: 'var(--nb-accent-error)' }}
            title="Delete cell"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Prompt Input */}
      <div className="px-3 py-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
            Ask AI:
          </span>
          {aiData.user_prompt && (
            <button
              onClick={(e) => { e.stopPropagation(); copyToClipboard(aiData.user_prompt, 'prompt') }}
              className="p-1 rounded hover:opacity-80 transition-colors"
              style={{ color: copiedPrompt ? 'var(--nb-accent-success)' : 'var(--nb-text-muted)' }}
              title="Copy prompt"
            >
              {copiedPrompt ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
        {isEditing || !aiData.user_prompt ? (
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={localPrompt}
              onChange={(e) => setLocalPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              onBlur={() => {
                if (localPrompt.trim() || images.length > 0) {
                  onUpdate({
                    ai_data: {
                      ...aiData,
                      user_prompt: localPrompt,
                      images: images.length > 0 ? images : undefined,
                    },
                  })
                }
              }}
              placeholder="Ask a question... (Shift+Enter to run, paste or drag images)"
              className="w-full bg-transparent text-sm resize-none outline-none min-h-[48px] p-2 rounded"
              style={{
                color: 'var(--nb-text-primary)',
                backgroundColor: 'rgba(168, 85, 247, 0.05)',
                border: isDragging ? '2px dashed #a855f7' : '1px solid rgba(168, 85, 247, 0.2)',
              }}
            />

            {/* Image previews - improved layout */}
            {(images.length > 0 || imagesLoading > 0) && (
              <div className="mt-2 p-2 rounded" style={{ backgroundColor: 'rgba(168, 85, 247, 0.05)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs flex items-center gap-2" style={{ color: 'var(--nb-text-muted)' }}>
                    {images.length} image{images.length !== 1 ? 's' : ''} attached
                    {imagesLoading > 0 && (
                      <span className="flex items-center gap-1 text-amber-400">
                        <div
                          className="w-3 h-3 border-2 border-t-transparent rounded-full animate-spin"
                          style={{ borderColor: '#fbbf24', borderTopColor: 'transparent' }}
                        />
                        Loading {imagesLoading}...
                      </span>
                    )}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setImages([])
                    }}
                    className="text-xs px-2 py-0.5 rounded hover:opacity-80"
                    style={{ color: 'var(--nb-accent-error)' }}
                    title="Remove all images"
                  >
                    Clear all
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {images.map((img, idx) => (
                    <div
                      key={idx}
                      className="relative group/img rounded-lg overflow-hidden shadow-sm cursor-pointer"
                      style={{ border: '1px solid rgba(168, 85, 247, 0.3)' }}
                      onClick={(e) => { e.stopPropagation(); setEnlargedImage(img) }}
                      title="Click to enlarge"
                    >
                      <img
                        src={`data:${img.mime_type};base64,${img.data}`}
                        alt={img.filename || 'Attached image'}
                        className="h-20 w-auto max-w-[120px] object-cover"
                      />
                      {/* Remove button - always visible */}
                      <button
                        onClick={(e) => { e.stopPropagation(); removeImage(idx) }}
                        className="absolute top-1 right-1 p-1 rounded-full transition-colors"
                        style={{
                          backgroundColor: 'rgba(0, 0, 0, 0.6)',
                          color: '#fff',
                        }}
                        title="Remove image"
                      >
                        <X className="w-3 h-3" />
                      </button>
                      {/* Filename label */}
                      <div
                        className="absolute bottom-0 left-0 right-0 text-[10px] px-1.5 py-0.5 truncate"
                        style={{ backgroundColor: 'rgba(0,0,0,0.7)', color: '#fff' }}
                        title={img.filename}
                      >
                        {img.filename}
                      </div>
                      {/* Image number badge */}
                      <div
                        className="absolute top-1 left-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                        style={{ backgroundColor: '#a855f7', color: '#fff' }}
                      >
                        {idx + 1}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>
            <div
              className="text-sm cursor-pointer p-2 rounded hover:opacity-80"
              style={{
                color: 'var(--nb-text-primary)',
                backgroundColor: 'rgba(168, 85, 247, 0.05)',
                border: '1px solid rgba(168, 85, 247, 0.2)',
              }}
              onClick={(e) => {
                e.stopPropagation()
                setIsEditing(true)
              }}
            >
              {aiData.user_prompt}
            </div>
            {/* Show attached images in view mode */}
            {aiData.images && aiData.images.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {aiData.images.map((img, idx) => (
                  <div
                    key={idx}
                    className="relative rounded-lg overflow-hidden shadow-sm cursor-pointer"
                    style={{ border: '1px solid rgba(168, 85, 247, 0.3)' }}
                    onClick={(e) => { e.stopPropagation(); setEnlargedImage(img) }}
                    title="Click to enlarge"
                  >
                    <img
                      src={`data:${img.mime_type};base64,${img.data}`}
                      alt={img.filename || 'Attached image'}
                      className="h-16 w-auto max-w-[100px] object-cover"
                    />
                    <div
                      className="absolute top-1 left-1 text-[9px] px-1 py-0.5 rounded-full font-medium"
                      style={{ backgroundColor: '#a855f7', color: '#fff' }}
                    >
                      {idx + 1}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Response Area - transparent with left border */}
      {(aiData.llm_response || aiData.status === 'running' || aiData.error) && (
        <div
          className="px-3 py-2 ml-3"
          style={{
            borderLeft: '2px solid rgba(168, 85, 247, 0.3)',
            backgroundColor: 'transparent',
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
              AI Response:
            </span>
            {aiData.llm_response && (
              <button
                onClick={(e) => { e.stopPropagation(); copyToClipboard(aiData.llm_response, 'response') }}
                className="p-1 rounded hover:opacity-80 transition-colors"
                style={{ color: copiedResponse ? 'var(--nb-accent-success)' : 'var(--nb-text-muted)' }}
                title="Copy response"
              >
                {copiedResponse ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {aiData.status === 'running' && (
            <div className="space-y-3">
              {/* Status header with cancel button */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--nb-text-muted)' }}>
                  <div
                    className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                    style={{ borderColor: '#a855f7', borderTopColor: 'transparent' }}
                  />
                  {aiData.streamState?.thinkingMessage || 'Thinking...'}
                </div>
                {onCancelAICell && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleCancel() }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded hover:opacity-80 transition-opacity font-medium"
                    style={{
                      backgroundColor: 'rgba(239, 68, 68, 0.2)',
                      color: 'var(--nb-accent-error)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                    }}
                    title="Cancel AI Cell execution"
                  >
                    <X className="w-3.5 h-3.5" />
                    Cancel
                  </button>
                )}
              </div>

              {/* LLM Thinking/Reasoning display - collapsible with live updates */}
              {aiData.streamState?.thinkingSteps && aiData.streamState.thinkingSteps.length > 0 && (
                <details open className="text-xs">
                  <summary
                    className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded-md transition-colors"
                    style={{
                      backgroundColor: 'rgba(147, 51, 234, 0.1)',
                      border: '1px solid rgba(147, 51, 234, 0.3)',
                    }}
                  >
                    <span className="w-5 h-5 rounded flex items-center justify-center" style={{ backgroundColor: 'rgba(147, 51, 234, 0.2)', color: '#9333ea' }}>💭</span>
                    <span style={{ color: '#9333ea' }} className="font-medium">Thinking...</span>
                    {/* Iteration badges */}
                    <span className="flex items-center gap-1 ml-1">
                      {[...new Set(aiData.streamState.thinkingSteps.map(s => s.iteration))].sort((a, b) => a - b).map(iter => (
                        <span
                          key={iter}
                          className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold"
                          style={{ backgroundColor: '#9333ea', color: '#fff' }}
                        >
                          {iter}
                        </span>
                      ))}
                    </span>
                    <span style={{ color: 'var(--nb-text-muted)' }} className="ml-1">
                      ({Math.round(aiData.streamState.thinkingSteps.reduce((sum, s) => sum + s.content.length, 0) / 1000)}k chars)
                    </span>
                    {/* Live indicator */}
                    <span className="ml-auto flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                      <span style={{ color: 'var(--nb-accent-success)' }}>Live</span>
                    </span>
                  </summary>
                  <div className="mt-2 space-y-2 ml-2 pl-3" style={{ borderLeft: '2px solid rgba(147, 51, 234, 0.3)' }}>
                    {[...new Set(aiData.streamState.thinkingSteps.map(s => s.iteration))].sort((a, b) => a - b).map(iteration => {
                      const iterSteps = aiData.streamState!.thinkingSteps.filter(s => s.iteration === iteration)
                      const combinedContent = iterSteps.map(s => s.content).join('\n\n')
                      return (
                        <div key={iteration}>
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold" style={{ backgroundColor: '#9333ea', color: '#fff' }}>
                              {iteration}
                            </span>
                            <span className="font-medium" style={{ color: '#9333ea' }}>Iteration {iteration}</span>
                            <span style={{ color: 'var(--nb-text-muted)' }}>({Math.round(combinedContent.length / 1000)}k chars)</span>
                          </div>
                          <div
                            className="text-[11px] rounded-md p-2 whitespace-pre-wrap break-words overflow-hidden font-mono max-h-[200px] overflow-y-auto"
                            style={{ backgroundColor: 'rgba(147, 51, 234, 0.05)', color: 'var(--nb-text-secondary)', border: '1px solid rgba(147, 51, 234, 0.2)' }}
                          >
                            {combinedContent.slice(0, 3000)}
                            {combinedContent.length > 3000 && '\n\n... (truncated)'}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </details>
              )}

              {/* Current tool call indicator */}
              {aiData.streamState?.currentToolCall && (
                <div
                  className="flex items-center gap-2 px-3 py-2 rounded-md text-xs animate-pulse"
                  style={{ backgroundColor: 'rgba(168, 85, 247, 0.1)', border: '1px solid rgba(168, 85, 247, 0.3)' }}
                >
                  <span className="w-5 h-5 rounded flex items-center justify-center" style={{ backgroundColor: 'rgba(168, 85, 247, 0.2)', color: '#a855f7' }}>⚡</span>
                  <span style={{ color: '#a855f7' }} className="font-medium">{aiData.streamState.currentToolCall.name}</span>
                  <span style={{ color: 'var(--nb-text-muted)' }} className="truncate max-w-[300px]">
                    {JSON.stringify(aiData.streamState.currentToolCall.args).slice(0, 100)}
                    {JSON.stringify(aiData.streamState.currentToolCall.args).length > 100 && '...'}
                  </span>
                </div>
              )}

              {/* Streaming steps (live updates) */}
              {aiData.streamState?.streamingSteps && aiData.streamState.streamingSteps.length > 0 && (
                <div className="space-y-1.5 ml-2 pl-3" style={{ borderLeft: '2px solid var(--nb-border-default)' }}>
                  {aiData.streamState.streamingSteps.map((step, idx) => (
                    <div key={idx} className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
                      <span className="flex items-center gap-1.5" style={{ color: 'var(--nb-text-secondary)' }}>
                        {step.type === 'tool_call' && (
                          <span className="w-4 h-4 rounded flex items-center justify-center text-[9px]" style={{ backgroundColor: 'rgba(168, 85, 247, 0.2)', color: '#a855f7' }}>⚡</span>
                        )}
                        {step.type === 'tool_result' && (
                          <span className="w-4 h-4 rounded flex items-center justify-center text-[9px]" style={{ backgroundColor: 'rgba(166, 227, 161, 0.2)', color: 'var(--nb-accent-success)' }}>✓</span>
                        )}
                        <span className="font-medium">{step.name}</span>
                      </span>
                      <pre className="mt-0.5 text-[10px] rounded p-1.5 whitespace-pre-wrap break-words overflow-hidden font-mono" style={{ backgroundColor: 'var(--nb-bg-ai-cell)', color: 'var(--nb-text-secondary)' }}>
                        {step.content.slice(0, 200)}
                        {step.content.length > 200 && '...'}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {aiData.error && (
            <div
              className="rounded-lg overflow-hidden"
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
              }}
            >
              {/* Error header */}
              <div
                className="flex items-center justify-between px-3 py-2"
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  borderBottom: '1px solid rgba(239, 68, 68, 0.2)',
                }}
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" style={{ color: 'var(--nb-accent-error)' }} />
                  <span className="text-sm font-medium" style={{ color: 'var(--nb-accent-error)' }}>
                    Error
                  </span>
                </div>
                {/* Retry button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleRun()
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md transition-all hover:opacity-80"
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    color: 'var(--nb-accent-error)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                  }}
                  title="Retry this request"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Retry
                </button>
              </div>
              {/* Error message */}
              <div className="px-3 py-2">
                <p className="text-sm" style={{ color: 'var(--nb-text-secondary)' }}>
                  {aiData.error}
                </p>
              </div>
            </div>
          )}

          {/* Completed state: Thinking → Tools → Response (chronological order) */}
          {/* Thinking steps (persisted from ipynb) - collapsed by default */}
          {aiData.status !== 'running' && aiData.thinking && aiData.thinking.length > 0 && renderThinking(aiData.thinking)}

          {/* Tool call steps - collapsed by default */}
          {aiData.status !== 'running' && aiData.steps && aiData.steps.length > 0 && renderSteps(aiData.steps)}

          {/* Final response (main content) */}
          {aiData.llm_response && renderResponse()}
        </div>
      )}

      {/* Image Enlarge Modal */}
      {enlargedImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setEnlargedImage(null)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh]">
            {/* Close button */}
            <button
              onClick={() => setEnlargedImage(null)}
              className="absolute -top-10 right-0 p-2 rounded-full hover:bg-white/10 transition-colors"
              style={{ color: '#fff' }}
              title="Close (Esc)"
            >
              <X className="w-6 h-6" />
            </button>
            {/* Enlarged image */}
            <img
              src={`data:${enlargedImage.mime_type};base64,${enlargedImage.data}`}
              alt={enlargedImage.filename || 'Enlarged image'}
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
            {/* Filename */}
            {enlargedImage.filename && (
              <div className="absolute -bottom-8 left-0 right-0 text-center text-sm text-white/70">
                {enlargedImage.filename}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
