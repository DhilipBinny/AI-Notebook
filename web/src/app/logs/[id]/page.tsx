'use client'

import { useEffect, useRef, useState, use } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { playgrounds } from '@/lib/api'

export default function LogsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params)
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstance = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [projectName, setProjectName] = useState<string>('')
  const [isInIframe, setIsInIframe] = useState(false)

  // Detect if running in iframe
  useEffect(() => {
    setIsInIframe(window.self !== window.top)
  }, [])

  useEffect(() => {
    if (!terminalRef.current) return

    // Get token from localStorage
    const token = localStorage.getItem('access_token')
    if (!token) {
      setError('Not authenticated. Please log in first.')
      return
    }

    // Initialize terminal
    const terminal = new Terminal({
      cursorBlink: false,
      disableStdin: true, // Read-only logs
      fontSize: 13,
      fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, monospace',
      scrollback: 10000,
      theme: {
        background: '#0d1117',
        foreground: '#c9d1d9',
        cursor: '#c9d1d9',
        cursorAccent: '#0d1117',
        selectionBackground: '#3b5070',
        black: '#484f58',
        red: '#ff7b72',
        green: '#7ee787',
        yellow: '#d29922',
        blue: '#58a6ff',
        magenta: '#bc8cff',
        cyan: '#76e3ea',
        white: '#b1bac4',
        brightBlack: '#6e7681',
        brightRed: '#ffa198',
        brightGreen: '#a5d6a7',
        brightYellow: '#e3b341',
        brightBlue: '#79c0ff',
        brightMagenta: '#d2a8ff',
        brightCyan: '#a5f3fc',
        brightWhite: '#f0f6fc',
      },
    })

    const fitAddon = new FitAddon()
    const webLinksAddon = new WebLinksAddon()

    terminal.loadAddon(fitAddon)
    terminal.loadAddon(webLinksAddon)
    terminal.open(terminalRef.current)
    fitAddon.fit()

    terminalInstance.current = terminal
    fitAddonRef.current = fitAddon

    terminal.writeln('\x1b[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m')
    terminal.writeln('\x1b[1;36m  AI Notebook - Playground Logs\x1b[0m')
    terminal.writeln('\x1b[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m')
    terminal.writeln('')
    terminal.writeln('\x1b[33mFetching logs...\x1b[0m')

    // Fetch initial logs
    const fetchInitialLogs = async () => {
      try {
        const { logs: initialLogs } = await playgrounds.getLogs(projectId, 200)
        if (initialLogs) {
          terminal.writeln('\x1b[32mLoaded initial logs\x1b[0m')
          terminal.writeln('')
          // Write each line
          initialLogs.split('\n').forEach((line: string) => {
            terminal.writeln(line)
          })
        }
      } catch (err) {
        console.error('Failed to fetch initial logs:', err)
        terminal.writeln('\x1b[31mFailed to fetch initial logs\x1b[0m')
      }
    }

    fetchInitialLogs()

    // Connect WebSocket for streaming logs
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/projects/${projectId}/playground/logs/stream?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
    }

    ws.onmessage = (event) => {
      const data = event.data
      if (data) {
        terminal.writeln(data)
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onclose = (event) => {
      setConnected(false)
      if (event.code === 4004) {
        terminal.writeln('')
        terminal.writeln('\x1b[31mPlayground not running.\x1b[0m')
      } else {
        terminal.writeln('')
        terminal.writeln('\x1b[33mLog stream disconnected.\x1b[0m')
      }
    }

    // Handle resize
    const handleResize = () => {
      fitAddon.fit()
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      ws.close()
      terminal.dispose()
    }
  }, [projectId])

  // Fetch project name
  useEffect(() => {
    const fetchProjectName = async () => {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) return

        const response = await fetch(`/api/projects/${projectId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (response.ok) {
          const data = await response.json()
          setProjectName(data.name || 'Unknown')
          document.title = `Logs - ${data.name}`
        }
      } catch {
        // Ignore errors
      }
    }
    fetchProjectName()
  }, [projectId])

  const handleClear = () => {
    if (terminalInstance.current) {
      terminalInstance.current.clear()
      terminalInstance.current.writeln('\x1b[33mLogs cleared. New logs will appear below.\x1b[0m')
      terminalInstance.current.writeln('')
    }
  }

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#0d1117' }}>
      {/* Custom scrollbar styles for xterm */}
      <style jsx global>{`
        .xterm-viewport::-webkit-scrollbar {
          width: 10px;
        }
        .xterm-viewport::-webkit-scrollbar-track {
          background: #161b22;
          border-radius: 5px;
        }
        .xterm-viewport::-webkit-scrollbar-thumb {
          background: #30363d;
          border-radius: 5px;
          border: 2px solid #161b22;
        }
        .xterm-viewport::-webkit-scrollbar-thumb:hover {
          background: #484f58;
        }
      `}</style>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: '#30363d', backgroundColor: '#161b22' }}>
        <div className="flex items-center gap-3">
          {!isInIframe && (
            <button
              onClick={() => window.close()}
              className="p-1.5 rounded hover:bg-white/10 transition-colors"
              title="Close logs"
            >
              <svg className="w-5 h-5" style={{ color: '#c9d1d9' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" style={{ color: '#58a6ff' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="font-medium" style={{ color: '#c9d1d9' }}>
              Playground Logs {projectName && `- ${projectName}`}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleClear}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded hover:bg-white/10 transition-colors"
            style={{ color: '#8b949e' }}
            title="Clear logs"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear
          </button>
          <button
            onClick={() => {
              if (terminalInstance.current) {
                // Get all text from the terminal buffer
                const buffer = terminalInstance.current.buffer.active
                let logs = ''
                for (let i = 0; i < buffer.length; i++) {
                  const line = buffer.getLine(i)
                  if (line) {
                    logs += line.translateToString(true) + '\n'
                  }
                }
                // Create and download file
                const blob = new Blob([logs], { type: 'text/plain' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `playground-logs-${projectId}-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
                URL.revokeObjectURL(url)
              }
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded hover:bg-white/10 transition-colors"
            style={{ color: '#8b949e' }}
            title="Export logs"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </button>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
            <span className="text-sm" style={{ color: '#8b949e' }}>
              {connected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Terminal */}
      <div className="flex-1 p-2">
        <div
          ref={terminalRef}
          className="h-full w-full"
          style={{ backgroundColor: '#0d1117' }}
        />
      </div>

      {/* Error display */}
      {error && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400">
          {error}
        </div>
      )}
    </div>
  )
}
