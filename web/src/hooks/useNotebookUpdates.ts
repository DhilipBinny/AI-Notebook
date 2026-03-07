'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import type { CellOutput } from '@/types'

/**
 * Notebook update message from WebSocket
 */
interface NotebookUpdateMessage {
  type: 'notebook_update' | 'pong'
  update_type?: 'cell_created' | 'cell_updated' | 'cell_deleted' | 'cell_executed'
  cell_id?: string
  cell_index?: number
  content?: string
  cell_type?: 'code' | 'markdown' | 'ai'
  outputs?: CellOutput[]
  execution_count?: number
}

interface UseNotebookUpdatesOptions {
  onCellCreated?: (cellId: string, cellIndex: number, content: string, cellType: string) => void
  onCellUpdated?: (cellId: string, cellIndex: number, content: string, cellType?: string) => void
  onCellDeleted?: (cellId: string, cellIndex: number) => void
  onCellExecuted?: (cellId: string, cellIndex: number, outputs: CellOutput[], executionCount?: number) => void
}

/**
 * Hook for receiving real-time notebook updates via WebSocket.
 *
 * Connects to Master API's /api/internal/ws/notebook/{projectId} endpoint
 * and receives updates when LLM tools modify cells via the internal API.
 *
 * Usage:
 *   const { status } = useNotebookUpdates(projectId, {
 *     onCellUpdated: (cellId, index, content) => {
 *       // Update local cell state
 *     },
 *     onCellCreated: (cellId, index, content, type) => {
 *       // Add new cell to local state
 *     },
 *   })
 */
export function useNotebookUpdates(
  projectId: string | null,
  options: UseNotebookUpdatesOptions = {}
) {
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const disposedRef = useRef(false)
  const optionsRef = useRef(options)

  // Keep options ref updated
  useEffect(() => {
    optionsRef.current = options
  }, [options])

  // Handle incoming messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: NotebookUpdateMessage = JSON.parse(event.data)

      if (data.type === 'pong') {
        return
      }

      if (data.type === 'notebook_update' && data.update_type && data.cell_id !== undefined) {
        const { update_type, cell_id, cell_index, content, cell_type, outputs, execution_count } = data

        console.log(`[NotebookUpdates] ${update_type}: cell=${cell_id}, index=${cell_index}`)

        switch (update_type) {
          case 'cell_created':
            if (content !== undefined && cell_type) {
              optionsRef.current.onCellCreated?.(cell_id, cell_index ?? 0, content, cell_type)
            }
            break

          case 'cell_updated':
            if (content !== undefined) {
              optionsRef.current.onCellUpdated?.(cell_id, cell_index ?? 0, content, cell_type)
            }
            break

          case 'cell_deleted':
            optionsRef.current.onCellDeleted?.(cell_id, cell_index ?? 0)
            break

          case 'cell_executed':
            if (outputs) {
              optionsRef.current.onCellExecuted?.(cell_id, cell_index ?? 0, outputs, execution_count)
            }
            break
        }
      }
    } catch (err) {
      console.error('[NotebookUpdates] Failed to parse message:', err)
    }
  }, [])

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (disposedRef.current) return
    if (!projectId) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    setStatus('connecting')

    // Build WebSocket URL - connect to Master API's internal WebSocket
    // Use same origin (goes through nginx proxy)
    // WebSocket auth requires JWT token as query parameter (can't use headers)
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
    const wsUrl = `${wsProtocol}//${window.location.host}/api/internal/ws/notebook/${projectId}${token ? `?token=${token}` : ''}`

    console.log('[NotebookUpdates] Connecting to:', wsUrl)

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[NotebookUpdates] Connected to project:', projectId)
        setStatus('connected')
      }

      ws.onmessage = handleMessage

      ws.onclose = () => {
        console.log('[NotebookUpdates] Disconnected')
        setStatus('disconnected')
        wsRef.current = null

        // Reconnect after 3 seconds (only if not disposed)
        if (!disposedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, 3000)
        }
      }

      ws.onerror = (error) => {
        console.error('[NotebookUpdates] WebSocket error:', error)
        setStatus('disconnected')
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[NotebookUpdates] Failed to connect:', err)
      setStatus('disconnected')
    }
  }, [projectId, handleMessage])

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setStatus('disconnected')
  }, [])

  // Connect when project ID is available
  useEffect(() => {
    disposedRef.current = false
    if (projectId) {
      connect()
    }

    return () => {
      disposedRef.current = true
      disconnect()
    }
  }, [projectId, connect, disconnect])

  // Ping to keep connection alive
  useEffect(() => {
    if (status !== 'connected') return

    const pingInterval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // Ping every 30 seconds

    return () => clearInterval(pingInterval)
  }, [status])

  return {
    status,
    connect,
    disconnect,
  }
}
