'use client'

import { useState, useRef, useEffect, useCallback } from 'react'

// Copy icon component for reuse
function CopyIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}

// Check icon for copy feedback
function CheckIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Cell as CellType, AICellData, ImageInput } from '@/types'

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
  onInsertCodeCells,
  onScrollToCell,
}: AICellProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const responseRef = useRef<HTMLDivElement>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [localPrompt, setLocalPrompt] = useState(cell.ai_data?.user_prompt || '')
  const [images, setImages] = useState<ImageInput[]>(cell.ai_data?.images || [])

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
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      // Extract base64 data (remove "data:image/png;base64," prefix)
      const base64 = dataUrl.split(',')[1]
      const mimeType = dataUrl.split(';')[0].split(':')[1]

      const filename = file.name || `image-${Date.now()}.${mimeType.split('/')[1]}`

      const newImage: ImageInput = {
        data: base64,
        mime_type: mimeType,
        filename: filename
      }

      setImages(prev => [...prev, newImage])
      // Note: No placeholder text added - image preview thumbnails show what's attached
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
    if (!localPrompt.trim() && images.length === 0) return

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
      return `<button class="cell-reference" data-cell-id="${cellId}" style="color: #a855f7; text-decoration: underline; cursor: pointer; background: none; border: none; font: inherit; padding: 0;">${match}</button>`
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
          className="prose prose-sm max-w-none prose-invert"
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
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
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

  return (
    <div
      id={`cell-${cell.id}`}
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
      {/* Cell Header */}
      <div
        className="flex items-center justify-between px-3 py-2 cell-ai-header"
      >
        <div className="flex items-center gap-3">
          {/* Running indicator */}
          {aiData.status === 'running' && (
            <div
              className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: '#a855f7', borderTopColor: 'transparent' }}
            />
          )}

          {/* Cell type badge */}
          <span
            className="text-xs px-2 py-0.5 rounded flex items-center gap-1.5 font-medium"
            style={{
              backgroundColor: '#a855f7',
              color: '#ffffff',
            }}
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            AI
          </span>

          {/* Status indicator */}
          {aiData.status === 'completed' && (
            <span className="text-xs" style={{ color: 'var(--nb-accent-success)' }}>
              Completed
            </span>
          )}
          {aiData.status === 'error' && (
            <span className="text-xs" style={{ color: 'var(--nb-accent-error)' }}>
              Error
            </span>
          )}

          {/* Cell ID */}
          <span
            className="text-[10px] font-mono opacity-50 hover:opacity-100 cursor-pointer transition-opacity"
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
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onMoveDown() }}
            className="p-1 rounded hover:opacity-80"
            style={{ color: 'var(--nb-text-muted)' }}
            title="Move down"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleRun()
            }}
            disabled={aiData.status === 'running' || !localPrompt.trim()}
            className="p-1 rounded hover:opacity-80 disabled:opacity-30"
            style={{ color: 'var(--nb-accent-success)' }}
            title="Run AI Cell (Shift+Enter)"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete() }}
            className="p-1 rounded hover:opacity-80"
            style={{ color: 'var(--nb-accent-error)' }}
            title="Delete cell"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
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
              {copiedPrompt ? <CheckIcon className="w-3.5 h-3.5" /> : <CopyIcon className="w-3.5 h-3.5" />}
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
            {images.length > 0 && (
              <div className="mt-2 p-2 rounded" style={{ backgroundColor: 'rgba(168, 85, 247, 0.05)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
                    {images.length} image{images.length > 1 ? 's' : ''} attached
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
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
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

      {/* Response Area */}
      {(aiData.llm_response || aiData.status === 'running' || aiData.error) && (
        <div
          className="px-3 py-2"
          style={{
            borderTop: '1px solid var(--nb-border-default)',
            backgroundColor: 'var(--nb-bg-output)',
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
                {copiedResponse ? <CheckIcon className="w-3.5 h-3.5" /> : <CopyIcon className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {aiData.status === 'running' && (
            <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--nb-text-muted)' }}>
              <div
                className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: '#a855f7', borderTopColor: 'transparent' }}
              />
              Thinking...
            </div>
          )}

          {aiData.error && (
            <div className="text-sm" style={{ color: 'var(--nb-accent-error)' }}>
              Error: {aiData.error}
            </div>
          )}

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
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
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
