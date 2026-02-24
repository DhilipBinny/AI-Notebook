'use client'

import { useEffect, useState, useCallback, useRef, use } from 'react'
import { useRouter } from 'next/navigation'
import { auth, projects, playgrounds, chat, notebooks, files, apiKeys } from '@/lib/api'
import { useAuthStore, useProjectsStore, useNotebookStore } from '@/lib/store'
import Cell from '@/components/notebook/Cell'
import AICell from '@/components/notebook/AICell'
import NotebookToolbar from '@/components/notebook/NotebookToolbar'
import CellInsertButtons from '@/components/notebook/CellInsertButtons'
import ChatPanel from '@/components/chat/ChatPanel'
import FilePanel from '@/components/files/FilePanel'
import AppHeader from '@/components/AppHeader'
import { useKernel } from '@/hooks/useKernel'
import { useNotebookUpdates } from '@/hooks/useNotebookUpdates'
import { ThemeProvider } from '@/contexts/ThemeContext'
import type { Cell as CellType, CellOutput, Playground, ChatMessage, ImageInput } from '@/types'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  ChevronLeft,
  BookOpen,
  RefreshCw,
  Plus,
  AlertTriangle,
  LogOut,
} from 'lucide-react'

// Configure marked for PDF export
marked.setOptions({
  gfm: true,
  breaks: true,
})

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
  const { cells, setCells, addCell, updateCell, updateCellAiData, updateCellFromServer, deleteCell, deleteCellFromServer, moveCell, isDirty, setDirty } = useNotebookStore()

  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isExportingPDF, setIsExportingPDF] = useState(false)
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
  const [availableProviders, setAvailableProviders] = useState<{ provider: string; display_name: string }[]>([])
  const [toolMode, setToolMode] = useState<'auto' | 'manual' | 'ai_decide'>('auto')
  const [contextFormat, setContextFormat] = useState<'xml' | 'json' | 'plain'>('xml')
  const [showChat, setShowChat] = useState(true)
  const [showFiles, setShowFiles] = useState(false)  // File panel visibility
  const [chatStreamStatus, setChatStreamStatus] = useState<string | null>(null)  // Real-time SSE status
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

  // Notebook updates hook - receive real-time cell updates from LLM tools via Master API
  // Uses server-specific update functions that don't overwrite local dirty cells
  const notebookUpdates = useNotebookUpdates(projectId, {
    onCellCreated: useCallback((cellId: string, cellIndex: number, content: string, cellType: string) => {
      console.log(`[NotebookPage] Cell created from server: ${cellId} at index ${cellIndex}`)
      // Check if cell already exists (avoid duplicates)
      const existingCell = cells.find(c => c.id === cellId)
      if (existingCell) {
        console.log(`[NotebookPage] Cell ${cellId} already exists, skipping creation`)
        return
      }
      // Create a new cell and insert it at the specified index
      // Note: This uses addCell which marks as dirty, but since this is from server,
      // we immediately mark the cell as clean after adding
      const newCell: CellType = {
        id: cellId,
        type: cellType as 'code' | 'markdown' | 'raw' | 'ai',
        source: content,
        outputs: [],
        metadata: { cell_id: cellId },
      }
      // Use setCells to add without marking dirty (server is source of truth)
      const newCells = [...cells]
      const insertIndex = Math.min(cellIndex, newCells.length)
      newCells.splice(insertIndex, 0, newCell)
      setCells(newCells)
    }, [cells, setCells]),

    onCellUpdated: useCallback((cellId: string, cellIndex: number, content: string, cellType?: string) => {
      console.log(`[NotebookPage] Cell updated from server: ${cellId}`)
      // Check if cell exists
      const existingCell = cells.find(c => c.id === cellId)
      if (!existingCell) {
        console.log(`[NotebookPage] Cell ${cellId} not found, skipping update`)
        return
      }
      // Use updateCellFromServer which respects local dirty state
      updateCellFromServer(cellId, {
        source: content,
        ...(cellType && { type: cellType as 'code' | 'markdown' | 'raw' | 'ai' }),
      })
    }, [cells, updateCellFromServer]),

    onCellDeleted: useCallback((cellId: string, cellIndex: number) => {
      console.log(`[NotebookPage] Cell deleted from server: ${cellId}`)
      // Check if cell exists
      const existingCell = cells.find(c => c.id === cellId)
      if (!existingCell) {
        console.log(`[NotebookPage] Cell ${cellId} not found, skipping delete`)
        return
      }
      // Use deleteCellFromServer which doesn't mark notebook as dirty
      deleteCellFromServer(cellId)
    }, [cells, deleteCellFromServer]),

    onCellExecuted: useCallback((cellId: string, cellIndex: number, outputs: CellOutput[], executionCount?: number) => {
      console.log(`[NotebookPage] Cell executed from server: ${cellId}, outputs:`, outputs.length)
      // Check if cell exists
      const existingCell = cells.find(c => c.id === cellId)
      if (!existingCell) {
        console.log(`[NotebookPage] Cell ${cellId} not found, skipping execution update`)
        return
      }
      // Use updateCellFromServer - outputs don't conflict with local source edits
      updateCellFromServer(cellId, {
        outputs,
        execution_count: executionCount,
      })
    }, [cells, updateCellFromServer]),
  })

  // Core save function - shared by handleSave (manual) and saveNotebook (auto)
  const saveNotebookCore = useCallback(async (): Promise<boolean> => {
    if (!currentProject) return false

    // Build cells in Jupyter .ipynb standard format
    const cellsToSave = cells.map((cell) => ({
      cell_type: cell.type,
      source: cell.source,
      outputs: (cell.outputs || []) as unknown as Record<string, unknown>[],
      execution_count: cell.execution_count,
      metadata: { ...cell.metadata, cell_id: cell.id } as Record<string, unknown>,
      ai_data: cell.type === 'ai' && cell.ai_data ? cell.ai_data : undefined,
    }))

    await notebooks.save(projectId, cellsToSave as Parameters<typeof notebooks.save>[1])
    setDirty(false)
    return true
  }, [currentProject, projectId, cells, setDirty])

  // Auto-save helper (for chat, AI cell, etc.) - silent, returns success/failure
  const saveNotebook = useCallback(async (): Promise<boolean> => {
    try {
      const success = await saveNotebookCore()
      if (success) {
        console.log('Notebook auto-saved')
      }
      return success
    } catch (err) {
      console.error('Failed to auto-save notebook:', err)
      return false
    }
  }, [saveNotebookCore])

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

        // Get existing playground status (user-scoped)
        const pg = await playgrounds.getStatus()
        setPlayground(pg)

        // If playground not running, still load notebook but show error popup
        if (!pg || pg.status !== 'running') {
          console.warn('Playground not running, showing start prompt')
          // We'll show the error popup after loading the notebook
          // This allows user to view/edit notebook and start playground from here
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
              images: m.images,  // Include images from chat history
              steps: m.steps,   // Include steps from chat history
            })))
            console.log(`Loaded ${historyData.messages.length} messages from chat history`)
          }
        } catch {
          // No chat history yet
          console.log('No chat history found')
        }

        // Load available providers and set default
        try {
          const providers = await apiKeys.getProviders()
          const available = providers.filter(p => p.has_key)
          if (available.length > 0) {
            setAvailableProviders(available.map(p => ({ provider: p.provider, display_name: p.display_name })))
            // Use the provider marked as default, otherwise fall back to first available
            const defaultProvider = available.find(p => p.is_default)
            setLlmProvider(defaultProvider ? defaultProvider.provider : available[0].provider)
          }
        } catch {
          // Fallback to defaults
        }

        // Show playground not running popup after everything is loaded
        if (!pg || pg.status !== 'running') {
          setErrorPopup('Playground is not running. Start the playground to execute code and use AI features.')
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
    playgrounds.updateActivity().catch((err) => {
      console.warn('Failed to send activity heartbeat:', err)
    })

    // Set up interval for heartbeat every 2 minutes
    const heartbeatInterval = setInterval(() => {
      // Check if tab is visible before sending heartbeat
      if (document.visibilityState === 'visible') {
        playgrounds.updateActivity().catch((err) => {
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
      await playgrounds.stop()
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

  // Run AI cell - send prompt to LLM with notebook context (streaming version)
  const handleRunAICell = useCallback(async (
    cellId: string,
    prompt: string,
    images?: { data: string; mime_type: string; filename?: string }[]
  ) => {
    if (!playground || playground.status !== 'running') {
      updateCell(cellId, {
        ai_data: {
          user_prompt: prompt,
          llm_response: '',
          status: 'error',
          error: 'Playground is not running. Start the playground first.',
          images: images,
        },
      })
      return
    }

    // Save notebook first to ensure context is up to date
    await saveNotebook()

    // Get all cell IDs for context (excluding the AI cell itself, but including other AI cells)
    // Other AI cells' user_ask_ai and ai_response will be included in context by the backend
    const contextCellIds = cells
      .filter(c => c.id !== cellId)
      .map(c => c.id)

    // Get AI cell's position for positional awareness
    const aiCellIndex = cells.findIndex(c => c.id === cellId)

    // Initialize streaming state - clear previous response, steps, thinking, and errors
    updateCell(cellId, {
      ai_data: {
        user_prompt: prompt,
        llm_response: '',
        status: 'running',
        images: images,
        steps: undefined,  // Clear previous tool steps
        thinking: undefined,  // Clear previous thinking
        error: undefined,  // Clear previous error
        streamState: {
          thinkingMessage: 'Starting AI analysis...',
          thinkingSteps: [],
          streamingSteps: [],
        },
      },
    })

    // Use unified API (always SSE, real-time progress depends on playground config)
    chat.runAICell(
      projectId,
      prompt,
      contextCellIds,
      llmProvider,
      cellId,
      aiCellIndex,
      contextFormat,
      images,
      // onEvent - handle streaming progress events
      // Uses updateCellAiData with functional updater to get FRESH cell state
      // This avoids stale closure issues where previous event's data gets overwritten
      (event) => {
        if (event.type === 'thinking') {
          // Status message (e.g., "Iteration 1...")
          const message = (event.data.message as string) || 'Thinking...'
          const iterMatch = message.match(/Iteration (\d+)/)

          updateCellAiData(cellId, (cell) => {
            const currentStreamState = cell.ai_data?.streamState || { streamingSteps: [], thinkingSteps: [] }
            const iteration = iterMatch ? parseInt(iterMatch[1]) : (currentStreamState.currentIteration || 1)
            return {
              user_prompt: prompt,
              llm_response: '',
              status: 'running',
              images: images,
              streamState: {
                ...currentStreamState,
                thinkingMessage: message,
                currentIteration: iteration,
              },
            }
          })
        } else if (event.type === 'llm_thinking') {
          // LLM's internal reasoning/thinking process (from extended thinking)
          const thinkingContent = (event.data.content as string) || ''
          const iteration = (event.data.iteration as number) || 1
          console.log('[AICell] Received llm_thinking event, iteration:', iteration, 'content length:', thinkingContent.length)

          const newThinkingStep = {
            iteration,
            content: thinkingContent,
            timestamp: new Date().toISOString(),
          }

          updateCellAiData(cellId, (cell) => {
            const currentStreamState = cell.ai_data?.streamState || { streamingSteps: [], thinkingSteps: [] }
            return {
              user_prompt: prompt,
              llm_response: '',
              status: 'running',
              images: images,
              streamState: {
                ...currentStreamState,
                thinkingMessage: `Reasoning (Iteration ${iteration})...`,
                currentIteration: iteration,
                thinkingSteps: [...(currentStreamState.thinkingSteps || []), newThinkingStep],
              },
            }
          })
        } else if (event.type === 'tool_call') {
          const newStep = {
            type: 'tool_call' as const,
            name: (event.data.name as string) || '',
            content: JSON.stringify(event.data.args || {}),
          }

          updateCellAiData(cellId, (cell) => {
            const currentStreamState = cell.ai_data?.streamState || { streamingSteps: [], thinkingSteps: [] }
            return {
              user_prompt: prompt,
              llm_response: '',
              status: 'running',
              images: images,
              streamState: {
                ...currentStreamState,
                thinkingMessage: `Calling ${event.data.name}...`,
                currentToolCall: { name: event.data.name as string, args: event.data.args as Record<string, unknown> },
                streamingSteps: [...currentStreamState.streamingSteps, newStep],
              },
            }
          })
        } else if (event.type === 'tool_result') {
          const newStep = {
            type: 'tool_result' as const,
            name: (event.data.name as string) || '',
            content: ((event.data.result as string) || '').slice(0, 500),
          }

          updateCellAiData(cellId, (cell) => {
            const currentStreamState = cell.ai_data?.streamState || { streamingSteps: [], thinkingSteps: [] }
            return {
              user_prompt: prompt,
              llm_response: '',
              status: 'running',
              images: images,
              streamState: {
                ...currentStreamState,
                thinkingMessage: 'Processing result...',
                currentToolCall: undefined,
                streamingSteps: [...currentStreamState.streamingSteps, newStep],
              },
            }
          })
        }
      },
      // onDone - handle final response
      async (result) => {
        // Use updateCellAiData to get FRESH thinkingSteps from current cell state
        // This avoids stale closure issues
        updateCellAiData(cellId, (cell) => {
          const thinkingSteps = cell.ai_data?.streamState?.thinkingSteps || []

          // Also check if thinking came in the result (backup method)
          let finalThinking = thinkingSteps
          if (thinkingSteps.length === 0 && result.thinking) {
            // Thinking was included in the done event, create a step from it
            finalThinking = [{
              iteration: 1,
              content: result.thinking as string,
              timestamp: new Date().toISOString(),
            }]
            console.log('[AICell] Using thinking from done event:', (result.thinking as string).length, 'chars')
          } else if (thinkingSteps.length > 0) {
            console.log('[AICell] Using accumulated thinkingSteps:', thinkingSteps.length, 'steps')
          }

          return {
            user_prompt: prompt,
            llm_response: result.response,
            status: result.success ? 'completed' : 'error',
            model: result.model,
            error: result.cancelled ? 'Cancelled by user' : undefined,
            timestamp: new Date().toISOString(),
            images: images,
            steps: result.steps,
            thinking: finalThinking.length > 0 ? finalThinking : undefined, // Persist thinking to ipynb
            streamState: undefined, // Clear streaming state
          }
        })

        // Auto-save after completion
        await saveNotebook()
      },
      // onError - handle errors
      (error) => {
        updateCellAiData(cellId, () => ({
          user_prompt: prompt,
          llm_response: '',
          status: 'error',
          error: error,
          images: images,
          streamState: undefined,
        }))
      }
    )
  }, [playground, projectId, llmProvider, contextFormat, updateCellAiData, saveNotebook])

  // Cancel running AI cell
  const handleCancelAICell = useCallback(async (cellId: string) => {
    // Send cancel to backend - it will interrupt the running operation
    try {
      const response = await chat.cancelAICell(projectId)
      console.log('Cancel response:', response)
    } catch (err) {
      console.error('Failed to cancel AI cell:', err)
    }
  }, [projectId])

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
    // Trim and clean the cellId to avoid whitespace issues
    const cleanedCellId = cellId.trim()
    console.log('[Page] handleScrollToCell called with cellId:', JSON.stringify(cleanedCellId))

    // The cell ID format is "cell-xxx" (e.g., "cell-1764683711390-swbvvzf58")
    // This matches both the cell.id property and the DOM element ID
    const elementId = cleanedCellId
    console.log('[Page] Looking for element with ID:', JSON.stringify(elementId))

    const cellElement = document.getElementById(elementId)
    console.log('[Page] Found element:', !!cellElement)

    if (cellElement) {
      cellElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Select the cell (use the full ID including 'cell-' prefix)
      setSelectedCellId(cleanedCellId)
      // Add a brief highlight effect
      cellElement.style.transition = 'box-shadow 0.3s ease'
      cellElement.style.boxShadow = '0 0 20px rgba(168, 85, 247, 0.6)'
      setTimeout(() => {
        cellElement.style.boxShadow = ''
      }, 1500)
    } else {
      // Debug: Check what IDs actually exist in DOM
      const allCellElements = document.querySelectorAll('[id^="cell-"]')
      const domIds = Array.from(allCellElements).map(el => el.id)
      console.log('[Page] Element not found! DOM cell IDs:', domIds.slice(0, 10), '...')
      console.log('[Page] Cell objects IDs:', cells.slice(0, 10).map(c => c.id))
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

      // Scroll cell into view (cell.id already has 'cell-' prefix)
      setTimeout(() => {
        const cellElement = document.getElementById(cell.id)
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


  // Manual save handler - shows loading state and error popup on failure
  const handleSave = useCallback(async () => {
    if (!currentProject) return
    setIsSaving(true)
    try {
      await saveNotebookCore()
      // Also persist chat history to S3
      if (chatMessages.length > 0) {
        await chat.saveHistory(projectId, chatMessages)
      }
      console.log('Notebook and chat saved')
    } catch (err) {
      console.error('Failed to save:', err)
      setErrorPopup('Failed to save notebook. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }, [currentProject, saveNotebookCore, chatMessages, projectId])

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

  const handleExportPDF = useCallback(async () => {
    if (!currentProject || cells.length === 0) {
      setErrorPopup('No cells to export. Add some content first.')
      return
    }
    setIsExportingPDF(true)
    try {
      // First save the notebook to ensure we export the latest version
      if (isDirty) {
        await handleSave()
      }

      // Helper function to escape HTML
      function escapeHtml(text: string): string {
        const div = document.createElement('div')
        div.textContent = text
        return div.innerHTML
      }

      // Helper function to strip ANSI escape codes
      function stripAnsi(text: string): string {
        // eslint-disable-next-line no-control-regex
        return text.replace(/\x1b\[[0-9;]*m/g, '')
      }

      // Helper function to render markdown to HTML
      function renderMarkdown(text: string): string {
        try {
          const html = marked.parse(text) as string
          return DOMPurify.sanitize(html)
        } catch {
          return escapeHtml(text)
        }
      }

      // Helper function to extract text output from cell outputs
      function getOutputContent(outputs: CellOutput[]): { text: string; html: string } {
        let textOutput = ''
        let htmlOutput = ''

        for (const output of outputs) {
          if (output.output_type === 'stream' || output.output_type === 'execute_result') {
            // Text output
            if (output.text) {
              const text = Array.isArray(output.text) ? output.text.join('') : output.text
              textOutput += stripAnsi(text)
            }
            // Rich data output
            if (output.data) {
              // Prefer HTML, then markdown, then plain text
              if (output.data['text/html']) {
                const html = Array.isArray(output.data['text/html'])
                  ? output.data['text/html'].join('')
                  : output.data['text/html'] as string
                htmlOutput += DOMPurify.sanitize(html)
              } else if (output.data['text/markdown']) {
                const md = Array.isArray(output.data['text/markdown'])
                  ? output.data['text/markdown'].join('')
                  : output.data['text/markdown'] as string
                htmlOutput += renderMarkdown(md)
              } else if (output.data['image/png']) {
                const imgData = output.data['image/png'] as string
                htmlOutput += `<img src="data:image/png;base64,${imgData}" style="max-width: 100%;" />`
              } else if (output.data['image/svg+xml']) {
                const svg = Array.isArray(output.data['image/svg+xml'])
                  ? output.data['image/svg+xml'].join('')
                  : output.data['image/svg+xml'] as string
                htmlOutput += DOMPurify.sanitize(svg)
              } else if (output.data['text/plain']) {
                const plain = Array.isArray(output.data['text/plain'])
                  ? output.data['text/plain'].join('')
                  : output.data['text/plain'] as string
                textOutput += stripAnsi(plain)
              }
            }
          } else if (output.output_type === 'display_data') {
            // Display data (images, HTML, etc.)
            if (output.data) {
              if (output.data['text/html']) {
                const html = Array.isArray(output.data['text/html'])
                  ? output.data['text/html'].join('')
                  : output.data['text/html'] as string
                htmlOutput += DOMPurify.sanitize(html)
              } else if (output.data['image/png']) {
                const imgData = output.data['image/png'] as string
                htmlOutput += `<img src="data:image/png;base64,${imgData}" style="max-width: 100%;" />`
              } else if (output.data['image/svg+xml']) {
                const svg = Array.isArray(output.data['image/svg+xml'])
                  ? output.data['image/svg+xml'].join('')
                  : output.data['image/svg+xml'] as string
                htmlOutput += DOMPurify.sanitize(svg)
              } else if (output.data['text/markdown']) {
                const md = Array.isArray(output.data['text/markdown'])
                  ? output.data['text/markdown'].join('')
                  : output.data['text/markdown'] as string
                htmlOutput += renderMarkdown(md)
              }
            }
          } else if (output.output_type === 'error') {
            // Error output
            if (output.traceback) {
              textOutput += stripAnsi(output.traceback.join('\n'))
            } else if (output.ename && output.evalue) {
              textOutput += `${output.ename}: ${output.evalue}`
            }
          }
        }

        return { text: textOutput.trim(), html: htmlOutput }
      }

      // Build HTML content for PDF
      let htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>${currentProject.name}</title>
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
              max-width: 800px;
              margin: 0 auto;
              padding: 40px 20px;
              line-height: 1.6;
              color: #1a1a1a;
            }
            h1.title { border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 30px; }
            .cell { margin-bottom: 24px; page-break-inside: avoid; }
            .cell-header {
              font-size: 11px;
              color: #6b7280;
              margin-bottom: 8px;
              padding: 4px 8px;
              background: #f3f4f6;
              border-radius: 4px;
              display: inline-block;
            }
            .code-cell .cell-header { background: #dbeafe; color: #1e40af; }
            .markdown-cell .cell-header { background: #f3e8ff; color: #7c3aed; }
            .ai-cell .cell-header { background: #fce7f3; color: #be185d; }
            pre {
              background: #1e1e1e;
              color: #d4d4d4;
              padding: 16px;
              border-radius: 8px;
              overflow-x: auto;
              font-size: 13px;
              font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
              white-space: pre-wrap;
              word-wrap: break-word;
            }
            .output {
              background: #fafafa;
              border: 1px solid #e5e7eb;
              padding: 12px 16px;
              border-radius: 6px;
              margin-top: 8px;
              font-family: monospace;
              font-size: 13px;
              white-space: pre-wrap;
              word-wrap: break-word;
            }
            .output-html {
              margin-top: 8px;
            }
            .output-html img { max-width: 100%; height: auto; }
            .output-html table { border-collapse: collapse; margin: 8px 0; }
            .output-html table th, .output-html table td { border: 1px solid #e5e7eb; padding: 8px; }
            .output-label { font-size: 10px; color: #9ca3af; margin-bottom: 4px; }
            .markdown-content { }
            .markdown-content h1 { font-size: 1.8em; margin: 0.5em 0; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.3em; }
            .markdown-content h2 { font-size: 1.5em; margin: 0.5em 0; }
            .markdown-content h3 { font-size: 1.25em; margin: 0.5em 0; }
            .markdown-content ul, .markdown-content ol { padding-left: 2em; margin: 0.5em 0; }
            .markdown-content li { margin: 0.25em 0; }
            .markdown-content code { background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
            .markdown-content pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; }
            .markdown-content pre code { background: none; padding: 0; }
            .markdown-content blockquote { border-left: 4px solid #e5e7eb; margin: 0.5em 0; padding-left: 1em; color: #6b7280; }
            .ai-prompt { background: #fef3c7; padding: 12px; border-radius: 6px; margin-bottom: 8px; }
            .ai-response { background: #ecfdf5; padding: 12px; border-radius: 6px; }
            .ai-response h1, .ai-response h2, .ai-response h3 { margin-top: 0.5em; }
            .ai-response ul, .ai-response ol { padding-left: 2em; }
            .ai-response code { background: rgba(0,0,0,0.1); padding: 2px 6px; border-radius: 3px; }
            .ai-response pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; overflow-x: auto; }
            .ai-response pre code { background: none; padding: 0; }
            .thinking { background: #f3f4f6; padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #6b7280; margin-bottom: 8px; font-style: italic; }
            @media print {
              body { padding: 0; }
              .cell { page-break-inside: avoid; }
              pre { white-space: pre-wrap; word-wrap: break-word; }
            }
          </style>
        </head>
        <body>
          <h1 class="title">${escapeHtml(currentProject.name)}</h1>
      `

      cells.forEach((cell, index) => {
        const cellClass = cell.type === 'code' ? 'code-cell' : cell.type === 'markdown' ? 'markdown-cell' : 'ai-cell'
        const cellLabel = cell.type === 'code' ? 'Code' : cell.type === 'markdown' ? 'Markdown' : 'AI'

        htmlContent += `<div class="cell ${cellClass}">`
        htmlContent += `<div class="cell-header">[${index + 1}] ${cellLabel}</div>`

        if (cell.type === 'code') {
          htmlContent += `<pre>${escapeHtml(cell.source || '')}</pre>`
          if (cell.outputs && cell.outputs.length > 0) {
            const { text, html } = getOutputContent(cell.outputs)
            if (text) {
              htmlContent += `<div class="output"><div class="output-label">Output:</div>${escapeHtml(text)}</div>`
            }
            if (html) {
              htmlContent += `<div class="output-html">${html}</div>`
            }
          }
        } else if (cell.type === 'markdown') {
          // Render markdown to HTML
          htmlContent += `<div class="markdown-content">${renderMarkdown(cell.source || '')}</div>`
        } else if (cell.type === 'ai') {
          if (cell.ai_data?.user_prompt) {
            htmlContent += `<div class="ai-prompt"><strong>Question:</strong> ${escapeHtml(cell.ai_data.user_prompt)}</div>`
          }
          if (cell.ai_data?.thinking && cell.ai_data.thinking.length > 0) {
            const thinkingText = cell.ai_data.thinking.map(t => t.content).join('\n\n')
            htmlContent += `<div class="thinking">${escapeHtml(thinkingText)}</div>`
          }
          if (cell.ai_data?.llm_response) {
            // Render AI response as markdown (it usually contains markdown formatting)
            htmlContent += `<div class="ai-response"><strong>Answer:</strong> ${renderMarkdown(cell.ai_data.llm_response)}</div>`
          }
        }

        htmlContent += `</div>`
      })

      htmlContent += `
          <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 11px; color: #9ca3af;">
            Exported from AI Notebook on ${new Date().toLocaleDateString()}
          </div>
        </body>
        </html>
      `

      // Open print dialog
      const printWindow = window.open('', '_blank')
      if (printWindow) {
        printWindow.document.write(htmlContent)
        printWindow.document.close()
        printWindow.focus()
        // Small delay to ensure content is loaded
        setTimeout(() => {
          printWindow.print()
        }, 250)
      } else {
        setErrorPopup('Please allow popups to export PDF')
      }

    } catch (err) {
      console.error('Failed to export PDF:', err)
      setErrorPopup('Failed to export PDF. Please try again.')
    } finally {
      setIsExportingPDF(false)
    }
  }, [currentProject, cells, isDirty, handleSave])

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
        // Also skip Ctrl+A to allow select-all in textarea
        if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
          return  // Let the textarea handle select-all
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

          const selectedCell = cells.find(c => c.id === selectedCellId)
          if (!selectedCell) return

          // Handle AI cells differently - they don't use kernel
          if (selectedCell.type === 'ai') {
            // Don't run if AI cell is already running
            if (selectedCell.ai_data?.status === 'running') {
              console.log('[Page Global] Shift+Enter ignored - AI cell is already running')
              return
            }
            e.preventDefault()
            console.log('[Page Global] Shift+Enter in COMMAND mode - running AI cell')
            // Run AI cell with existing prompt
            const prompt = selectedCell.ai_data?.user_prompt || ''
            const images = selectedCell.ai_data?.images
            if (prompt.trim() || (images && images.length > 0)) {
              handleRunAICell(selectedCellId, prompt, images)
            }
            const currentIndex = getSelectedCellIndex()
            if (currentIndex < cells.length - 1) {
              navigateToCell(currentIndex + 1)
            }
            return
          }

          // For code cells, check if kernel is busy
          if (kernel.runningCellId !== null) {
            console.log('[Page Global] Shift+Enter ignored - a cell is already running')
            return
          }
          e.preventDefault()
          console.log('[Page Global] Shift+Enter in COMMAND mode - running code cell and moving to next')
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

        // X - Cut selected cell (but not Ctrl+X which is system cut)
        if ((e.key === 'x' || e.key === 'X') && !e.ctrlKey && !e.metaKey) {
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

        // C - Copy selected cell (but not Ctrl+C which is system copy)
        if ((e.key === 'c' || e.key === 'C') && !e.ctrlKey && !e.metaKey) {
          e.preventDefault()
          if (selectedCellId) {
            const cellToCopy = cells.find(c => c.id === selectedCellId)
            if (cellToCopy) {
              setClipboardCell({ ...cellToCopy })
            }
          }
          return
        }

        // V - Paste cell below (but not Ctrl+V which is system paste)
        if ((e.key === 'v' || e.key === 'V') && !e.ctrlKey && !e.metaKey) {
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

        // Z - Undo cell deletion (but not Ctrl+Z which is system undo)
        if ((e.key === 'z' || e.key === 'Z') && !e.ctrlKey && !e.metaKey) {
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
  }, [handleSave, isEditMode, getSelectedCellIndex, navigateToCell, cells, selectedCellId, enterEditMode, exitEditMode, handleRunCell, handleRunAICell, lastNavDirection, clipboardCell, deletedCells, addCell, deleteCell, updateCell, kernel.runningCellId])

  const handleStartKernel = useCallback(async () => {
    // Check if playground is running first
    if (!playground || playground.status !== 'running') {
      setErrorPopup('Playground is not running. Please start the playground first.')
      return
    }

    // Start kernel by calling the start endpoint
    const success = await kernel.start()
    if (!success) {
      setErrorPopup('Failed to start kernel. Try running a code cell instead.')
    }
  }, [kernel, playground])

  const handleStopKernel = useCallback(() => {
    setConfirmPopup({
      title: 'Stop Kernel',
      message: 'Are you sure you want to stop the kernel?\n\nThis will terminate the Python process. All variables and execution state will be lost.',
      confirmText: 'Stop Kernel',
      confirmColor: 'red',
      onConfirm: async () => {
        setConfirmPopup(null)
        const success = await kernel.stop()
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

  const handleRestartPlayground = useCallback(() => {
    setConfirmPopup({
      title: 'Restart Playground',
      message: 'Are you sure you want to restart the playground container?\n\nThis will stop the current container and start a new one. All kernel state, variables, and installed packages will be lost.',
      confirmText: 'Restart Playground',
      confirmColor: 'red',
      onConfirm: async () => {
        setConfirmPopup(null)
        setPlaygroundLoading(true)
        try {
          // Stop the playground
          await playgrounds.stop()
          // Wait a bit for cleanup
          await new Promise(resolve => setTimeout(resolve, 1000))
          // Start a new playground
          const result = await playgrounds.start(projectId)
          setPlayground(result.playground)
          // Clear execution counts
          cells.forEach((cell) => {
            if (cell.type === 'code') {
              updateCell(cell.id, { execution_count: undefined })
            }
          })
        } catch (err) {
          console.error('Failed to restart playground:', err)
          setErrorPopup('Failed to restart playground. Please try again.')
        } finally {
          setPlaygroundLoading(false)
        }
      },
    })
  }, [projectId, cells, updateCell])

  const handleCloseSession = useCallback(() => {
    setConfirmPopup({
      title: 'Close Session',
      message: 'Stop the playground and return to dashboard?\n\nAll kernel state, variables, and installed packages will be lost. Your notebook and chat history are saved.',
      confirmText: 'Close Session',
      confirmColor: 'red',
      onConfirm: async () => {
        setConfirmPopup(null)
        try {
          // Save notebook if dirty
          if (isDirty) {
            await saveNotebookCore()
          }
          // Save chat history
          if (chatMessages.length > 0) {
            await chat.saveHistory(projectId, chatMessages)
          }
          // Stop the playground
          await playgrounds.stop()
        } catch (err) {
          console.error('Failed to close session:', err)
        }
        router.push('/dashboard')
      },
    })
  }, [projectId, isDirty, saveNotebookCore, chatMessages, router])

  // Handle LLM provider change (local state only, not persisted)
  const handleProviderChange = useCallback((provider: string) => {
    setLlmProvider(provider)
  }, [])

  // Chat handlers
  const handleSendMessage = useCallback(async (message: string, images?: ImageInput[]) => {
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
    setChatStreamStatus('Analyzing...')
    setChatMessages((prev) => [...prev, { role: 'user', content: message, images }])

    // Auto-save notebook before sending message (ensure LLM sees latest edits via Master API)
    if (isDirty) {
      await saveNotebook()
    }

    // Send ALL cell IDs - backend loads content from S3 and creates tiered context
    const allCellIds = cells.map(c => c.id)

    // Use SSE for real-time streaming
    chat.sendMessageWithSSE(
      projectId,
      message,
      allCellIds,
      projectId,  // sessionId = projectId (same kernel session)
      toolMode,
      llmProvider,
      contextFormat,
      images,
      // onEvent: Handle real-time SSE events
      (event) => {
        switch (event.type) {
          case 'thinking':
            setChatStreamStatus((event.data as { message?: string }).message || 'Thinking...')
            break
          case 'tool_call':
            setChatStreamStatus(`Running tool: ${(event.data as { name?: string }).name || 'unknown'}...`)
            break
          case 'tool_result':
            setChatStreamStatus('Processing result...')
            break
          case 'pending_tools':
            setChatStreamStatus('Awaiting approval...')
            break
        }
      },
      // onDone: Handle completion
      (response) => {
        setChatStreamStatus(null)
        setChatLoading(false)

        if (response.success) {
          // Handle pending tools
          if (response.pending_tool_calls.length > 0) {
            setPendingTools(response.pending_tool_calls)
          }

          // Add assistant response and persist to S3
          if (response.response) {
            setChatMessages((prev) => {
              const updated: ChatMessage[] = [
                ...prev,
                {
                  role: 'assistant' as const,
                  content: response.response,
                  steps: response.steps,
                },
              ]
              chat.saveHistory(projectId, updated).catch(err => console.error('Failed to save chat history:', err))
              return updated
            })
          }

          // Only reload from S3 if WebSocket is not connected (fallback)
          if (notebookUpdates.status !== 'connected') {
            console.log('[Chat] WebSocket not connected, reloading notebook from S3')
            reloadNotebook()
          }
        } else {
          const errorMsg = response.error || 'Unknown error'
          if (errorMsg.includes('playground') || errorMsg.includes('kernel') ||
              errorMsg.includes('not running') || errorMsg.includes('Connection refused') ||
              errorMsg.includes('container')) {
            setChatMessages((prev) => prev.slice(0, -1))
            setErrorPopup(`Cannot process request: ${errorMsg}\n\nPlease make sure the playground is running.`)
          } else {
            setChatMessages((prev) => [
              ...prev,
              { role: 'assistant', content: `Error: ${errorMsg}` },
            ])
          }
        }
      },
      // onError: Handle errors
      (error) => {
        console.error('Chat SSE error:', error)
        setChatStreamStatus(null)
        setChatLoading(false)

        const errorMsg = error || 'Unknown error'
        if (errorMsg.includes('playground') || errorMsg.includes('kernel') ||
            errorMsg.includes('not running') || errorMsg.includes('Connection refused') ||
            errorMsg.includes('container')) {
          setChatMessages((prev) => prev.slice(0, -1))
          setErrorPopup(`Cannot process request: ${errorMsg}\n\nPlease make sure the playground is running.`)
        } else {
          setChatMessages((prev) => prev.slice(0, -1))
          setErrorPopup('Failed to connect to the AI service.\n\nPlease make sure the playground is running and try again.')
        }
      }
    )
  }, [projectId, cells, toolMode, llmProvider, contextFormat, playground, isDirty, saveNotebook, reloadNotebook, notebookUpdates.status])

  const handleApproveTools = useCallback((tools: PendingToolCall[]) => {
    setChatLoading(true)
    setChatStreamStatus('Executing tools...')

    // Use SSE for real-time streaming
    chat.executeToolsWithSSE(
      projectId,
      tools,
      projectId,  // sessionId = projectId (same kernel session)
      toolMode,
      llmProvider,
      contextFormat,
      // onEvent: Handle real-time SSE events
      (event) => {
        switch (event.type) {
          case 'thinking':
            setChatStreamStatus((event.data as { message?: string }).message || 'Processing...')
            break
          case 'tool_executing':
            setChatStreamStatus(`Executing: ${(event.data as { name?: string }).name || 'tool'}...`)
            break
          case 'tool_result':
            setChatStreamStatus('Tool completed, processing...')
            break
          case 'pending_tools':
            setChatStreamStatus('More tools need approval...')
            break
        }
      },
      // onDone: Handle completion
      (response) => {
        setChatStreamStatus(null)
        setChatLoading(false)

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
                chat.saveHistory(projectId, newMessages).catch(err => console.error('Failed to save chat history:', err))
                return newMessages
              })
            }
          } else {
            // Final response - no more pending tools
            setPendingTools([])

            // Update the last assistant message with final response and all steps, then persist
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
                chat.saveHistory(projectId, newMessages).catch(err => console.error('Failed to save chat history:', err))
                return newMessages
              })
            }
          }

          // Only reload from S3 if WebSocket is not connected (fallback)
          if (notebookUpdates.status !== 'connected') {
            console.log('[Chat] WebSocket not connected, reloading notebook from S3')
            reloadNotebook()
          }
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
      },
      // onError: Handle errors
      (error) => {
        console.error('Tool execution SSE error:', error)
        setChatStreamStatus(null)
        setChatLoading(false)
        setErrorPopup(`Failed to execute tools: ${error}\n\nPlease make sure the playground is running and try again.`)
        setPendingTools([])
      }
    )
  }, [projectId, toolMode, llmProvider, contextFormat, reloadNotebook, notebookUpdates.status])

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
      {/* Header */}
      <AppHeader
        title={currentProject?.name || 'Notebook'}
        subtitle={isDirty ? 'Unsaved changes' : undefined}
        subtitleColor={isDirty ? 'var(--app-accent-warning)' : undefined}
        leftActions={
          <button
            onClick={() => router.push('/dashboard')}
            className="p-2 rounded-lg transition-all"
            style={{ color: 'var(--app-text-muted)' }}
            title="Back to dashboard"
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        }
        rightActions={
          <button
            onClick={handleCloseSession}
            className="p-2 rounded-lg transition-all flex items-center gap-1.5 text-sm"
            style={{ color: 'var(--app-text-muted)' }}
            title="Stop playground and return to dashboard"
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'; e.currentTarget.style.color = 'var(--app-accent-error)' }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = 'var(--app-text-muted)' }}
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Close Session</span>
          </button>
        }
        onBeforeLogout={async () => {
          try {
            if (isDirty) await saveNotebookCore()
            if (chatMessages.length > 0) await chat.saveHistory(projectId, chatMessages)
            await playgrounds.stop()
          } catch {}
        }}
      />

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
        onExportPDF={handleExportPDF}
        isExportingPDF={isExportingPDF}
        totalCells={cells.length}
        isDirty={isDirty}
        isSaving={isSaving}
        playgroundStatus={kernel.status}
        kernelStatus={kernel.kernelStatus}
        onStartKernel={handleStartKernel}
        onStopKernel={handleStopKernel}
        onRestartKernel={handleRestartKernel}
        onRestartPlayground={handleRestartPlayground}
        showChat={showChat}
        onToggleChat={() => setShowChat(!showChat)}
        onOpenLogs={handleOpenLogs}
        onOpenTerminal={() => window.open(`/terminal/${projectId}`, '_blank')}
        llmProvider={llmProvider}
        onProviderChange={setLlmProvider}
        availableProviders={availableProviders}
        contextFormat={contextFormat}
        onContextFormatChange={setContextFormat}
        showFiles={showFiles}
        onToggleFiles={() => setShowFiles(!showFiles)}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* File panel - left side */}
        {showFiles && (
          <div className="w-[240px] min-w-[200px] max-w-[300px] flex-shrink-0">
            <FilePanel
              projectId={projectId}
              isPlaygroundRunning={playground?.status === 'running'}
              onClose={() => setShowFiles(false)}
            />
          </div>
        )}

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
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
            )}
            {cells.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                  <BookOpen className="w-8 h-8 text-gray-500" strokeWidth={1.5} />
                </div>
                <h4 className="text-lg font-medium text-white mb-2">Empty notebook</h4>
                <p className="text-gray-400 mb-6">Add your first cell to get started</p>
                <div className="flex justify-center gap-3">
                  <button
                    onClick={() => handleAddCell('code')}
                    className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white rounded-xl font-medium shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    Code Cell
                  </button>
                  <button
                    onClick={() => handleAddCell('markdown')}
                    className="px-5 py-2.5 bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 rounded-xl font-medium transition-all flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
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
                        onCancelAICell={handleCancelAICell}
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
              streamStatus={chatStreamStatus}
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
                <AlertTriangle className="w-6 h-6" />
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

      {/* Playground Loading Overlay */}
      {playgroundLoading && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div
            className="rounded-xl p-8 max-w-sm mx-4 shadow-2xl text-center"
            style={{
              backgroundColor: 'var(--nb-bg-cell)',
              border: '1px solid var(--nb-border-default)',
            }}
          >
            <div className="relative w-16 h-16 mx-auto mb-4">
              {/* Outer spinning ring */}
              <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full" />
              <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" />
              {/* Inner pulsing circle */}
              <div className="absolute inset-3 bg-gradient-to-br from-blue-500 to-teal-500 rounded-full animate-pulse" />
            </div>
            <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--nb-text-primary)' }}>
              Starting Playground
            </h3>
            <p className="text-sm" style={{ color: 'var(--nb-text-muted)' }}>
              Setting up your Python environment...
            </p>
            <div className="mt-4 flex justify-center gap-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
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
                <AlertTriangle className="w-6 h-6" />
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
