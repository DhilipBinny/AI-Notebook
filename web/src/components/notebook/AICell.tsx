'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Cell as CellType, AICellData } from '@/types'

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
  onRunAICell: (cellId: string, prompt: string) => Promise<void>
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

  const aiData = cell.ai_data || {
    user_prompt: '',
    llm_response: '',
    status: 'idle' as const,
  }

  // Update local prompt when cell changes
  useEffect(() => {
    setLocalPrompt(cell.ai_data?.user_prompt || '')
  }, [cell.ai_data?.user_prompt])

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

  // Handle run
  const handleRun = async () => {
    if (!localPrompt.trim()) return

    // Update cell with prompt and running status
    onUpdate({
      ai_data: {
        ...aiData,
        user_prompt: localPrompt,
        status: 'running',
      },
    })

    setIsEditing(false)
    await onRunAICell(cell.id, localPrompt)
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
      className="group rounded-lg transition-all overflow-hidden cell-wrapper cell-ai"
      onClick={onSelect}
      style={{
        backgroundColor: 'var(--nb-bg-ai-cell, #2a1f4e)',
        borderColor: 'var(--nb-border-default)',
        ...getSelectionStyle(),
      }}
    >
      {/* Cell Header */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{
          borderBottom: '1px solid var(--nb-border-default)',
          backgroundColor: 'rgba(168, 85, 247, 0.1)',
        }}
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
        <div className="text-xs mb-1" style={{ color: 'var(--nb-text-muted)' }}>
          Ask AI:
        </div>
        {isEditing || !aiData.user_prompt ? (
          <textarea
            ref={textareaRef}
            value={localPrompt}
            onChange={(e) => setLocalPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => {
              if (localPrompt.trim()) {
                onUpdate({
                  ai_data: {
                    ...aiData,
                    user_prompt: localPrompt,
                  },
                })
              }
            }}
            placeholder="Ask a question about your notebook... (Shift+Enter to run)"
            className="w-full bg-transparent text-sm resize-none outline-none min-h-[48px] p-2 rounded"
            style={{
              color: 'var(--nb-text-primary)',
              backgroundColor: 'rgba(168, 85, 247, 0.05)',
              border: '1px solid rgba(168, 85, 247, 0.2)',
            }}
          />
        ) : (
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
          <div className="text-xs mb-2" style={{ color: 'var(--nb-text-muted)' }}>
            AI Response:
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
    </div>
  )
}
