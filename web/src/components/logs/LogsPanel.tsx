'use client'

import { useEffect, useRef, useState } from 'react'
import { playgrounds } from '@/lib/api'
import { Trash2, Download, ExternalLink } from 'lucide-react'
import '@xterm/xterm/css/xterm.css'

interface LogsPanelProps {
  projectId: string
  onOpenInWindow?: () => void
}

export default function LogsPanel({ projectId, onOpenInWindow }: LogsPanelProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const terminalInstance = useRef<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fitAddonRef = useRef<any>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!terminalRef.current) return

    const token = localStorage.getItem('access_token')
    if (!token) {
      setError('Not authenticated')
      return
    }

    let disposed = false
    let ws: WebSocket | null = null
    let resizeObserver: ResizeObserver | null = null

    const initTerminal = async () => {
      const [xtermModule, fitModule, webLinksModule] = await Promise.all([
        import('@xterm/xterm'),
        import('@xterm/addon-fit'),
        import('@xterm/addon-web-links'),
      ])

      if (disposed || !terminalRef.current) return

      const { Terminal } = xtermModule
      const { FitAddon } = fitModule
      const { WebLinksAddon } = webLinksModule

      const terminal = new Terminal({
        cursorBlink: false,
        disableStdin: true,
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

      terminal.writeln('\x1b[33mFetching logs...\x1b[0m')

      // Fetch initial logs
      try {
        const { logs: initialLogs } = await playgrounds.getLogs(projectId, 200)
        if (initialLogs && !disposed) {
          terminal.writeln('\x1b[32mLoaded initial logs\x1b[0m')
          terminal.writeln('')
          initialLogs.split('\n').forEach((line: string) => {
            terminal.writeln(line)
          })
        }
      } catch {
        if (!disposed) terminal.writeln('\x1b[31mFailed to fetch initial logs\x1b[0m')
      }

      // Connect WebSocket for streaming logs
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/projects/${projectId}/playground/logs/stream?token=${encodeURIComponent(token)}`

      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onmessage = (event) => {
        if (event.data) terminal.writeln(event.data)
      }
      ws.onerror = () => setError('WebSocket connection error')
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

      // Use ResizeObserver for panel resize (drag handle doesn't fire window.resize)
      resizeObserver = new ResizeObserver(() => {
        fitAddon.fit()
      })
      resizeObserver.observe(terminalRef.current)
    }

    initTerminal()

    return () => {
      disposed = true
      if (resizeObserver) resizeObserver.disconnect()
      if (ws) ws.close()
      if (terminalInstance.current) {
        terminalInstance.current.dispose()
        terminalInstance.current = null
      }
    }
  }, [projectId])

  const handleClear = () => {
    if (terminalInstance.current) {
      terminalInstance.current.clear()
      terminalInstance.current.writeln('\x1b[33mLogs cleared.\x1b[0m')
      terminalInstance.current.writeln('')
    }
  }

  const handleExport = () => {
    if (terminalInstance.current) {
      const buffer = terminalInstance.current.buffer.active
      let logs = ''
      for (let i = 0; i < buffer.length; i++) {
        const line = buffer.getLine(i)
        if (line) {
          logs += line.translateToString(true) + '\n'
        }
      }
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
  }

  return (
    <div className="h-full flex flex-col" style={{ backgroundColor: '#0d1117' }}>
      {/* Scrollbar styles for xterm */}
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

      {/* Compact header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b flex-shrink-0"
        style={{ borderColor: '#30363d', backgroundColor: '#161b22' }}
      >
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-sm font-medium" style={{ color: '#c9d1d9' }}>
            Logs
          </span>
          <span className="text-xs" style={{ color: '#8b949e' }}>
            {connected ? 'Live' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClear}
            className="p-1.5 rounded hover:bg-white/10 transition-colors"
            style={{ color: '#8b949e' }}
            title="Clear logs"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={handleExport}
            className="p-1.5 rounded hover:bg-white/10 transition-colors"
            style={{ color: '#8b949e' }}
            title="Export logs"
          >
            <Download className="w-3.5 h-3.5" />
          </button>
          {onOpenInWindow && (
            <button
              onClick={onOpenInWindow}
              className="p-1.5 rounded hover:bg-white/10 transition-colors"
              style={{ color: '#8b949e' }}
              title="Open in new window"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Terminal */}
      <div className="flex-1 p-2 min-h-0">
        <div
          ref={terminalRef}
          className="h-full w-full"
          style={{ backgroundColor: '#0d1117' }}
        />
      </div>

      {/* Error display */}
      {error && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  )
}
