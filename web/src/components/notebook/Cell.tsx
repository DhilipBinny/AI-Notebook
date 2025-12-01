'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Cell as CellType, CellOutput } from '@/types'

// Configure marked
marked.setOptions({
  gfm: true,
  breaks: true,
})

interface CellProps {
  cell: CellType
  index: number
  isSelected: boolean
  isRunning: boolean
  onSelect: () => void
  onRun: () => void
  onStop: () => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onUpdate: (updates: Partial<CellType>) => void
  onToggleContext: () => void
  isInContext: boolean
}

export default function Cell({
  cell,
  index,
  isSelected,
  isRunning,
  onSelect,
  onRun,
  onStop,
  onDelete,
  onMoveUp,
  onMoveDown,
  onUpdate,
  onToggleContext,
  isInContext,
}: CellProps) {
  // For markdown cells with content, default to rendered view (not editing)
  // For code cells, always show editor
  const [isEditing, setIsEditing] = useState(cell.type === 'code' || !cell.source.trim())
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Track the previous source to detect external changes (e.g., from LLM)
  const prevSourceRef = useRef(cell.source)
  const isUserEditingRef = useRef(false)

  // Only exit editing mode for markdown when content changes externally (not from user typing)
  useEffect(() => {
    // If the source changed and user is not actively editing, it's an external update
    if (cell.type === 'markdown' && cell.source !== prevSourceRef.current && !isUserEditingRef.current) {
      if (cell.source.trim()) {
        setIsEditing(false)
      }
    }
    prevSourceRef.current = cell.source
  }, [cell.source, cell.type])

  // Render markdown with sanitization
  const renderedMarkdown = useMemo(() => {
    if (cell.type !== 'markdown' || !cell.source.trim()) return ''
    try {
      const html = marked.parse(cell.source) as string
      return DOMPurify.sanitize(html)
    } catch {
      return cell.source
    }
  }, [cell.type, cell.source])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.max(100, textareaRef.current.scrollHeight) + 'px'
    }
  }, [cell.source])

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (isEditing && textareaRef.current && isSelected) {
      textareaRef.current.focus()
    }
  }, [isEditing, isSelected])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault()
      if (cell.type === 'code') {
        onRun()
      } else {
        // For markdown, exit edit mode on Shift+Enter
        setIsEditing(false)
      }
    }
    if (e.key === 'Escape' && cell.type === 'markdown') {
      setIsEditing(false)
    }
    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault()
      const textarea = textareaRef.current
      if (textarea) {
        const start = textarea.selectionStart
        const end = textarea.selectionEnd
        const value = textarea.value
        const newValue = value.substring(0, start) + '    ' + value.substring(end)
        onUpdate({ source: newValue })
        // Set cursor position after React re-renders
        setTimeout(() => {
          textarea.selectionStart = textarea.selectionEnd = start + 4
        }, 0)
      }
    }
  }, [onRun, onUpdate, cell.type])

  const renderOutput = (output: CellOutput, idx: number) => {
    switch (output.output_type) {
      case 'stream':
        const text = Array.isArray(output.text) ? output.text.join('') : output.text || ''
        return (
          <pre
            key={idx}
            className="text-sm whitespace-pre-wrap font-mono"
            style={{ color: 'var(--nb-text-output, var(--nb-text-primary))' }}
          >
            {text}
          </pre>
        )
      case 'execute_result':
      case 'display_data':
        if (output.data) {
          if (output.data['text/html']) {
            return (
              <div
                key={idx}
                className="text-sm output-html"
                style={{ color: 'var(--nb-text-output, var(--nb-text-primary))' }}
                dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(output.data['text/html'] as string) }}
              />
            )
          }
          if (output.data['image/png']) {
            return (
              <img
                key={idx}
                src={`data:image/png;base64,${output.data['image/png']}`}
                alt="Output"
                className="max-w-full"
              />
            )
          }
          if (output.data['image/jpeg']) {
            return (
              <img
                key={idx}
                src={`data:image/jpeg;base64,${output.data['image/jpeg']}`}
                alt="Output"
                className="max-w-full"
              />
            )
          }
          if (output.data['text/plain']) {
            const plainText = Array.isArray(output.data['text/plain'])
              ? output.data['text/plain'].join('')
              : output.data['text/plain']
            return (
              <pre
                key={idx}
                className="text-sm whitespace-pre-wrap font-mono"
                style={{ color: 'var(--nb-text-output, var(--nb-text-primary))' }}
              >
                {plainText as string}
              </pre>
            )
          }
        }
        return null
      case 'error':
        return (
          <div key={idx} className="text-sm font-mono" style={{ color: 'var(--nb-accent-error)' }}>
            <div className="font-bold">{output.ename}: {output.evalue}</div>
            {output.traceback && (
              <pre className="whitespace-pre-wrap text-xs mt-1 opacity-80">
                {output.traceback.join('\n').replace(/\x1b\[[0-9;]*m/g, '')}
              </pre>
            )}
          </div>
        )
      default:
        return null
    }
  }

  // Cell type-specific classes
  const cellTypeClass = cell.type === 'code' ? 'cell-code' : 'cell-markdown'

  return (
    <div
      className={`group rounded-lg transition-all overflow-hidden ${cellTypeClass} ${
        isSelected
          ? 'ring-2 ring-[var(--nb-border-selected)]'
          : 'hover:ring-1 hover:ring-[var(--nb-border-default)]'
      }`}
      onClick={onSelect}
      style={{
        backgroundColor: cell.type === 'code'
          ? 'var(--nb-bg-code-cell)'
          : 'var(--nb-bg-markdown-cell)',
        borderColor: 'var(--nb-border-default)',
      }}
    >
      {/* Cell content wrapper - left border for context highlight (excludes output) */}
      <div
        style={{
          borderLeft: isInContext ? '4px solid var(--nb-accent-success)' : 'none',
          paddingLeft: isInContext ? '0' : '4px',  // Maintain consistent spacing
        }}
      >
        {/* Cell Header */}
        <div
          className="flex items-center justify-between px-3 py-2"
          style={{
            borderBottom: '1px solid var(--nb-border-default)',
            backgroundColor: cell.type === 'code'
              ? 'var(--nb-bg-code-cell)'
              : 'var(--nb-bg-markdown-cell)',
          }}
        >
        <div className="flex items-center gap-3">
          {/* Context checkbox */}
          <input
            type="checkbox"
            checked={isInContext}
            onChange={onToggleContext}
            className="w-4 h-4 rounded"
            style={{
              accentColor: 'var(--nb-accent-success)',
            }}
            title="Include in AI context"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Running indicator */}
          {isRunning && (
            <div
              className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: 'var(--nb-accent-code)', borderTopColor: 'transparent' }}
            />
          )}

          {/* Cell type badge with icon */}
          <span
            className="text-xs px-2 py-0.5 rounded flex items-center gap-1.5 font-medium"
            style={{
              backgroundColor: cell.type === 'code'
                ? 'var(--nb-accent-code)'
                : 'var(--nb-accent-markdown)',
              color: cell.type === 'code' ? '#11111b' : '#11111b',
              opacity: 0.9,
            }}
          >
            {cell.type === 'code' ? (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                Code
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Markdown
              </>
            )}
          </span>

          {/* Execution count */}
          {cell.type === 'code' && (
            <span className="execution-count">
              {cell.execution_count ? `In [${cell.execution_count}]:` : 'In [ ]:'}
            </span>
          )}

          {/* Cell ID - shown on hover or always visible as muted text */}
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
          {cell.type === 'code' && (
            isRunning ? (
              <button
                onClick={(e) => { e.stopPropagation(); onStop() }}
                className="p-1 rounded hover:opacity-80"
                style={{ color: 'var(--nb-accent-error)' }}
                title="Stop execution"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" />
                </svg>
              </button>
            ) : (
              <button
                onClick={(e) => { e.stopPropagation(); onRun() }}
                className="p-1 rounded hover:opacity-80"
                style={{ color: 'var(--nb-accent-success)' }}
                title="Run cell (Shift+Enter)"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </button>
            )
          )}
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

      {/* Cell Input */}
      <div className="p-3" style={{ color: 'var(--nb-text-primary)' }}>
        {cell.type === 'markdown' && !isEditing && cell.source.trim() ? (
          <div
            className="prose prose-sm max-w-none cursor-text"
            onClick={() => {
              isUserEditingRef.current = true
              setIsEditing(true)
            }}
            dangerouslySetInnerHTML={{ __html: renderedMarkdown }}
          />
        ) : (
          <textarea
            ref={textareaRef}
            value={cell.source}
            onChange={(e) => {
              isUserEditingRef.current = true
              onUpdate({ source: e.target.value })
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              isUserEditingRef.current = true
            }}
            onBlur={() => {
              isUserEditingRef.current = false
              // Don't auto-render on blur - only render on Shift+Enter
            }}
            placeholder={cell.type === 'code' ? 'Enter Python code...' : 'Enter markdown... (Shift+Enter to preview)'}
            className="w-full bg-transparent font-mono text-sm resize-none outline-none"
            style={{
              minHeight: '100px',
              color: 'var(--nb-text-primary)',
            }}
          />
        )}
      </div>
      </div>
      {/* End of cell content wrapper - output below is NOT highlighted */}

      {/* Cell Output */}
      {cell.type === 'code' && cell.outputs && cell.outputs.length > 0 && (
        <div
          className="cell-output p-3 space-y-2"
          style={{
            borderTop: '1px solid var(--nb-border-default)',
            backgroundColor: 'var(--nb-bg-output)',
          }}
        >
          {cell.outputs.map((output, idx) => renderOutput(output, idx))}
        </div>
      )}
    </div>
  )
}
