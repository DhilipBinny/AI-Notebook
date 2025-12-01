'use client'

import { useEffect, useState, useCallback, use } from 'react'
import { useRouter } from 'next/navigation'
import { auth, projects, playgrounds, chat, notebooks } from '@/lib/api'
import { useAuthStore, useProjectsStore, useNotebookStore } from '@/lib/store'
import Cell from '@/components/notebook/Cell'
import NotebookToolbar from '@/components/notebook/NotebookToolbar'
import CellInsertButtons from '@/components/notebook/CellInsertButtons'
import ChatPanel from '@/components/chat/ChatPanel'
import { useKernel } from '@/hooks/useKernel'
import { ThemeProvider } from '@/contexts/ThemeContext'
import type { Cell as CellType, Playground, ChatMessage } from '@/types'

// Generate unique cell ID
function generateCellId(): string {
  return `cell-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

// Create empty cell
function createCell(type: 'code' | 'markdown' | 'raw'): CellType {
  const cellId = generateCellId()
  return {
    id: cellId,
    type,
    source: '',
    outputs: [],
    metadata: { cell_id: cellId },  // Store in metadata for ipynb compatibility
  }
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
  const [contextCellIds, setContextCellIds] = useState<Set<string>>(new Set())

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading] = useState(false)
  const [pendingTools, setPendingTools] = useState<PendingToolCall[]>([])
  const [llmProvider, setLlmProvider] = useState('gemini')
  const [toolMode, setToolMode] = useState<'auto' | 'manual' | 'ai_decide'>('manual')
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
  const kernel = useKernel(playgroundUrl)

  // Helper to save notebook (for auto-save before chat)
  const saveNotebook = useCallback(async () => {
    if (!currentProject) return false

    try {
      // Save in Jupyter .ipynb standard format
      const cellsToSave = cells.map((cell) => ({
        cell_type: cell.type,  // Jupyter standard field name
        source: cell.source,
        outputs: (cell.outputs || []) as unknown as Record<string, unknown>[],
        execution_count: cell.execution_count,
        metadata: { ...cell.metadata, cell_id: cell.id },  // cell_id in metadata only
      }))

      await notebooks.save(projectId, cellsToSave)
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
        const loadedCells = notebookData.notebook.cells.map((cell) => ({
          id: cell.metadata?.cell_id || generateCellId(),  // cell_id from metadata (Jupyter standard)
          type: (cell.cell_type || 'code') as 'code' | 'markdown' | 'raw',
          source: cell.source,
          outputs: cell.outputs as any[],
          execution_count: cell.execution_count,
          metadata: cell.metadata,
        }))
        setCells(loadedCells)
        // Auto-add any new cells to context (keep existing context, add new ones)
        setContextCellIds((prev) => {
          const newIds = new Set(prev)
          loadedCells.forEach(c => newIds.add(c.id))
          return newIds
        })
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
            const loadedCells = notebookData.notebook.cells.map((cell) => ({
              id: cell.metadata?.cell_id || generateCellId(),  // cell_id from metadata
              type: (cell.cell_type || 'code') as 'code' | 'markdown' | 'raw',
              source: cell.source,
              outputs: cell.outputs as any[],
              execution_count: cell.execution_count,
              metadata: cell.metadata,
            }))
            setCells(loadedCells)
            // Auto-add all loaded cells to context
            setContextCellIds(new Set(loadedCells.map(c => c.id)))
          } else {
            // Initialize with one empty code cell if none
            const newCell = createCell('code')
            setCells([newCell])
            setContextCellIds(new Set([newCell.id]))
          }
        } catch {
          // No notebook yet, start with empty cell
          const newCell = createCell('code')
          setCells([newCell])
          setContextCellIds(new Set([newCell.id]))
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
      // Get current cell to append to its outputs
      const cell = cells.find((c) => c.id === cellId)
      if (cell) {
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
    })
  }, [kernel, cells, updateCell])

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
  const handleAddCell = useCallback((type: 'code' | 'markdown' | 'raw') => {
    const newCell = createCell(type)
    const selectedIndex = cells.findIndex((c) => c.id === selectedCellId)
    addCell(newCell, selectedIndex >= 0 ? selectedIndex + 1 : undefined)
    setSelectedCellId(newCell.id)
    // Auto-add new cell to context
    setContextCellIds((prev) => new Set([...prev, newCell.id]))
  }, [cells, selectedCellId, addCell])

  // Insert cell at specific position (used by insert buttons between cells)
  const handleInsertCellAt = useCallback((type: 'code' | 'markdown' | 'raw', index: number) => {
    const newCell = createCell(type)
    addCell(newCell, index)
    setSelectedCellId(newCell.id)
    // Auto-add new cell to context
    setContextCellIds((prev) => new Set([...prev, newCell.id]))
  }, [addCell])

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

    for (const cell of cells) {
      if (cell.type === 'code' && cell.source.trim()) {
        updateCell(cell.id, { outputs: [] })
        kernel.execute(cell.id, cell.source)
        // Wait a bit between executions
        await new Promise((resolve) => setTimeout(resolve, 500))
      }
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
        setContextCellIds(new Set())
        setSelectedCellId(null)
        setConfirmPopup(null)
      },
    })
  }, [cells.length])

  // Select/Deselect all cells for AI context
  const handleSelectAllContext = useCallback(() => {
    setContextCellIds(new Set(cells.map(c => c.id)))
  }, [cells])

  const handleDeselectAllContext = useCallback(() => {
    setContextCellIds(new Set())
  }, [])

  const handleSave = useCallback(async () => {
    if (!currentProject) return
    setIsSaving(true)
    try {
      // Save notebook to S3 via API (Jupyter .ipynb standard format)
      const cellsToSave = cells.map((cell) => ({
        cell_type: cell.type,  // Jupyter standard field name
        source: cell.source,
        outputs: (cell.outputs || []) as unknown as Record<string, unknown>[],
        execution_count: cell.execution_count,
        metadata: { ...cell.metadata, cell_id: cell.id },  // cell_id in metadata only
      }))

      const result = await notebooks.save(projectId, cellsToSave)
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

  // Keyboard shortcuts (Ctrl+S to save)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleSave])

  const handleToggleContext = useCallback((cellId: string) => {
    setContextCellIds((prev) => {
      const next = new Set(prev)
      if (next.has(cellId)) {
        next.delete(cellId)
      } else {
        next.add(cellId)
      }
      return next
    })
  }, [])

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

      // Send only cell IDs - backend loads content from S3
      const selectedCellIds = Array.from(contextCellIds)

      // Call chat API - backend loads cell content from S3 notebook
      const response = await chat.sendMessage(projectId, message, selectedCellIds, toolMode, llmProvider)

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
  }, [projectId, cells, contextCellIds, toolMode, llmProvider, playground, isDirty, saveNotebook, reloadNotebook])

  const handleApproveTools = useCallback(async (tools: PendingToolCall[]) => {
    setChatLoading(true)
    try {
      const response = await chat.executeTools(projectId, tools)

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
  }, [projectId, reloadNotebook])

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
        onAddNotes={() => handleAddCell('raw')}
        onRunAll={handleRunAll}
        onClearOutputs={handleClearOutputs}
        onDeleteAllCells={handleDeleteAllCells}
        onSave={handleSave}
        onExport={handleExport}
        isExporting={isExporting}
        contextCount={contextCellIds.size}
        totalCells={cells.length}
        onSelectAllContext={handleSelectAllContext}
        onDeselectAllContext={handleDeselectAllContext}
        isDirty={isDirty}
        isSaving={isSaving}
        kernelStatus={kernel.status}
        onRestartKernel={handleRestartKernel}
        showChat={showChat}
        onToggleChat={() => setShowChat(!showChat)}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Notebook panel */}
        <div className="flex-1 overflow-y-auto p-4" style={{ backgroundColor: 'var(--nb-bg-primary)' }}>
          <div className="max-w-4xl mx-auto space-y-4">
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
                  onInsertNotes={() => handleInsertCellAt('raw', 0)}
                />

                {cells.map((cell, index) => (
                  <div key={cell.id}>
                    <Cell
                      cell={cell}
                      index={index}
                      isSelected={selectedCellId === cell.id}
                      isRunning={kernel.runningCellId === cell.id}
                      onSelect={() => setSelectedCellId(cell.id)}
                      onRun={() => handleRunCell(cell.id)}
                      onStop={() => kernel.interrupt()}
                      onDelete={() => deleteCell(cell.id)}
                      onMoveUp={() => moveCell(cell.id, 'up')}
                      onMoveDown={() => moveCell(cell.id, 'down')}
                      onUpdate={(updates) => updateCell(cell.id, updates)}
                      onToggleContext={() => handleToggleContext(cell.id)}
                      isInContext={contextCellIds.has(cell.id)}
                    />
                    {/* Insert button after each cell */}
                    <CellInsertButtons
                      onInsertCode={() => handleInsertCellAt('code', index + 1)}
                      onInsertMarkdown={() => handleInsertCellAt('markdown', index + 1)}
                      onInsertNotes={() => handleInsertCellAt('raw', index + 1)}
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
              onDeleteMessage={handleDeleteMessage}
              onEditMessage={handleEditMessage}
              onRerunMessage={handleRerunMessage}
              onClearHistory={handleClearHistory}
              onSummarize={handleSummarize}
              isSummarizing={isSummarizing}
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
