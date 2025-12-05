'use client'

import { useEffect, useState, useCallback, useRef, use } from 'react'
import { useRouter } from 'next/navigation'
import { auth, projects, playgrounds, chat, notebooks } from '@/lib/api'
import { useAuthStore, useProjectsStore, useNotebookStore } from '@/lib/store'
import Cell from '@/components/notebook/Cell'
import AICell from '@/components/notebook/AICell'
import NotebookToolbar from '@/components/notebook/NotebookToolbar'
import CellInsertButtons from '@/components/notebook/CellInsertButtons'
import ChatPanel from '@/components/chat/ChatPanel'
import { useKernel } from '@/hooks/useKernel'
import { ThemeProvider } from '@/contexts/ThemeContext'
import type { Cell as CellType, Playground, ChatMessage } from '@/types'

// ANSI color code to CSS color mapping
const ansiColors: Record<number, string> = {
  30: '#4b5563', // black (gray for visibility)
  31: '#ef4444', // red
  32: '#22c55e', // green
  33: '#eab308', // yellow
  34: '#3b82f6', // blue
  35: '#a855f7', // magenta
  36: '#06b6d4', // cyan
  37: '#e5e7eb', // white
  90: '#6b7280', // bright black (gray)
  91: '#f87171', // bright red
  92: '#4ade80', // bright green
  93: '#facc15', // bright yellow
  94: '#60a5fa', // bright blue
  95: '#c084fc', // bright magenta
  96: '#22d3ee', // bright cyan
  97: '#ffffff', // bright white
}

// Parse ANSI escape codes and return array of styled segments
interface AnsiSegment {
  text: string
  color?: string
  bold?: boolean
}

function parseAnsi(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = []
  let currentColor: string | undefined
  let currentBold = false

  // Normalize different escape representations
  const normalized = text
    .replace(/␛/g, '\x1b')  // Unicode escape symbol to actual escape

  // Match ANSI sequences or text between them
  const regex = /\x1b\[([0-9;]*)m|([^\x1b]+)/g
  let match

  while ((match = regex.exec(normalized)) !== null) {
    if (match[1] !== undefined) {
      // ANSI sequence
      const codes = match[1].split(';').map(Number)
      for (const code of codes) {
        if (code === 0) {
          // Reset
          currentColor = undefined
          currentBold = false
        } else if (code === 1) {
          // Bold
          currentBold = true
        } else if (code === 22) {
          // Normal intensity (not bold)
          currentBold = false
        } else if (ansiColors[code]) {
          currentColor = ansiColors[code]
        }
      }
    } else if (match[2]) {
      // Regular text
      segments.push({
        text: match[2],
        color: currentColor,
        bold: currentBold,
      })
    }
  }

  // If no segments were found, return the original text (stripped of any remaining codes)
  if (segments.length === 0) {
    const stripped = text
      .replace(/\x1b\[[0-9;]*[a-zA-Z]/g, '')
      .replace(/\x1b\][^\x07]*\x07/g, '')
      .replace(/\x1b\[\?[0-9;]*[a-zA-Z]/g, '')
      .replace(/\x1b[=>]/g, '')
      .replace(/␛\[[0-9;]*[a-zA-Z]/g, '')
    return [{ text: stripped }]
  }

  return segments
}

// Generate unique cell ID
function generateCellId(): string {
  return `cell-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

// Create empty cell
function createCell(type: 'code' | 'markdown' | 'raw' | 'ai'): CellType {
  const cellId = generateCellId()
  const cell: CellType = {
    id: cellId,
    type,
    source: '',
    outputs: [],
    metadata: { cell_id: cellId },  // Store in metadata for ipynb compatibility
  }

  // Add AI-specific data for AI cells
  if (type === 'ai') {
    cell.ai_data = {
      user_prompt: '',
      llm_response: '',
      status: 'idle',
    }
  }

  return cell
}

interface PendingToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export default function NotebookPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params)
  const router = useRouter()

  const { setUser } = useAuthStore()
  const { currentProject, setCurrentProject } = useProjectsStore()
  const { cells, setCells, addCell, updateCell, deleteCell, moveCell, isDirty, setDirty } = useNotebookStore()

  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isSummarizing, setIsSummarizing] = useState(false)
  const [playground, setPlayground] = useState<Playground | null>(null)
  const [playgroundLoading, setPlaygroundLoading] = useState(false)
  const [selectedCellId, setSelectedCellId] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(false) // false = command mode (navigate with arrows), true = edit mode (typing)
  const [lastNavDirection, setLastNavDirection] = useState<'up' | 'down'>('down') // Track last navigation direction for Esc

  // Notebook width state - stored in localStorage for persistence
  const [notebookWidth, setNotebookWidth] = useState<number | null>(null) // null = auto (max-w-6xl)
  const [isResizing, setIsResizing] = useState(false)
  const notebookContainerRef = useRef<HTMLDivElement>(null)

  // Ref to prevent double-processing of Shift+Enter
  const shiftEnterHandledRef = useRef(false)

  // Ref for Run All to resolve promises when cells complete
  const runAllResolveRef = useRef<(() => void) | null>(null)

  // Clipboard and undo state for cell operations
  const [clipboardCell, setClipboardCell] = useState<CellType | null>(null)
  const [deletedCells, setDeletedCells] = useState<{ cell: CellType; index: number }[]>([])
  const lastKeyRef = useRef<{ key: string; time: number } | null>(null) // For double-key detection (DD)

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const [pendingTools, setPendingTools] = useState<PendingToolCall[]>([])
  const [llmProvider, setLlmProvider] = useState('gemini')
  const [toolMode, setToolMode] = useState<'auto' | 'manual' | 'ai_decide'>('auto')
  const [contextFormat, setContextFormat] = useState<'xml' | 'plain'>('xml')
  const [showChat, setShowChat] = useState(true)
  const [errorPopup, setErrorPopup] = useState<string | null>(null)
  const [confirmPopup, setConfirmPopup] = useState<{
    title: string
    message: string
    onConfirm: () => void
    confirmText?: string
    confirmColor?: string
  } | null>(null)


  // Kernel hook - connect to playground when running
  // Construct URL through nginx proxy: /playground/{container_name}
  const playgroundUrl = playground?.status === 'running' && playground?.container_name
    ? `${window.location.origin}/playground/${playground.container_name}`
    : null
  // Pass projectId as sessionId so frontend kernel and AI Cell tools use the same kernel
  const kernel = useKernel(playgroundUrl, projectId)

  // Helper to save notebook (for auto-save before chat)
  const saveNotebook = useCallback(async () => {
    if (!currentProject) return false

    try {
      // Save in Jupyter .ipynb standard format
      const cellsToSave = cells.map((cell) => {
        const cellToSave = {
          cell_type: cell.type,  // Jupyter standard field name
          source: cell.source,
          outputs: (cell.outputs || []) as unknown as Record<string, unknown>[],
          execution_count: cell.execution_count,
          metadata: { ...cell.metadata, cell_id: cell.id } as Record<string, unknown>,  // cell_id in metadata only
          ai_data: cell.type === 'ai' && cell.ai_data ? cell.ai_data : undefined,
        }
        return cellToSave
      })

      await notebooks.save(projectId, cellsToSave as Parameters<typeof notebooks.save>[1])
      setDirty(false)
      console.log('Notebook auto-saved before chat')
      return true
    } catch (err) {
      console.error('Failed to auto-save notebook:', err)
      return false
    }
  }, [currentProject, projectId, cells, setDirty])

  // Helper to reload notebook from S3 (after LLM tools modify it)
  const reloadNotebook = useCallback(async () => {
    try {
      const notebookData = await notebooks.get(projectId)
      if (notebookData.notebook.cells.length > 0) {
        const loadedCells = notebookData.notebook.cells.map((cell) => {
          const cellType = (cell.cell_type || cell.type || 'code') as 'code' | 'markdown' | 'raw' | 'ai'
          const loadedCell: CellType = {
            id: (cell.metadata?.cell_id as string) || generateCellId(),
            type: cellType,
            source: cell.source,
            outputs: cell.outputs as any[],
            execution_count: cell.execution_count,
            metadata: cell.metadata,
          }
          // Load ai_data for AI cells
          if (cellType === 'ai' && (cell as any).ai_data) {
            loadedCell.ai_data = (cell as any).ai_data
          }
          return loadedCell
        })
        setCells(loadedCells)
        setDirty(false)
        console.log('Notebook reloaded from S3 after LLM update')
      }
    } catch (err) {
      console.error('Failed to reload notebook:', err)
    }
  }, [projectId, setCells, setDirty])
  // Note: syncNotebookToPlayground removed - LLM tools now fetch from Master API directly

  // Load project and notebook
  useEffect(() => {
    const init = async () => {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) {
          router.push('/auth/login')
          return
        }

        // Get user
        const userData = await auth.getMe()
        setUser(userData)

        // Get project
        const project = await projects.get(projectId)
        setCurrentProject(project)

        // Get existing playground status
        const pg = await playgrounds.get(projectId)
        setPlayground(pg)

        // If playground not running, show error and redirect back to dashboard
        if (!pg || pg.status !== 'running') {
          console.warn('Playground not running, redirecting to dashboard')
          // Can't use setErrorPopup here as component isn't mounted yet
          // Use a brief timeout to show alert-style message before redirect
          setTimeout(() => {
            router.push('/dashboard')
          }, 100)
          // Set a flag to show message on dashboard (stored in sessionStorage)
          sessionStorage.setItem('notebook_redirect_message', 'Playground is not running. Please start it from the dashboard first.')
          return
        }

        // Load notebook from S3
        try {
          const notebookData = await notebooks.get(projectId)
          if (notebookData.notebook.cells.length > 0) {
            // Convert to our cell format (Jupyter standard: cell_type and metadata.cell_id)
            const loadedCells = notebookData.notebook.cells.map((cell) => {
              const cellType = (cell.cell_type || cell.type || 'code') as 'code' | 'markdown' | 'raw' | 'ai'
              const loadedCell: CellType = {
                id: (cell.metadata?.cell_id as string) || generateCellId(),
                type: cellType,
                source: cell.source,
                outputs: cell.outputs as any[],
                execution_count: cell.execution_count,
                metadata: cell.metadata,
              }
              // Load ai_data for AI cells
              if (cellType === 'ai' && (cell as any).ai_data) {
                loadedCell.ai_data = (cell as any).ai_data
              }
              return loadedCell
            })
            setCells(loadedCells)
          } else {
            // Initialize with one empty code cell if none
            const newCell = createCell('code')
            setCells([newCell])
          }
        } catch {
          // No notebook yet, start with empty cell
          const newCell = createCell('code')
          setCells([newCell])
        }

        // Load chat history
        try {
          const historyData = await chat.getHistory(projectId)
          if (historyData.success && historyData.messages && historyData.messages.length > 0) {
            setChatMessages(historyData.messages.map(m => ({
              role: m.role as 'user' | 'assistant',
              content: m.content,
            })))
            console.log(`Loaded ${historyData.messages.length} messages from chat history`)
          }
        } catch {
          // No chat history yet
          console.log('No chat history found')
        }

      } catch (err) {
        console.error('Failed to initialize:', err)
        router.push('/dashboard')
      } finally {
        setIsLoading(false)
      }
    }

    init()
  }, [projectId, router, setUser, setCurrentProject, setCells])

  // Note: Notebook sync on load removed - LLM tools now fetch from Master API directly

  // Setup kernel callbacks
  useEffect(() => {
    kernel.setOutputCallback((cellId, output) => {
      // Get current cell to append/merge outputs
      const cell = cells.find((c) => c.id === cellId)
      if (cell) {
        // For stream outputs, merge with the last output if it's also a stream
        // This allows proper handling of \r for progress bars
        if (output.output_type === 'stream' && cell.outputs.length > 0) {
          const lastOutput = cell.outputs[cell.outputs.length - 1]
          if (lastOutput.output_type === 'stream') {
            // Merge stream text - append new text to existing
            const existingText = Array.isArray(lastOutput.text)
              ? lastOutput.text.join('')
              : lastOutput.text || ''
            const newText = Array.isArray(output.text)
              ? output.text.join('')
              : output.text || ''

            // Update the last output with merged text
            const updatedOutputs = [...cell.outputs]
            updatedOutputs[updatedOutputs.length - 1] = {
              ...lastOutput,
              text: existingText + newText,
            }
            updateCell(cellId, { outputs: updatedOutputs })
            return
          }
        }

        // For non-stream or first output, just append
        updateCell(cellId, {
          outputs: [...cell.outputs, output],
        })
      }
    })

    kernel.setExecutionCountCallback((cellId, count) => {
      updateCell(cellId, { execution_count: count })
    })

    kernel.setCompletionCallback((cellId, success) => {
      console.log(`Cell ${cellId} completed: ${success ? 'success' : 'error'}`)
      // Resolve Run All promise if waiting
      if (runAllResolveRef.current) {
        const resolve = runAllResolveRef.current
        runAllResolveRef.current = null
        resolve()
      }
    })
  }, [kernel, cells, updateCell])

  // Load notebook width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem('notebook-width')
    if (savedWidth) {
      const width = parseInt(savedWidth, 10)
      if (!isNaN(width) && width >= 400 && width <= 2400) {
        setNotebookWidth(width)
      }
    }
  }, [])

  // Handle resize drag - side parameter determines direction
  const handleResizeStart = useCallback((e: React.MouseEvent, side: 'left' | 'right') => {
    e.preventDefault()
    setIsResizing(true)

    const startX = e.clientX
    const container = notebookContainerRef.current
    if (!container) return

    const startWidth = container.offsetWidth

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - startX
      // Left side: dragging left (negative deltaX) should expand
      // Right side: dragging right (positive deltaX) should expand
      const multiplier = side === 'left' ? -2 : 2
      const newWidth = Math.max(400, Math.min(2400, startWidth + deltaX * multiplier))
      setNotebookWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      // Save to localStorage
      if (notebookContainerRef.current) {
        localStorage.setItem('notebook-width', notebookContainerRef.current.offsetWidth.toString())
      }
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [])

  // Reset notebook width to default
  const resetNotebookWidth = useCallback(() => {
    setNotebookWidth(null)
    localStorage.removeItem('notebook-width')
  }, [])

  // Heartbeat to keep playground alive - sends activity ping every 2 minutes
  useEffect(() => {
    // Only run heartbeat if playground is running
    if (!playground || playground.status !== 'running') {
      return
    }

    // Send initial heartbeat
    playgrounds.updateActivity(projectId).catch((err) => {
      console.warn('Failed to send activity heartbeat:', err)
    })

    // Set up interval for heartbeat every 2 minutes
    const heartbeatInterval = setInterval(() => {
      // Check if tab is visible before sending heartbeat
      if (document.visibilityState === 'visible') {
        playgrounds.updateActivity(projectId).catch((err) => {
          console.warn('Failed to send activity heartbeat:', err)
        })
      }
    }, 2 * 60 * 1000) // 2 minutes

    // Cleanup on unmount or when playground stops
    return () => {
      clearInterval(heartbeatInterval)
    }
  }, [projectId, playground?.status])

  // Playground handlers
  const handleStartPlayground = async () => {
    setPlaygroundLoading(true)
    try {
      const { playground: pg } = await playgrounds.start(projectId)
      setPlayground(pg)
    } catch (err) {
      console.error('Failed to start playground:', err)
    } finally {
      setPlaygroundLoading(false)
    }
  }

  const handleStopPlayground = async () => {
    setPlaygroundLoading(true)
    try {
      await playgrounds.stop(projectId)
      setPlayground((prev) => prev ? { ...prev, status: 'stopped' } : null)
    } catch (err) {
      console.error('Failed to stop playground:', err)
    } finally {
      setPlaygroundLoading(false)
    }
  }

  // Cell handlers
  const handleAddCell = useCallback((type: 'code' | 'markdown' | 'ai') => {
    const newCell = createCell(type)
    const selectedIndex = cells.findIndex((c) => c.id === selectedCellId)
    addCell(newCell, selectedIndex >= 0 ? selectedIndex + 1 : undefined)
    setSelectedCellId(newCell.id)
  }, [cells, selectedCellId, addCell])

  // Insert cell at specific position (used by insert buttons between cells)
  const handleInsertCellAt = useCallback((type: 'code' | 'markdown' | 'ai', index: number) => {
    const newCell = createCell(type)
    addCell(newCell, index)
    setSelectedCellId(newCell.id)
  }, [addCell])

  // Delete cell
  const handleDeleteCell = useCallback((cellId: string) => {
    deleteCell(cellId)
  }, [deleteCell])

  // Run AI cell - send prompt to LLM with notebook context
  const handleRunAICell = useCallback(async (cellId: string, prompt: string) => {
    if (!playground || playground.status !== 'running') {
      updateCell(cellId, {
        ai_data: {
          user_prompt: prompt,
          llm_response: '',
          status: 'error',
          error: 'Playground is not running. Start the playground first.',
        },
      })
      return
    }

    // Save notebook first to ensure context is up to date
    await saveNotebook()

    // Get all cell IDs for context (excluding the AI cell itself)
    const contextCellIds = cells
      .filter(c => c.id !== cellId && c.type !== 'ai')
      .map(c => c.id)

    // Get AI cell's position for positional awareness
    const aiCellIndex = cells.findIndex(c => c.id === cellId)

    try {
      const response = await chat.runAICell(projectId, prompt, contextCellIds, llmProvider, cellId, aiCellIndex, contextFormat)

      updateCell(cellId, {
        ai_data: {
          user_prompt: prompt,
          llm_response: response.response,
          status: response.success ? 'completed' : 'error',
          model: response.model,
          error: response.error,
          timestamp: new Date().toISOString(),
        },
      })

      // Auto-save after AI cell completion to persist the response
      await saveNotebook()
    } catch (err) {
      updateCell(cellId, {
        ai_data: {
          user_prompt: prompt,
          llm_response: '',
          status: 'error',
          error: err instanceof Error ? err.message : 'Unknown error',
        },
      })
    }
  }, [cells, playground, projectId, llmProvider, contextFormat, updateCell, saveNotebook])

  // Insert code cells from AI cell suggestion (supports multiple code blocks)
  const handleInsertCodeFromAICell = useCallback((afterCellId: string, codeBlocks: string[]) => {
    const cellIndex = cells.findIndex(c => c.id === afterCellId)
    if (cellIndex === -1 || codeBlocks.length === 0) return

    // Insert all code blocks as separate cells
    let lastNewCellId = ''
    codeBlocks.forEach((code, idx) => {
      const newCell = createCell('code')
      newCell.source = code
      addCell(newCell, cellIndex + 1 + idx)
      lastNewCellId = newCell.id
    })

    // Select the last inserted cell
    if (lastNewCellId) {
      setSelectedCellId(lastNewCellId)
    }
  }, [cells, addCell])

  // Scroll to a specific cell by ID (used for @cell-xxx references in AI responses)
  const handleScrollToCell = useCallback((cellId: string) => {
    console.log('[Page] handleScrollToCell called with cellId:', cellId)
    const elementId = `cell-${cellId}`
    console.log('[Page] Looking for element with ID:', elementId)
    const cellElement = document.getElementById(elementId)
    console.log('[Page] Found element:', !!cellElement)
    if (cellElement) {
      cellElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Select the cell and briefly highlight it
      setSelectedCellId(cellId)
      // Add a brief highlight effect
      cellElement.style.transition = 'box-shadow 0.3s ease'
      cellElement.style.boxShadow = '0 0 20px rgba(168, 85, 247, 0.6)'
      setTimeout(() => {
        cellElement.style.boxShadow = ''
      }, 1500)
    } else {
      console.log('[Page] Element not found! Available cells:', cells.map(c => c.id))
    }
  }, [cells])

  const handleRunCell = useCallback((cellId: string) => {
    const cell = cells.find((c) => c.id === cellId)
    if (!cell || cell.type !== 'code' || !cell.source.trim()) return

    if (!playground || playground.status !== 'running') {
      setErrorPopup('Please start the playground first to run code cells.')
      return
    }

    // Clear previous outputs
    updateCell(cellId, { outputs: [] })

    // Execute via kernel
    const success = kernel.execute(cellId, cell.source)
    if (!success) {
      console.error('Failed to execute cell - kernel not ready')
    }
  }, [cells, playground, kernel, updateCell])

  const handleRunAll = useCallback(async () => {
    if (!playground || playground.status !== 'running') {
      setErrorPopup('Please start the playground first to run all cells.')
      return
    }

    // Get all code cells with content
    const codeCells = cells.filter(cell => cell.type === 'code' && cell.source.trim())

    for (const cell of codeCells) {
      // Select the cell and scroll to it
      setSelectedCellId(cell.id)
      setIsEditMode(false)

      // Scroll cell into view
      setTimeout(() => {
        const cellElement = document.getElementById(`cell-${cell.id}`)
        if (cellElement) {
          cellElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 50)

      // Clear outputs
      updateCell(cell.id, { outputs: [] })

      // Execute and wait for completion using a ref-based approach
      await new Promise<void>((resolve) => {
        runAllResolveRef.current = resolve

        // Timeout after 5 minutes
        const timeout = setTimeout(() => {
          if (runAllResolveRef.current === resolve) {
            runAllResolveRef.current = null
            resolve()
          }
        }, 300000)

        // Send execution directly via WebSocket to avoid stale closure
        kernel.execute(cell.id, cell.source)
      })

      // Small delay before next cell
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }, [cells, playground, kernel, updateCell])

  const handleClearOutputs = useCallback(() => {
    cells.forEach((cell) => {
      if (cell.type === 'code') {
        updateCell(cell.id, { outputs: [], execution_count: undefined })
      }
    })
  }, [cells, updateCell])

  const handleDeleteAllCells = useCallback(() => {
    if (cells.length === 0) return

    setConfirmPopup({
      title: 'Delete All Cells',
      message: `Are you sure you want to delete all ${cells.length} cell${cells.length > 1 ? 's' : ''}?\n\nThis action cannot be undone.`,
      confirmText: 'Delete All',
      confirmColor: 'red',
      onConfirm: () => {
        // Clear all cells and add one empty code cell
        setCells([createCell('code')])
        setSelectedCellId(null)
        setConfirmPopup(null)
      },
    })
  }, [cells.length])


  const handleSave = useCallback(async () => {
    if (!currentProject) return
    setIsSaving(true)
    try {
      // Save notebook to S3 via API (Jupyter .ipynb standard format)
      const cellsToSave = cells.map((cell) => {
        const cellToSave = {
          cell_type: cell.type,  // Jupyter standard field name
          source: cell.source,
          outputs: (cell.outputs || []) as unknown as Record<string, unknown>[],
          execution_count: cell.execution_count,
          metadata: { ...cell.metadata, cell_id: cell.id } as Record<string, unknown>,  // cell_id in metadata only
          ai_data: cell.type === 'ai' && cell.ai_data ? cell.ai_data : undefined,
        }
        return cellToSave
      })

      const result = await notebooks.save(projectId, cellsToSave as Parameters<typeof notebooks.save>[1])
      console.log('Notebook saved:', result)
      setDirty(false)
      // Note: No sync needed - LLM tools fetch from Master API directly
    } catch (err) {
      console.error('Failed to save:', err)
      setErrorPopup('Failed to save notebook. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [currentProject, projectId, cells, setDirty])

  const handleExport = useCallback(async () => {
    if (!currentProject) return
    setIsExporting(true)
    try {
      // First save the notebook to ensure we export the latest version
      if (isDirty) {
        await handleSave()
      }

      // Export notebook as .ipynb
      const ipynbData = await notebooks.export(projectId)

      // Create a blob and download
      const blob = new Blob([JSON.stringify(ipynbData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${currentProject.name.replace(/[^a-z0-9]/gi, '_')}.ipynb`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      console.log('Notebook exported successfully')
    } catch (err) {
      console.error('Failed to export:', err)
      setErrorPopup('Failed to export notebook. Please try again.')
    } finally {
      setIsExporting(false)
    }
  }, [currentProject, projectId, isDirty, handleSave])

  const handleSummarize = useCallback(async () => {
    if (!currentProject || cells.length === 0) {
      setErrorPopup('No cells to summarize. Add some content first.')
      return
    }

    // Check if playground is running (needed for LLM)
    if (!playground || playground.status !== 'running') {
      setErrorPopup('Please start the playground first to use AI summarization.')
      return
    }

    setIsSummarizing(true)
    try {
      // Save notebook first if dirty
      if (isDirty) {
        await handleSave()
      }

      // Call the summarize API
      const result = await notebooks.summarize(projectId, llmProvider)

      if (result.success && result.summary) {
        // Create a new markdown cell with the summary at the top
        const summaryCell = createCell('markdown')
        summaryCell.source = `# Notebook Summary\n\n${result.summary}\n\n---\n*Generated by AI on ${new Date().toLocaleString()}*`

        // Add the cell at the beginning
        addCell(summaryCell, 0)
        setSelectedCellId(summaryCell.id)
        // Note: Summary cell is NOT auto-added to context (user can manually add if needed)

        console.log('Summary generated and added to notebook')
      } else {
        setErrorPopup(result.error || 'Failed to generate summary. Please try again.')
      }
    } catch (err) {
      console.error('Failed to summarize:', err)
      setErrorPopup('Failed to generate summary. Please try again.')
    } finally {
      setIsSummarizing(false)
    }
  }, [currentProject, projectId, cells.length, isDirty, handleSave, playground, llmProvider, addCell])

  // Handle logs - open in new tab
  const handleOpenLogs = useCallback(() => {
    window.open(`/logs/${projectId}`, '_blank')
  }, [projectId])

  // Get selected cell index helper
  const getSelectedCellIndex = useCallback(() => {
    if (!selectedCellId) return -1
    return cells.findIndex(c => c.id === selectedCellId)
  }, [selectedCellId, cells])

  // Navigate to cell by index and optionally focus it
  const navigateToCell = useCallback((index: number, focus: boolean = false) => {
    if (index >= 0 && index < cells.length) {
      const cellId = cells[index].id
      console.log('[Page] navigateToCell called, index:', index, 'cellId:', cellId)
      setSelectedCellId(cellId)
      // Scroll cell into view
      const cellElement = document.getElementById(`cell-${cellId}`)
      if (cellElement) {
        cellElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        // Focus the textarea if requested
        if (focus) {
          setTimeout(() => {
            const textarea = cellElement.querySelector('textarea') as HTMLTextAreaElement
            if (textarea) {
              textarea.focus()
              // Put cursor at the start for up navigation, end for down navigation
              textarea.setSelectionRange(0, 0)
            }
          }, 50)
        }
      }
    }
  }, [cells])

  // Enter edit mode on selected cell
  const enterEditMode = useCallback(() => {
    if (!selectedCellId) return
    setIsEditMode(true)
    // Focus the textarea of the selected cell
    setTimeout(() => {
      const cellElement = document.getElementById(`cell-${selectedCellId}`)
      const textarea = cellElement?.querySelector('textarea') as HTMLTextAreaElement
      if (textarea) {
        textarea.focus()
        // Put cursor at the end
        textarea.setSelectionRange(textarea.value.length, textarea.value.length)
      }
    }, 10)
  }, [selectedCellId])

  // Exit edit mode - optionally move to next cell in navigation direction
  // shiftEnterHandled: set to true when called from Shift+Enter to prevent double execution
  const exitEditMode = useCallback((moveToNext: boolean = false, shiftEnterHandled: boolean = false) => {
    console.log('[Page] exitEditMode called, moveToNext:', moveToNext, 'shiftEnterHandled:', shiftEnterHandled, 'selectedCellId:', selectedCellId)

    // Set flag to prevent global handler from double-processing
    if (moveToNext || shiftEnterHandled) {
      shiftEnterHandledRef.current = true
      // Reset the flag after a short delay
      setTimeout(() => {
        shiftEnterHandledRef.current = false
      }, 100)
    }

    setIsEditMode(false)
    // Blur any focused textarea
    const activeElement = document.activeElement
    if (activeElement instanceof HTMLElement) {
      activeElement.blur()
    }

    // Move to next cell if requested (for Shift+Enter)
    if (moveToNext && selectedCellId) {
      const currentIndex = cells.findIndex(c => c.id === selectedCellId)
      console.log('[Page] Moving to next cell, currentIndex:', currentIndex, 'total cells:', cells.length)
      if (currentIndex < cells.length - 1) {
        const nextCellId = cells[currentIndex + 1].id
        console.log('[Page] Setting selectedCellId to:', nextCellId)
        setSelectedCellId(nextCellId)
        setTimeout(() => {
          const cellElement = document.getElementById(`cell-${nextCellId}`)
          if (cellElement) {
            cellElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          }
        }, 10)
      }
    }
  }, [selectedCellId, cells])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+S / Cmd+S to save - works everywhere
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
        return
      }

      // If we're in the chat panel, modal inputs, or any text input, ignore all shortcuts
      const activeElement = document.activeElement
      const isInChatOrModal = activeElement?.closest('.chat-panel') ||
        activeElement?.closest('[role="dialog"]') ||
        (activeElement?.tagName === 'INPUT' && !activeElement?.closest('.cell-wrapper'))

      if (isInChatOrModal) return

      // If we're in a cell textarea (code cell or AI cell), skip single-key shortcuts
      // Only allow modifier combos (Ctrl/Cmd+key, Shift+Enter, etc.)
      const isInCellTextarea = activeElement?.tagName === 'TEXTAREA' && activeElement?.closest('.cell-wrapper')
      if (isInCellTextarea) {
        // Allow Shift+Enter to be handled by cell's own handler
        if (e.key === 'Enter' && e.shiftKey) {
          console.log('[Page Global] Shift+Enter in cell textarea - skipping global handler')
          return
        }
        // Skip all single-key shortcuts (a, b, d, j, k, etc.) when typing in textarea
        if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
          return  // Let the textarea handle normal typing
        }
      }

      // Escape - exit edit mode and move in last navigation direction
      if (e.key === 'Escape' && isEditMode) {
        e.preventDefault()
        exitEditMode()
        // Move to next cell in the last navigation direction
        const currentIndex = getSelectedCellIndex()
        if (lastNavDirection === 'down' && currentIndex < cells.length - 1) {
          navigateToCell(currentIndex + 1)
        } else if (lastNavDirection === 'up' && currentIndex > 0) {
          navigateToCell(currentIndex - 1)
        }
        return
      }

      // Command mode shortcuts (when NOT in edit mode)
      if (!isEditMode) {
        // Arrow Up - select previous cell
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          setLastNavDirection('up')
          const currentIndex = getSelectedCellIndex()
          console.log('[Page] ArrowUp pressed, currentIndex:', currentIndex, 'isEditMode:', isEditMode)
          if (currentIndex > 0) {
            navigateToCell(currentIndex - 1)
          } else if (currentIndex === -1 && cells.length > 0) {
            navigateToCell(cells.length - 1)
          }
          return
        }

        // Arrow Down - select next cell
        if (e.key === 'ArrowDown') {
          e.preventDefault()
          setLastNavDirection('down')
          const currentIndex = getSelectedCellIndex()
          console.log('[Page] ArrowDown pressed, currentIndex:', currentIndex, 'isEditMode:', isEditMode)
          if (currentIndex < cells.length - 1) {
            navigateToCell(currentIndex + 1)
          } else if (currentIndex === -1 && cells.length > 0) {
            navigateToCell(0)
          }
          return
        }

        // Enter - enter edit mode on selected cell
        if (e.key === 'Enter' && !e.shiftKey && selectedCellId) {
          e.preventDefault()
          enterEditMode()
          return
        }

        // Shift+Enter in command mode - run selected cell and move to next
        if (e.key === 'Enter' && e.shiftKey && selectedCellId) {
          // Check if this was already handled by a cell's handler
          if (shiftEnterHandledRef.current) {
            console.log('[Page Global] Shift+Enter already handled by cell - skipping')
            return
          }
          // Do nothing if any cell is already running
          if (kernel.runningCellId !== null) {
            console.log('[Page Global] Shift+Enter ignored - a cell is already running')
            return
          }
          e.preventDefault()
          console.log('[Page Global] Shift+Enter in COMMAND mode - running cell and moving to next')
          handleRunCell(selectedCellId)
          const currentIndex = getSelectedCellIndex()
          if (currentIndex < cells.length - 1) {
            navigateToCell(currentIndex + 1)
          }
          return
        }

        // A - Insert cell above
        if (e.key === 'a' || e.key === 'A') {
          e.preventDefault()
          const currentIndex = getSelectedCellIndex()
          const newCell = createCell('code')
          if (currentIndex >= 0) {
            addCell(newCell, currentIndex)
          } else {
            addCell(newCell, 0)
          }
          setSelectedCellId(newCell.id)
          return
        }

        // B - Insert cell below
        if (e.key === 'b' || e.key === 'B') {
          e.preventDefault()
          const currentIndex = getSelectedCellIndex()
          const newCell = createCell('code')
          if (currentIndex >= 0) {
            addCell(newCell, currentIndex + 1)
          } else {
            addCell(newCell, cells.length)
          }
          setSelectedCellId(newCell.id)
          return
        }

        // D twice - Delete selected cell
        if (e.key === 'd' || e.key === 'D') {
          const now = Date.now()
          if (lastKeyRef.current?.key === 'd' && now - lastKeyRef.current.time < 500) {
            // Double D pressed within 500ms
            e.preventDefault()
            if (selectedCellId) {
              const currentIndex = getSelectedCellIndex()
              const cellToDelete = cells.find(c => c.id === selectedCellId)
              if (cellToDelete) {
                // Save for undo
                setDeletedCells(prev => [...prev, { cell: cellToDelete, index: currentIndex }])
                deleteCell(selectedCellId)
                // Select next cell or previous if at end
                if (currentIndex < cells.length - 1) {
                  setSelectedCellId(cells[currentIndex + 1]?.id || null)
                } else if (currentIndex > 0) {
                  setSelectedCellId(cells[currentIndex - 1]?.id || null)
                }
              }
            }
            lastKeyRef.current = null
          } else {
            lastKeyRef.current = { key: 'd', time: now }
          }
          return
        }

        // X - Cut selected cell
        if (e.key === 'x' || e.key === 'X') {
          e.preventDefault()
          if (selectedCellId) {
            const currentIndex = getSelectedCellIndex()
            const cellToCut = cells.find(c => c.id === selectedCellId)
            if (cellToCut) {
              setClipboardCell({ ...cellToCut })
              setDeletedCells(prev => [...prev, { cell: cellToCut, index: currentIndex }])
              deleteCell(selectedCellId)
              // Select next cell or previous if at end
              if (currentIndex < cells.length - 1) {
                setSelectedCellId(cells[currentIndex + 1]?.id || null)
              } else if (currentIndex > 0) {
                setSelectedCellId(cells[currentIndex - 1]?.id || null)
              }
            }
          }
          return
        }

        // C - Copy selected cell
        if (e.key === 'c' || e.key === 'C') {
          e.preventDefault()
          if (selectedCellId) {
            const cellToCopy = cells.find(c => c.id === selectedCellId)
            if (cellToCopy) {
              setClipboardCell({ ...cellToCopy })
            }
          }
          return
        }

        // V - Paste cell below
        if (e.key === 'v' || e.key === 'V') {
          e.preventDefault()
          if (clipboardCell) {
            const currentIndex = getSelectedCellIndex()
            // Create new cell with new ID but same content
            const newCell: CellType = {
              ...clipboardCell,
              id: `cell-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
              metadata: { ...clipboardCell.metadata, cell_id: `cell-${Date.now()}-${Math.random().toString(36).substr(2, 9)}` },
              outputs: [], // Clear outputs for pasted cell
              execution_count: undefined,
            }
            if (currentIndex >= 0) {
              addCell(newCell, currentIndex + 1)
            } else {
              addCell(newCell, cells.length)
            }
            setSelectedCellId(newCell.id)
          }
          return
        }

        // Z - Undo cell deletion
        if (e.key === 'z' || e.key === 'Z') {
          e.preventDefault()
          if (deletedCells.length > 0) {
            const lastDeleted = deletedCells[deletedCells.length - 1]
            // Restore with original ID
            addCell(lastDeleted.cell, lastDeleted.index)
            setDeletedCells(prev => prev.slice(0, -1))
            setSelectedCellId(lastDeleted.cell.id)
          }
          return
        }

        // Y - Change cell to code (not allowed for raw/ai cells)
        if (e.key === 'y' || e.key === 'Y') {
          e.preventDefault()
          if (selectedCellId) {
            const cell = cells.find(c => c.id === selectedCellId)
            if (cell && cell.type !== 'raw' && cell.type !== 'ai' && cell.type !== 'code') {
              updateCell(selectedCellId, { type: 'code' })
            }
          }
          return
        }

        // M - Change cell to markdown (not allowed for raw/ai cells)
        if (e.key === 'm' || e.key === 'M') {
          e.preventDefault()
          if (selectedCellId) {
            const cell = cells.find(c => c.id === selectedCellId)
            if (cell && cell.type !== 'raw' && cell.type !== 'ai' && cell.type !== 'markdown') {
              updateCell(selectedCellId, { type: 'markdown' })
            }
          }
          return
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave, isEditMode, getSelectedCellIndex, navigateToCell, cells, selectedCellId, enterEditMode, exitEditMode, handleRunCell, lastNavDirection, clipboardCell, deletedCells, addCell, deleteCell, updateCell])

  const handleRestartKernel = useCallback(() => {
    setConfirmPopup({
      title: 'Restart Kernel',
      message: 'Are you sure you want to restart the kernel?\n\nThis will clear all variables and execution state. Any unsaved data in memory will be lost.',
      confirmText: 'Restart',
      confirmColor: 'red',
      onConfirm: async () => {
        setConfirmPopup(null)
        const success = await kernel.restart()
        if (success) {
          // Clear execution counts
          cells.forEach((cell) => {
            if (cell.type === 'code') {
              updateCell(cell.id, { execution_count: undefined })
            }
          })
        }
      },
    })
  }, [kernel, cells, updateCell])

  // Handle LLM provider change (local state only, not persisted)
  const handleProviderChange = useCallback((provider: string) => {
    setLlmProvider(provider)
  }, [])

  // Chat handlers
  const handleSendMessage = useCallback(async (message: string) => {
    // Check if playground is running
    if (!playground || playground.status !== 'running') {
      const shouldStart = confirm('Playground is not running. Start it now?')
      if (shouldStart) {
        setPlaygroundLoading(true)
        try {
          const { playground: pg } = await playgrounds.start(projectId)
          setPlayground(pg)
          // Wait a moment for playground to be ready
          await new Promise(resolve => setTimeout(resolve, 2000))
        } catch (err) {
          console.error('Failed to start playground:', err)
          setErrorPopup('Failed to start playground. Please try again.')
          setPlaygroundLoading(false)
          return
        } finally {
          setPlaygroundLoading(false)
        }
      } else {
        return
      }
    }

    setChatLoading(true)
    setChatMessages((prev) => [...prev, { role: 'user', content: message }])

    try {
      // Auto-save notebook before sending message (ensure LLM sees latest edits via Master API)
      if (isDirty) {
        await saveNotebook()
      }

      // Send ALL cell IDs - backend loads content from S3 and creates tiered context
      const allCellIds = cells.map(c => c.id)

      // Call chat API - backend loads cell content from S3 notebook
      const response = await chat.sendMessage(projectId, message, allCellIds, toolMode, llmProvider, contextFormat)

      if (response.success) {
        // Handle pending tools
        if (response.pending_tool_calls.length > 0) {
          setPendingTools(response.pending_tool_calls)
        }

        // Add assistant response
        if (response.response) {
          setChatMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: response.response,
              steps: response.steps,
            },
          ])
        }

        // Reload notebook from S3 to get LLM tool changes
        // LLM tools modify S3 directly, so we need to refresh UI
        await reloadNotebook()
      } else {
        // Check if it's a playground/kernel error - show popup instead of saving to chat
        const errorMsg = response.error || 'Unknown error'
        if (errorMsg.includes('playground') || errorMsg.includes('kernel') ||
            errorMsg.includes('not running') || errorMsg.includes('Connection refused') ||
            errorMsg.includes('container')) {
          // Remove the user message we just added since we can't process it
          setChatMessages((prev) => prev.slice(0, -1))
          setErrorPopup(`Cannot process request: ${errorMsg}\n\nPlease make sure the playground is running.`)
        } else {
          setChatMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `Error: ${errorMsg}` },
          ])
        }
      }
    } catch (err) {
      console.error('Chat error:', err)
      // Remove the user message we just added since we can't process it
      setChatMessages((prev) => prev.slice(0, -1))
      setErrorPopup('Failed to connect to the AI service.\n\nPlease make sure the playground is running and try again.')
    } finally {
      setChatLoading(false)
    }
  }, [projectId, cells, toolMode, llmProvider, contextFormat, playground, isDirty, saveNotebook, reloadNotebook])

  const handleApproveTools = useCallback(async (tools: PendingToolCall[]) => {
    setChatLoading(true)
    try {
      const response = await chat.executeTools(projectId, tools, toolMode, llmProvider, contextFormat)

      if (response.success) {
        // Check for more pending tools
        if (response.pending_tool_calls.length > 0) {
          setPendingTools(response.pending_tool_calls)

          // For intermediate steps, update the last assistant message instead of adding new one
          if (response.response) {
            setChatMessages((prev) => {
              const newMessages = [...prev]
              const lastIdx = newMessages.length - 1

              // If last message is assistant, update it with accumulated steps
              if (lastIdx >= 0 && newMessages[lastIdx].role === 'assistant') {
                const existingSteps = newMessages[lastIdx].steps || []
                newMessages[lastIdx] = {
                  ...newMessages[lastIdx],
                  content: response.response,
                  steps: [...existingSteps, ...(response.steps || [])],
                }
              } else {
                // First assistant response after user message
                newMessages.push({
                  role: 'assistant',
                  content: response.response,
                  steps: response.steps,
                })
              }
              return newMessages
            })
          }
        } else {
          // Final response - no more pending tools
          setPendingTools([])

          // Update the last assistant message with final response and all steps
          if (response.response) {
            setChatMessages((prev) => {
              const newMessages = [...prev]
              const lastIdx = newMessages.length - 1

              // If last message is assistant, update it with final response
              if (lastIdx >= 0 && newMessages[lastIdx].role === 'assistant') {
                const existingSteps = newMessages[lastIdx].steps || []
                newMessages[lastIdx] = {
                  ...newMessages[lastIdx],
                  content: response.response,
                  steps: [...existingSteps, ...(response.steps || [])],
                }
              } else {
                // Only assistant response
                newMessages.push({
                  role: 'assistant',
                  content: response.response,
                  steps: response.steps,
                })
              }
              return newMessages
            })
          }
        }

        // Reload notebook from S3 to get LLM tool changes
        await reloadNotebook()
      } else {
        const errorMsg = response.error || 'Tool execution failed'
        if (errorMsg.includes('playground') || errorMsg.includes('kernel') ||
            errorMsg.includes('not running') || errorMsg.includes('Connection refused') ||
            errorMsg.includes('container')) {
          setErrorPopup(`Tool execution failed: ${errorMsg}\n\nPlease make sure the playground is running.`)
        } else {
          setChatMessages((prev) => [
            ...prev,
            { role: 'assistant', content: `Error: ${errorMsg}` },
          ])
        }
        setPendingTools([])
      }
    } catch (err) {
      console.error('Tool execution error:', err)
      setErrorPopup('Failed to execute tools.\n\nPlease make sure the playground is running and try again.')
      setPendingTools([])
    } finally {
      setChatLoading(false)
    }
  }, [projectId, toolMode, llmProvider, contextFormat, reloadNotebook])

  const handleRejectTools = useCallback(() => {
    setPendingTools([])
    setChatMessages((prev) => [
      ...prev,
      { role: 'assistant', content: 'Tool execution cancelled by user.' },
    ])
  }, [])

  // Delete a chat message (and all assistant responses after user message)
  const handleDeleteMessage = useCallback(async (index: number) => {
    const msg = chatMessages[index]
    if (!msg || msg.role !== 'user') return

    // Find how many consecutive assistant messages follow
    let deleteCount = 1
    let nextIndex = index + 1
    while (nextIndex < chatMessages.length && chatMessages[nextIndex].role === 'assistant') {
      deleteCount++
      nextIndex++
    }

    // Remove messages from state
    const newMessages = [...chatMessages]
    newMessages.splice(index, deleteCount)
    setChatMessages(newMessages)

    // Save to server
    try {
      await chat.saveHistory(projectId, newMessages)
    } catch (err) {
      console.error('Failed to save chat history after delete:', err)
    }
  }, [chatMessages, projectId])

  // Edit a chat message
  const handleEditMessage = useCallback(async (index: number, newContent: string) => {
    const newMessages = [...chatMessages]
    newMessages[index] = { ...newMessages[index], content: newContent }
    setChatMessages(newMessages)

    // Save to server
    try {
      await chat.saveHistory(projectId, newMessages)
    } catch (err) {
      console.error('Failed to save chat history after edit:', err)
    }
  }, [chatMessages, projectId])

  // Re-run last user message (delete responses and re-send)
  const handleRerunMessage = useCallback(async (index: number) => {
    const msg = chatMessages[index]
    if (!msg || msg.role !== 'user') return

    // Keep messages up to but not including this user message
    const newMessages = chatMessages.slice(0, index)
    setChatMessages(newMessages)

    // Save trimmed history
    try {
      await chat.saveHistory(projectId, newMessages)
    } catch (err) {
      console.error('Failed to save trimmed history:', err)
    }

    // Re-send the message
    handleSendMessage(msg.content)
  }, [chatMessages, projectId, handleSendMessage])

  // Clear all chat history
  const handleClearHistory = useCallback(() => {
    if (chatMessages.length === 0) return

    setConfirmPopup({
      title: 'Clear Chat History',
      message: `Are you sure you want to clear all ${chatMessages.length} message${chatMessages.length > 1 ? 's' : ''}?\n\nThis action cannot be undone.`,
      confirmText: 'Clear All',
      confirmColor: 'red',
      onConfirm: async () => {
        try {
          await chat.clearHistory(projectId)
          setChatMessages([])
          setConfirmPopup(null)
        } catch (err) {
          console.error('Failed to clear chat history:', err)
          setConfirmPopup(null)
          setErrorPopup('Failed to clear chat history. Please try again.')
        }
      },
    })
  }, [projectId, chatMessages.length])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
          <span className="text-blue-300 text-sm">Loading notebook...</span>
        </div>
      </div>
    )
  }

  return (
    <ThemeProvider>
    <div
      className="h-screen flex flex-col"
      style={{
        backgroundColor: 'var(--nb-bg-primary)',
        color: 'var(--nb-text-primary)',
      }}
    >
      {/* Header - Fixed dark styling, not affected by theme */}
      <header className="flex items-center justify-between px-4 py-2 backdrop-blur-xl bg-slate-900/95 border-b border-white/10">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/dashboard')}
            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-white">{currentProject?.name || 'Notebook'}</h1>
          </div>
          {isDirty && <span className="text-amber-400 text-sm flex items-center gap-1"><span className="w-1.5 h-1.5 bg-amber-400 rounded-full" /> Unsaved</span>}
        </div>
        <div className="flex items-center gap-3">
          {/* Playground controls */}
          {playground?.status === 'running' ? (
            <>
              <span className="flex items-center gap-2 text-sm text-emerald-400 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse shadow-lg shadow-emerald-400/50" />
                Running
              </span>
              <button
                onClick={handleStopPlayground}
                disabled={playgroundLoading}
                className="px-4 py-1.5 text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg transition-all disabled:opacity-50"
              >
                Stop
              </button>
            </>
          ) : playground?.status === 'starting' ? (
            <span className="flex items-center gap-2 text-sm text-amber-400 px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg">
              <div className="w-3 h-3 border-2 border-amber-400/30 border-t-amber-400 rounded-full animate-spin" />
              Starting...
            </span>
          ) : (
            <button
              onClick={handleStartPlayground}
              disabled={playgroundLoading}
              className="px-4 py-1.5 text-sm bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-lg transition-all disabled:opacity-50 flex items-center gap-2"
            >
              {playgroundLoading ? (
                <>
                  <div className="w-3 h-3 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Start Playground
                </>
              )}
            </button>
          )}
        </div>
      </header>

      {/* Toolbar */}
      <NotebookToolbar
        onAddCode={() => handleAddCell('code')}
        onAddMarkdown={() => handleAddCell('markdown')}
        onAddAI={() => handleAddCell('ai')}
        onRunAll={handleRunAll}
        onClearOutputs={handleClearOutputs}
        onDeleteAllCells={handleDeleteAllCells}
        onSave={handleSave}
        onExport={handleExport}
        isExporting={isExporting}
        totalCells={cells.length}
        isDirty={isDirty}
        isSaving={isSaving}
        kernelStatus={kernel.status}
        onRestartKernel={handleRestartKernel}
        showChat={showChat}
        onToggleChat={() => setShowChat(!showChat)}
        onOpenLogs={handleOpenLogs}
        onOpenTerminal={() => window.open(`/terminal/${projectId}`, '_blank')}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Notebook panel wrapper */}
        <div className="flex-1 relative" style={{ backgroundColor: 'var(--nb-bg-primary)' }}>
          {/* Notebook scroll area */}
          <div
            className="absolute inset-0 overflow-y-auto p-4"
            onClick={(e) => {
              // Exit edit mode when clicking on empty space (not on a cell)
              const target = e.target as HTMLElement
              // Check if click is on a cell or inside a cell
              const isInsideCell = target.closest('.cell-wrapper') !== null
              const isInsideToolbar = target.closest('[class*="NotebookToolbar"]') !== null
              if (!isInsideCell && !isInsideToolbar && isEditMode) {
                setIsEditMode(false)
              }
            }}
          >
          <div
            ref={notebookContainerRef}
            className={`mx-auto space-y-4 relative ${isResizing ? 'select-none' : ''}`}
            style={{
              width: notebookWidth ? `${notebookWidth}px` : undefined,
              maxWidth: notebookWidth ? undefined : '72rem', // max-w-6xl equivalent
            }}
          >
            {/* Left resize handle */}
            <div
              className="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize group hover:bg-blue-500/30 transition-colors -ml-2"
              onMouseDown={(e) => handleResizeStart(e, 'left')}
              title="Drag to resize notebook width"
            >
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-16 bg-gray-500/30 rounded group-hover:bg-blue-500 transition-colors" />
            </div>
            {/* Right resize handle */}
            <div
              className="absolute right-0 top-0 bottom-0 w-1 cursor-ew-resize group hover:bg-blue-500/30 transition-colors -mr-2"
              onMouseDown={(e) => handleResizeStart(e, 'right')}
              title="Drag to resize notebook width"
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-16 bg-gray-500/30 rounded group-hover:bg-blue-500 transition-colors" />
            </div>
            {/* Width indicator and reset button - shown when custom width is set */}
            {notebookWidth && (
              <div className="absolute -top-6 right-0 flex items-center gap-2 text-xs" style={{ color: 'var(--nb-text-muted)' }}>
                <span>{notebookWidth}px</span>
                <button
                  onClick={resetNotebookWidth}
                  className="hover:text-white transition-colors"
                  title="Reset to default width"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>
            )}
            {cells.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h4 className="text-lg font-medium text-white mb-2">Empty notebook</h4>
                <p className="text-gray-400 mb-6">Add your first cell to get started</p>
                <div className="flex justify-center gap-3">
                  <button
                    onClick={() => handleAddCell('code')}
                    className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white rounded-xl font-medium shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Code Cell
                  </button>
                  <button
                    onClick={() => handleAddCell('markdown')}
                    className="px-5 py-2.5 bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 rounded-xl font-medium transition-all flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Markdown Cell
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Insert button at the very top */}
                <CellInsertButtons
                  onInsertCode={() => handleInsertCellAt('code', 0)}
                  onInsertMarkdown={() => handleInsertCellAt('markdown', 0)}
                  onInsertAI={() => handleInsertCellAt('ai', 0)}
                />

                {cells.map((cell, index) => (
                  <div key={cell.id}>
                    {cell.type === 'ai' ? (
                      <AICell
                        cell={cell}
                        index={index}
                        isSelected={selectedCellId === cell.id}
                        onSelect={() => {
                          if (selectedCellId !== cell.id) {
                            setIsEditMode(false)
                          }
                          setSelectedCellId(cell.id)
                        }}
                        onDelete={() => handleDeleteCell(cell.id)}
                        onMoveUp={() => moveCell(cell.id, 'up')}
                        onMoveDown={() => moveCell(cell.id, 'down')}
                        onUpdate={(updates) => updateCell(cell.id, updates)}
                        onRunAICell={handleRunAICell}
                        onInsertCodeCells={handleInsertCodeFromAICell}
                        onScrollToCell={handleScrollToCell}
                      />
                    ) : (
                      <Cell
                        cell={cell}
                        index={index}
                        isSelected={selectedCellId === cell.id}
                        isRunning={kernel.runningCellId === cell.id}
                        isAnyRunning={kernel.runningCellId !== null}
                        isEditMode={selectedCellId === cell.id && isEditMode}
                        onSelect={() => {
                          // Clicking on cell header area - just select, don't enter edit mode
                          // (Clicking on textarea will trigger onEnterEditMode separately)
                          if (selectedCellId !== cell.id) {
                            // Switching to a different cell - exit edit mode
                            // For markdown cells that were being edited, they will auto-render
                            setIsEditMode(false)
                          }
                          setSelectedCellId(cell.id)
                        }}
                        onRun={() => handleRunCell(cell.id)}
                        onRunAndAdvance={() => {
                          handleRunCell(cell.id)
                          // Move to next cell after running
                          if (index < cells.length - 1) {
                            navigateToCell(index + 1)
                          }
                        }}
                        onStop={() => kernel.interrupt()}
                        onDelete={() => handleDeleteCell(cell.id)}
                        onMoveUp={() => moveCell(cell.id, 'up')}
                        onMoveDown={() => moveCell(cell.id, 'down')}
                        onUpdate={(updates) => updateCell(cell.id, updates)}
                        onEnterEditMode={() => {
                          // Enter edit mode on this cell
                          setSelectedCellId(cell.id)
                          setIsEditMode(true)
                        }}
                        onExitEditMode={(moveToNext, shiftEnterHandled) => exitEditMode(moveToNext, shiftEnterHandled)}
                      />
                    )}
                    {/* Insert button after each cell */}
                    <CellInsertButtons
                      onInsertCode={() => handleInsertCellAt('code', index + 1)}
                      onInsertMarkdown={() => handleInsertCellAt('markdown', index + 1)}
                      onInsertAI={() => handleInsertCellAt('ai', index + 1)}
                    />
                  </div>
                ))}
              </>
            )}

            {/* Add cell button at bottom (fallback for empty state, though we now have insert buttons) */}
            {cells.length > 0 && (
              <div className="flex justify-center gap-2 py-2">
                <span className="text-xs text-gray-500">
                  Hover between cells to insert
                </span>
              </div>
            )}

          </div>
          </div>
        </div>

        {/* Chat panel - 30% width */}
        {showChat && (
          <div className="w-[30%] min-w-[320px] flex-shrink-0">
            <ChatPanel
              messages={chatMessages}
              isLoading={chatLoading}
              pendingTools={pendingTools}
              onSendMessage={handleSendMessage}
              onApproveTools={handleApproveTools}
              onRejectTools={handleRejectTools}
              llmProvider={llmProvider}
              onProviderChange={handleProviderChange}
              toolMode={toolMode}
              onToolModeChange={setToolMode}
              contextFormat={contextFormat}
              onContextFormatChange={setContextFormat}
              onDeleteMessage={handleDeleteMessage}
              onEditMessage={handleEditMessage}
              onRerunMessage={handleRerunMessage}
              onClearHistory={handleClearHistory}
              onSummarize={handleSummarize}
              isSummarizing={isSummarizing}
              onScrollToCell={handleScrollToCell}
              onPanelClick={() => {
                if (isEditMode) {
                  setIsEditMode(false)
                }
              }}
            />
          </div>
        )}
      </div>

      {/* Error Popup Modal */}
      {errorPopup && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div
            className="rounded-lg p-6 max-w-md mx-4 shadow-xl"
            style={{
              backgroundColor: 'var(--nb-bg-cell)',
              border: '1px solid var(--nb-accent-error)',
            }}
          >
            <div className="flex items-start gap-3">
              <div
                className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                style={{ backgroundColor: 'var(--nb-accent-error)', color: '#fff' }}
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--nb-text-primary)' }}>
                  {errorPopup.toLowerCase().includes('playground') ? 'Playground Not Available' : 'Error'}
                </h3>
                <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--nb-text-secondary)' }}>
                  {errorPopup}
                </p>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setErrorPopup(null)}
                className="px-4 py-2 text-sm rounded-md bg-gray-600 hover:bg-gray-500 text-white"
              >
                Dismiss
              </button>
              {playground?.status !== 'running' && errorPopup.toLowerCase().includes('playground') && (
                <button
                  onClick={() => {
                    setErrorPopup(null)
                    handleStartPlayground()
                  }}
                  className="px-4 py-2 text-sm rounded-md bg-green-600 hover:bg-green-500 text-white"
                >
                  Start Playground
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Popup Modal */}
      {confirmPopup && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div
            className="rounded-lg p-6 max-w-md mx-4 shadow-xl"
            style={{
              backgroundColor: 'var(--nb-bg-cell)',
              border: `1px solid ${confirmPopup.confirmColor === 'red' ? 'var(--nb-accent-error)' : 'var(--nb-border-default)'}`,
            }}
          >
            <div className="flex items-start gap-3">
              <div
                className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                style={{
                  backgroundColor: confirmPopup.confirmColor === 'red' ? 'var(--nb-accent-error)' : 'var(--nb-accent-code)',
                  color: '#fff'
                }}
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--nb-text-primary)' }}>
                  {confirmPopup.title}
                </h3>
                <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--nb-text-secondary)' }}>
                  {confirmPopup.message}
                </p>
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmPopup(null)}
                className="px-4 py-2 text-sm rounded-md bg-gray-600 hover:bg-gray-500 text-white"
              >
                Cancel
              </button>
              <button
                onClick={confirmPopup.onConfirm}
                className={`px-4 py-2 text-sm rounded-md text-white ${
                  confirmPopup.confirmColor === 'red'
                    ? 'bg-red-600 hover:bg-red-500'
                    : 'bg-blue-600 hover:bg-blue-500'
                }`}
              >
                {confirmPopup.confirmText || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </ThemeProvider>
  )
}
