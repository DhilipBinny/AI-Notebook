'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import type { CellOutput } from '@/types'

interface KernelState {
  status: 'disconnected' | 'connecting' | 'connected'
  executionCount: number
}

interface ExecutionMessage {
  type: 'execution_count' | 'stream' | 'execute_result' | 'display_data' | 'error' | 'status'
  cell_id: string
  count?: number
  name?: string
  text?: string
  data?: Record<string, unknown>
  ename?: string
  evalue?: string
  traceback?: string[]
  status?: 'complete' | 'error'
}

export function useKernel(playgroundUrl: string | null, sessionId: string | null = null) {
  const [kernelState, setKernelState] = useState<KernelState>({
    status: 'disconnected',
    executionCount: 0,
  })
  const [runningCellId, setRunningCellId] = useState<string | null>(null)
  const sessionIdRef = useRef<string | null>(sessionId)

  const wsRef = useRef<WebSocket | null>(null)
  const outputCallbackRef = useRef<((cellId: string, output: CellOutput) => void) | null>(null)
  const executionCountCallbackRef = useRef<((cellId: string, count: number) => void) | null>(null)
  const completionCallbackRef = useRef<((cellId: string, success: boolean) => void) | null>(null)

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!playgroundUrl || wsRef.current?.readyState === WebSocket.OPEN) return

    setKernelState((prev) => ({ ...prev, status: 'connecting' }))

    // Build WebSocket URL from playground URL
    // playgroundUrl is like http://localhost:8888 or the container URL
    const wsProtocol = playgroundUrl.startsWith('https') ? 'wss:' : 'ws:'
    const host = playgroundUrl.replace(/^https?:\/\//, '')
    const wsUrl = `${wsProtocol}//${host}/ws/execute`

    console.log('[Kernel] Connecting to:', wsUrl)

    try {
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[Kernel] WebSocket connected')
        setKernelState((prev) => ({ ...prev, status: 'connected' }))
      }

      ws.onmessage = (event) => {
        try {
          const data: ExecutionMessage = JSON.parse(event.data)
          handleMessage(data)
        } catch (err) {
          console.error('[Kernel] Failed to parse message:', err)
        }
      }

      ws.onclose = () => {
        console.log('[Kernel] WebSocket disconnected')
        setKernelState((prev) => ({ ...prev, status: 'disconnected' }))
        wsRef.current = null
        // Attempt reconnect after 3 seconds
        setTimeout(() => connect(), 3000)
      }

      ws.onerror = (error) => {
        console.error('[Kernel] WebSocket error:', error)
        setKernelState((prev) => ({ ...prev, status: 'disconnected' }))
      }

      wsRef.current = ws
    } catch (err) {
      console.error('[Kernel] Failed to connect:', err)
      setKernelState((prev) => ({ ...prev, status: 'disconnected' }))
    }
  }, [playgroundUrl])

  // Handle incoming messages
  const handleMessage = useCallback((data: ExecutionMessage) => {
    const cellId = data.cell_id

    switch (data.type) {
      case 'execution_count':
        if (data.count !== undefined) {
          setKernelState((prev) => ({ ...prev, executionCount: data.count! }))
          executionCountCallbackRef.current?.(cellId, data.count)
        }
        break

      case 'stream':
        if (data.text) {
          const output: CellOutput = {
            output_type: 'stream',
            text: data.text,
          }
          outputCallbackRef.current?.(cellId, output)
        }
        break

      case 'execute_result':
      case 'display_data':
        if (data.data) {
          const output: CellOutput = {
            output_type: data.type,
            data: data.data,
          }
          outputCallbackRef.current?.(cellId, output)
        }
        break

      case 'error':
        const errorOutput: CellOutput = {
          output_type: 'error',
          ename: data.ename,
          evalue: data.evalue,
          traceback: data.traceback,
        }
        outputCallbackRef.current?.(cellId, errorOutput)
        break

      case 'status':
        if (data.status === 'complete' || data.status === 'error') {
          setRunningCellId(null)
          completionCallbackRef.current?.(cellId, data.status === 'complete')
        }
        break
    }
  }, [])

  // Execute code
  const execute = useCallback((cellId: string, code: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[Kernel] WebSocket not connected')
      return false
    }

    if (runningCellId) {
      console.warn('[Kernel] Already executing a cell')
      return false
    }

    setRunningCellId(cellId)

    wsRef.current.send(JSON.stringify({
      code,
      cell_id: cellId,
      session_id: sessionIdRef.current,
    }))

    return true
  }, [runningCellId])

  // Execute code and wait for completion - useful for Run All
  const executeAndWait = useCallback((cellId: string, code: string, timeoutMs: number = 300000): Promise<boolean> => {
    return new Promise((resolve) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.error('[Kernel] WebSocket not connected')
        resolve(false)
        return
      }

      // Set up one-time completion handler
      const originalCallback = completionCallbackRef.current
      let resolved = false

      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true
          completionCallbackRef.current = originalCallback
          console.warn(`Cell ${cellId} execution timed out`)
          resolve(false)
        }
      }, timeoutMs)

      completionCallbackRef.current = (completedCellId, success) => {
        // Call original callback too
        originalCallback?.(completedCellId, success)

        if (completedCellId === cellId && !resolved) {
          resolved = true
          clearTimeout(timeout)
          completionCallbackRef.current = originalCallback
          resolve(success)
        }
      }

      // Send execution request directly (bypass runningCellId check for Run All)
      setRunningCellId(cellId)
      wsRef.current.send(JSON.stringify({
        code,
        cell_id: cellId,
        session_id: sessionIdRef.current,
      }))
    })
  }, [])

  // Interrupt execution
  const interrupt = useCallback(async () => {
    if (!playgroundUrl || !sessionIdRef.current) return false

    try {
      const response = await fetch(`${playgroundUrl}/session/${sessionIdRef.current}/kernel/interrupt`, {
        method: 'POST',
      })
      if (response.ok) {
        setRunningCellId(null)
        return true
      }
    } catch (err) {
      console.error('[Kernel] Failed to interrupt:', err)
    }
    return false
  }, [playgroundUrl])

  // Restart kernel
  const restart = useCallback(async () => {
    if (!playgroundUrl || !sessionIdRef.current) return false

    try {
      const response = await fetch(`${playgroundUrl}/session/${sessionIdRef.current}/kernel/restart`, {
        method: 'POST',
      })
      if (response.ok) {
        setRunningCellId(null)
        setKernelState((prev) => ({ ...prev, executionCount: 0 }))
        return true
      }
    } catch (err) {
      console.error('[Kernel] Failed to restart:', err)
    }
    return false
  }, [playgroundUrl])

  // Set callbacks
  const setOutputCallback = useCallback((cb: (cellId: string, output: CellOutput) => void) => {
    outputCallbackRef.current = cb
  }, [])

  const setExecutionCountCallback = useCallback((cb: (cellId: string, count: number) => void) => {
    executionCountCallbackRef.current = cb
  }, [])

  const setCompletionCallback = useCallback((cb: (cellId: string, success: boolean) => void) => {
    completionCallbackRef.current = cb
  }, [])

  // Update sessionId ref when prop changes
  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  // Connect when playground URL changes
  useEffect(() => {
    if (playgroundUrl) {
      connect()
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [playgroundUrl, connect])

  return {
    status: kernelState.status,
    executionCount: kernelState.executionCount,
    runningCellId,
    execute,
    executeAndWait,
    interrupt,
    restart,
    setOutputCallback,
    setExecutionCountCallback,
    setCompletionCallback,
  }
}
