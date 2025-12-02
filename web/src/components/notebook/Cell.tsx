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

/**
 * Process terminal output text:
 * 1. Strip ANSI escape codes (colors, cursor control, etc.)
 * 2. Handle carriage returns for progress bars using terminal-style line buffer
 */
function processTerminalOutput(text: string): string {
  // Strip ANSI escape sequences:
  // - \x1b[ or \033[ followed by parameters and a command letter
  // - Includes color codes, cursor movement, clear screen, etc.
  let processed = text
    .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')  // Standard ANSI sequences like \x1b[32m
    .replace(/\x1b\][^\x07]*\x07/g, '')      // OSC sequences (operating system commands)
    .replace(/\x1b\[\?[0-9;]*[a-zA-Z]/g, '') // Private mode sequences like \x1b[?25h (show cursor)
    .replace(/\x1b[=>]/g, '')                // Simple escape sequences

  // Terminal-style line buffer processing for \r (carriage return)
  // This emulates how a terminal handles \r - it moves cursor to start of line
  // and subsequent characters overwrite the existing content
  const lines: string[] = []
  let currentLine = ''

  for (let i = 0; i < processed.length; i++) {
    const char = processed[i]

    if (char === '\n') {
      // Newline: push current line and start fresh
      lines.push(currentLine)
      currentLine = ''
    } else if (char === '\r') {
      // Carriage return: reset to beginning of current line
      // Don't push the line yet - next chars will overwrite
      // But if \r is followed by \n, treat as newline
      if (processed[i + 1] === '\n') {
        lines.push(currentLine)
        currentLine = ''
        i++ // Skip the \n
      } else {
        // Just \r - reset line buffer (overwrite mode)
        currentLine = ''
      }
    } else {
      currentLine += char
    }
  }

  // Don't forget the last line if it doesn't end with \n
  if (currentLine) {
    lines.push(currentLine)
  }

  // Remove consecutive duplicate lines (common in progress bar updates)
  const deduped: string[] = []
  for (const line of lines) {
    if (deduped.length === 0 || line !== deduped[deduped.length - 1]) {
      deduped.push(line)
    }
  }

  // Remove empty lines at the end (cleanup)
  while (deduped.length > 0 && deduped[deduped.length - 1].trim() === '') {
    deduped.pop()
  }

  return deduped.join('\n')
}

// Maximum height for output area (in pixels)
const MAX_OUTPUT_HEIGHT = 300

/**
 * OutputArea component with max height, auto-scroll, and expand/collapse
 */
function OutputArea({
  outputs,
  renderOutput
}: {
  outputs: CellOutput[]
  renderOutput: (output: CellOutput, idx: number) => React.ReactNode
}) {
  const outputRef = useRef<HTMLDivElement>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [needsExpand, setNeedsExpand] = useState(false)

  // Check if content exceeds max height and auto-scroll to bottom
  useEffect(() => {
    if (outputRef.current) {
      const shouldShowExpand = outputRef.current.scrollHeight > MAX_OUTPUT_HEIGHT
      setNeedsExpand(shouldShowExpand)

      // Auto-scroll to bottom when new output arrives
      if (!isExpanded) {
        outputRef.current.scrollTop = outputRef.current.scrollHeight
      }
    }
  }, [outputs, isExpanded])

  return (
    <div
      style={{
        borderTop: '1px solid var(--nb-border-default)',
        backgroundColor: 'var(--nb-bg-output)',
      }}
    >
      <div
        ref={outputRef}
        className="cell-output p-3 space-y-2 overflow-auto"
        style={{
          maxHeight: isExpanded ? 'none' : `${MAX_OUTPUT_HEIGHT}px`,
        }}
      >
        {outputs.map((output, idx) => renderOutput(output, idx))}
      </div>

      {/* Expand/Collapse button */}
      {needsExpand && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            setIsExpanded(!isExpanded)
          }}
          className="w-full py-1 text-xs flex items-center justify-center gap-1 hover:opacity-80 transition-opacity"
          style={{
            color: 'var(--nb-text-muted)',
            borderTop: '1px solid var(--nb-border-default)',
            backgroundColor: 'var(--nb-bg-secondary)',
          }}
        >
          {isExpanded ? (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
              Collapse output
            </>
          ) : (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              Expand output
            </>
          )}
        </button>
      )}
    </div>
  )
}

interface CellProps {
  cell: CellType
  index: number
  isSelected: boolean
  isRunning: boolean
  isEditMode: boolean  // true when this cell is being edited
  onSelect: () => void
  onRun: () => void
  onRunAndAdvance: () => void  // Runs cell and moves to next
  onStop: () => void
  onDelete: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  onUpdate: (updates: Partial<CellType>) => void
  onToggleContext: () => void
  isInContext: boolean
  onEnterEditMode: () => void
  onExitEditMode: (renderMarkdown?: boolean) => void  // Optional: render markdown on exit
}

export default function Cell({
  cell,
  index,
  isSelected,
  isRunning,
  isEditMode,
  onSelect,
  onRun,
  onRunAndAdvance,
  onStop,
  onDelete,
  onMoveUp,
  onMoveDown,
  onUpdate,
  onToggleContext,
  isInContext,
  onEnterEditMode,
  onExitEditMode,
}: CellProps) {
  // For markdown cells: show rendered view when not in edit mode and has content
  // isEditMode from parent is the source of truth
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevSourceRef = useRef(cell.source)

  // For markdown cells, determine if we should show rendered view
  // Show textarea if: in edit mode, OR no content yet, OR is code/raw cell
  const showTextarea = cell.type !== 'markdown' || isEditMode || !cell.source.trim()

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

  // Auto-resize textarea to fit content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px'
    }
  }, [cell.source])

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (isEditMode && textareaRef.current && isSelected) {
      textareaRef.current.focus()
    }
  }, [isEditMode, isSelected])

  // Handle external source changes (e.g., from LLM) - just track for reference
  useEffect(() => {
    prevSourceRef.current = cell.source
  }, [cell.source])

  // Handle keyboard shortcuts inside cell textarea
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const textarea = textareaRef.current

    // Shift+Enter - run cell and move to next (exit edit mode)
    if (e.key === 'Enter' && e.shiftKey) {
      e.preventDefault()
      console.log('[Cell] Shift+Enter pressed, cell type:', cell.type, 'cell id:', cell.id)
      if (cell.type === 'code') {
        // For code cells: onRunAndAdvance handles run + move to next
        console.log('[Cell] Calling onRunAndAdvance for code cell')
        onRunAndAdvance()
        onExitEditMode(false)  // Just exit edit mode, don't move again
      } else {
        // For markdown/raw cells: just exit edit mode and move to next
        console.log('[Cell] Calling onExitEditMode(true) for markdown cell')
        onExitEditMode(true)  // Exit and move to next cell
      }
      return
    }

    // Only handle Tab, Shift+Tab, and Ctrl+/ for code cells
    if (cell.type === 'code' && textarea) {
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const value = textarea.value

      // Get line information
      const getLineInfo = () => {
        const beforeStart = value.substring(0, start)
        const lineStartIndex = beforeStart.lastIndexOf('\n') + 1
        const afterEnd = value.substring(end)
        const lineEndIndex = end + (afterEnd.indexOf('\n') === -1 ? afterEnd.length : afterEnd.indexOf('\n'))
        return { lineStartIndex, lineEndIndex }
      }

      // Get all lines in selection
      const getSelectedLines = () => {
        const beforeStart = value.substring(0, start)
        const firstLineStart = beforeStart.lastIndexOf('\n') + 1
        const afterEnd = value.substring(end)
        const lastLineEnd = end + (afterEnd.indexOf('\n') === -1 ? afterEnd.length : afterEnd.indexOf('\n'))
        const selectedText = value.substring(firstLineStart, lastLineEnd)
        return {
          firstLineStart,
          lastLineEnd,
          lines: selectedText.split('\n'),
        }
      }

      // Tab - Indent right (4 spaces)
      if (e.key === 'Tab' && !e.shiftKey) {
        e.preventDefault()

        if (start === end) {
          // No selection - just insert 4 spaces at cursor
          const newValue = value.substring(0, start) + '    ' + value.substring(end)
          onUpdate({ source: newValue })
          setTimeout(() => {
            textarea.selectionStart = textarea.selectionEnd = start + 4
          }, 0)
        } else {
          // Multi-line selection - indent all selected lines
          const { firstLineStart, lastLineEnd, lines } = getSelectedLines()
          const indentedLines = lines.map(line => '    ' + line)
          const newValue = value.substring(0, firstLineStart) + indentedLines.join('\n') + value.substring(lastLineEnd)
          onUpdate({ source: newValue })
          setTimeout(() => {
            textarea.selectionStart = start + 4
            textarea.selectionEnd = end + (lines.length * 4)
          }, 0)
        }
        return
      }

      // Shift+Tab - Indent left (remove up to 4 spaces)
      if (e.key === 'Tab' && e.shiftKey) {
        e.preventDefault()

        const { firstLineStart, lastLineEnd, lines } = getSelectedLines()
        let totalRemoved = 0
        let firstLineRemoved = 0

        const outdentedLines = lines.map((line, idx) => {
          // Remove up to 4 leading spaces
          const match = line.match(/^( {1,4})/)
          if (match) {
            const removed = match[1].length
            totalRemoved += removed
            if (idx === 0) firstLineRemoved = removed
            return line.substring(removed)
          }
          return line
        })

        const newValue = value.substring(0, firstLineStart) + outdentedLines.join('\n') + value.substring(lastLineEnd)
        onUpdate({ source: newValue })
        setTimeout(() => {
          textarea.selectionStart = Math.max(firstLineStart, start - firstLineRemoved)
          textarea.selectionEnd = Math.max(textarea.selectionStart, end - totalRemoved)
        }, 0)
        return
      }

      // Ctrl+/ or Cmd+/ - Toggle comment
      // Use e.code for more reliable key detection across keyboard layouts
      if ((e.key === '/' || e.code === 'Slash') && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        e.stopPropagation()

        const { firstLineStart, lastLineEnd, lines } = getSelectedLines()

        // Check if all non-empty lines are commented
        const nonEmptyLines = lines.filter(line => line.trim().length > 0)
        const allCommented = nonEmptyLines.length > 0 && nonEmptyLines.every(line => line.trimStart().startsWith('#'))

        let newLines: string[]
        let deltaPerLine: number

        if (allCommented) {
          // Uncomment - remove '# ' or '#' from start of each line
          deltaPerLine = 0
          newLines = lines.map(line => {
            if (line.trimStart().startsWith('# ')) {
              const idx = line.indexOf('# ')
              return line.substring(0, idx) + line.substring(idx + 2)
            } else if (line.trimStart().startsWith('#')) {
              const idx = line.indexOf('#')
              return line.substring(0, idx) + line.substring(idx + 1)
            }
            return line
          })
        } else {
          // Comment - add '# ' at the start of each line (preserving indentation)
          deltaPerLine = 2
          newLines = lines.map(line => {
            if (line.trim().length === 0) return line // Keep empty lines empty
            const match = line.match(/^(\s*)/)
            const indent = match ? match[1] : ''
            return indent + '# ' + line.substring(indent.length)
          })
        }

        const newValue = value.substring(0, firstLineStart) + newLines.join('\n') + value.substring(lastLineEnd)
        onUpdate({ source: newValue })

        // Adjust selection
        setTimeout(() => {
          if (allCommented) {
            // Calculate removed characters
            const firstLineChange = lines[0].trimStart().startsWith('# ') ? 2 : (lines[0].trimStart().startsWith('#') ? 1 : 0)
            textarea.selectionStart = Math.max(firstLineStart, start - firstLineChange)
            textarea.selectionEnd = end - (nonEmptyLines.length * 2) // Approximate
          } else {
            textarea.selectionStart = start + 2
            textarea.selectionEnd = end + (lines.filter(l => l.trim().length > 0).length * 2)
          }
        }, 0)
        return
      }
    }

    // Tab for non-code cells - just insert spaces
    if (e.key === 'Tab' && !e.shiftKey && cell.type !== 'code') {
      e.preventDefault()
      if (textarea) {
        const start = textarea.selectionStart
        const end = textarea.selectionEnd
        const value = textarea.value
        const newValue = value.substring(0, start) + '    ' + value.substring(end)
        onUpdate({ source: newValue })
        setTimeout(() => {
          textarea.selectionStart = textarea.selectionEnd = start + 4
        }, 0)
      }
    }
  }, [onRunAndAdvance, onUpdate, cell.type, cell.id, onExitEditMode])

  const renderOutput = (output: CellOutput, idx: number) => {
    switch (output.output_type) {
      case 'stream':
        const rawText = Array.isArray(output.text) ? output.text.join('') : output.text || ''
        const text = processTerminalOutput(rawText)
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
          // HTML output (tables, rich display)
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
          // SVG images
          if (output.data['image/svg+xml']) {
            return (
              <div
                key={idx}
                className="max-w-full"
                dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(output.data['image/svg+xml'] as string) }}
              />
            )
          }
          // PNG images
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
          // JPEG images
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
          // GIF images
          if (output.data['image/gif']) {
            return (
              <img
                key={idx}
                src={`data:image/gif;base64,${output.data['image/gif']}`}
                alt="Output"
                className="max-w-full"
              />
            )
          }
          // Video (MP4, WebM)
          if (output.data['video/mp4'] || output.data['video/webm']) {
            const videoType = output.data['video/mp4'] ? 'video/mp4' : 'video/webm'
            const videoData = output.data[videoType] as string
            return (
              <video
                key={idx}
                controls
                className="max-w-full"
                style={{ maxHeight: '400px' }}
              >
                <source src={`data:${videoType};base64,${videoData}`} type={videoType} />
                Your browser does not support video playback.
              </video>
            )
          }
          // Audio (MP3, WAV, OGG)
          if (output.data['audio/mpeg'] || output.data['audio/wav'] || output.data['audio/ogg']) {
            const audioType = output.data['audio/mpeg'] ? 'audio/mpeg' :
                             output.data['audio/wav'] ? 'audio/wav' : 'audio/ogg'
            const audioData = output.data[audioType] as string
            return (
              <audio
                key={idx}
                controls
                className="w-full"
              >
                <source src={`data:${audioType};base64,${audioData}`} type={audioType} />
                Your browser does not support audio playback.
              </audio>
            )
          }
          // JSON data (pretty-printed)
          if (output.data['application/json']) {
            const jsonData = output.data['application/json']
            return (
              <pre
                key={idx}
                className="text-sm whitespace-pre-wrap font-mono p-2 rounded"
                style={{
                  color: 'var(--nb-text-output, var(--nb-text-primary))',
                  backgroundColor: 'var(--nb-bg-secondary)',
                }}
              >
                {typeof jsonData === 'string' ? jsonData : JSON.stringify(jsonData, null, 2)}
              </pre>
            )
          }
          // LaTeX (rendered as-is with styling, full rendering would need KaTeX/MathJax)
          if (output.data['text/latex']) {
            const latex = Array.isArray(output.data['text/latex'])
              ? output.data['text/latex'].join('')
              : output.data['text/latex']
            return (
              <div
                key={idx}
                className="text-sm font-mono p-2 rounded"
                style={{
                  color: 'var(--nb-accent-markdown)',
                  backgroundColor: 'var(--nb-bg-secondary)',
                }}
              >
                {latex as string}
              </div>
            )
          }
          // Markdown (rendered)
          if (output.data['text/markdown']) {
            const md = Array.isArray(output.data['text/markdown'])
              ? output.data['text/markdown'].join('')
              : output.data['text/markdown']
            try {
              const html = marked.parse(md as string) as string
              return (
                <div
                  key={idx}
                  className="prose prose-sm max-w-none"
                  style={{ color: 'var(--nb-text-output, var(--nb-text-primary))' }}
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}
                />
              )
            } catch {
              return (
                <pre key={idx} className="text-sm whitespace-pre-wrap font-mono">
                  {md as string}
                </pre>
              )
            }
          }
          // PDF (embedded viewer)
          if (output.data['application/pdf']) {
            return (
              <iframe
                key={idx}
                src={`data:application/pdf;base64,${output.data['application/pdf']}`}
                className="w-full border-0 rounded"
                style={{ height: '500px' }}
                title="PDF Output"
              />
            )
          }
          // Plain text (fallback)
          if (output.data['text/plain']) {
            const rawPlainText = Array.isArray(output.data['text/plain'])
              ? output.data['text/plain'].join('')
              : output.data['text/plain']
            const plainText = processTerminalOutput(rawPlainText as string)
            return (
              <pre
                key={idx}
                className="text-sm whitespace-pre-wrap font-mono"
                style={{ color: 'var(--nb-text-output, var(--nb-text-primary))' }}
              >
                {plainText}
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
                {processTerminalOutput(output.traceback.join('\n'))}
              </pre>
            )}
          </div>
        )
      default:
        return null
    }
  }

  // Cell type-specific classes
  const cellTypeClass = cell.type === 'code' ? 'cell-code' : cell.type === 'markdown' ? 'cell-markdown' : 'cell-raw'

  // Get background color based on cell type
  const getCellBgColor = () => {
    if (cell.type === 'code') return 'var(--nb-bg-code-cell)'
    if (cell.type === 'raw') return 'var(--nb-bg-raw-cell, #2d2a1f)'  // Warm amber tint
    return 'var(--nb-bg-markdown-cell)'
  }

  // Get selection indicator style - left border with subtle shadow
  // Blue = command mode (selected, ready to navigate)
  // Green = edit mode (typing inside cell)
  const getSelectionStyle = () => {
    if (!isSelected) {
      return {
        borderLeft: '3px solid transparent',
        boxShadow: 'none',
      }
    }
    if (isEditMode) {
      return {
        borderLeft: '3px solid #10b981', // emerald-500
        boxShadow: '0 0 12px rgba(16, 185, 129, 0.3), inset 0 0 0 1px rgba(16, 185, 129, 0.1)',
      }
    }
    return {
      borderLeft: '3px solid #3b82f6', // blue-500
      boxShadow: '0 0 8px rgba(59, 130, 246, 0.25)',
    }
  }

  return (
    <div
      id={`cell-${cell.id}`}
      className={`group rounded-lg transition-all overflow-hidden cell-wrapper ${cellTypeClass}`}
      onClick={onSelect}
      style={{
        backgroundColor: getCellBgColor(),
        borderColor: 'var(--nb-border-default)',
        ...getSelectionStyle(),
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
                : cell.type === 'raw'
                  ? 'var(--nb-accent-notes, #f59e0b)'
                  : 'var(--nb-accent-markdown)',
              color: '#11111b',
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
            ) : cell.type === 'raw' ? (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                Notes
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
      <div className="px-3 py-2" style={{ color: 'var(--nb-text-primary)' }}>
        {!showTextarea ? (
          // Rendered markdown view - click to edit
          <div
            className="prose prose-sm max-w-none cursor-text"
            onClick={(e) => {
              e.stopPropagation()
              onEnterEditMode()
            }}
            dangerouslySetInnerHTML={{ __html: renderedMarkdown }}
          />
        ) : (
          // Textarea for editing
          <textarea
            ref={textareaRef}
            value={cell.source}
            onChange={(e) => {
              onUpdate({ source: e.target.value })
            }}
            onKeyDown={handleKeyDown}
            onClick={(e) => {
              e.stopPropagation()
              // Clicking on textarea enters edit mode
              if (!isEditMode) {
                onEnterEditMode()
              }
            }}
            style={{
              color: 'var(--nb-text-primary)',
              lineHeight: '1.5',
            }}
            placeholder={cell.type === 'code' ? 'Enter Python code...' : cell.type === 'raw' ? 'Enter notes (plain text, not executed)...' : 'Enter markdown... (Shift+Enter to preview)'}
            className="w-full bg-transparent font-mono text-sm resize-none outline-none min-h-[24px]"
          />
        )}
      </div>
      </div>
      {/* End of cell content wrapper - output below is NOT highlighted */}

      {/* Cell Output */}
      {cell.type === 'code' && cell.outputs && cell.outputs.length > 0 && (
        <OutputArea outputs={cell.outputs} renderOutput={renderOutput} />
      )}
    </div>
  )
}
