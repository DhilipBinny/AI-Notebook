'use client'

import { useEffect, useRef, useState, use } from 'react'
import '@xterm/xterm/css/xterm.css'

export default function TerminalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params)
  const terminalRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const terminalInstance = useRef<any>(null)
  const wsRef = useRef<WebSocket | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fitAddonRef = useRef<any>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isInIframe, setIsInIframe] = useState(false)

  // Detect if running in iframe
  useEffect(() => {
    setIsInIframe(window.self !== window.top)
  }, [])

  useEffect(() => {
    if (!terminalRef.current) return

    const token = localStorage.getItem('access_token')
    if (!token) {
      setError('Not authenticated. Please log in first.')
      return
    }

    let disposed = false
    let ws: WebSocket | null = null
    let handleResize: (() => void) | null = null

    // Dynamic import of xterm (uses browser globals, can't be imported at top level)
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
        cursorBlink: true,
        fontSize: 14,
        fontFamily: 'Monaco, Menlo, "Ubuntu Mono", Consolas, monospace',
        theme: {
          background: '#1e1e2e',
          foreground: '#cdd6f4',
          cursor: '#f5e0dc',
          cursorAccent: '#1e1e2e',
          selectionBackground: '#585b70',
          black: '#45475a',
          red: '#f38ba8',
          green: '#a6e3a1',
          yellow: '#f9e2af',
          blue: '#89b4fa',
          magenta: '#f5c2e7',
          cyan: '#94e2d5',
          white: '#bac2de',
          brightBlack: '#585b70',
          brightRed: '#f38ba8',
          brightGreen: '#a6e3a1',
          brightYellow: '#f9e2af',
          brightBlue: '#89b4fa',
          brightMagenta: '#f5c2e7',
          brightCyan: '#94e2d5',
          brightWhite: '#a6adc8',
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
      terminal.writeln('\x1b[1;36m  AI Notebook - Container Terminal\x1b[0m')
      terminal.writeln('\x1b[1;34m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\x1b[0m')
      terminal.writeln('')
      terminal.writeln('\x1b[33mConnecting to container...\x1b[0m')

      // Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/projects/${projectId}/playground/terminal?token=${encodeURIComponent(token)}`

      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        terminal.writeln('\x1b[32mConnected!\x1b[0m')
        terminal.writeln('')
        const { cols, rows } = terminal
        ws!.send(JSON.stringify({ type: 'resize', cols, rows }))
      }

      ws.onmessage = (event) => {
        terminal.write(event.data)
      }

      ws.onerror = () => {
        setError('WebSocket connection error')
        terminal.writeln('\x1b[31mConnection error\x1b[0m')
      }

      ws.onclose = (event) => {
        setConnected(false)
        if (event.code === 4004) {
          terminal.writeln('\x1b[31mPlayground not running. Start the playground first.\x1b[0m')
          terminal.writeln('\x1b[33mClosing in 3 seconds...\x1b[0m')
          setTimeout(() => window.close(), 3000)
        } else {
          terminal.writeln('\x1b[33mDisconnected. Closing...\x1b[0m')
          setTimeout(() => window.close(), 1000)
        }
      }

      // Handle terminal input
      terminal.onData((data: string) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'input', data }))
        }
      })

      handleResize = () => {
        fitAddon.fit()
        if (ws && ws.readyState === WebSocket.OPEN) {
          const { cols, rows } = terminal
          ws.send(JSON.stringify({ type: 'resize', cols, rows }))
        }
      }
      window.addEventListener('resize', handleResize)

      terminal.focus()
    }

    initTerminal()

    return () => {
      disposed = true
      if (handleResize) window.removeEventListener('resize', handleResize)
      if (ws) ws.close()
      if (terminalInstance.current) {
        terminalInstance.current.dispose()
        terminalInstance.current = null
      }
    }
  }, [projectId])

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#1e1e2e' }}>
      {/* Custom scrollbar styles for xterm */}
      <style jsx global>{`
        .xterm-viewport::-webkit-scrollbar {
          width: 10px;
        }
        .xterm-viewport::-webkit-scrollbar-track {
          background: #181825;
          border-radius: 5px;
        }
        .xterm-viewport::-webkit-scrollbar-thumb {
          background: #45475a;
          border-radius: 5px;
          border: 2px solid #181825;
        }
        .xterm-viewport::-webkit-scrollbar-thumb:hover {
          background: #585b70;
        }
      `}</style>
      {/* Header - hidden in iframe mode */}
      {!isInIframe && (
      <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: '#313244', backgroundColor: '#181825' }}>
        <div className="flex items-center gap-3">
          <button
            onClick={() => window.close()}
            className="p-1.5 rounded hover:bg-white/10 transition-colors"
            title="Close terminal"
          >
            <svg className="w-5 h-5" style={{ color: '#cdd6f4' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5" style={{ color: '#89b4fa' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="font-medium" style={{ color: '#cdd6f4' }}>Container Terminal</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Clear button */}
          <button
            onClick={() => terminalInstance.current?.clear()}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-sm hover:bg-white/10 transition-colors"
            style={{ color: '#cdd6f4' }}
            title="Clear terminal"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Clear
          </button>
          {/* Export Logs button */}
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
                a.download = `terminal-logs-${projectId}-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`
                document.body.appendChild(a)
                a.click()
                document.body.removeChild(a)
                URL.revokeObjectURL(url)
              }
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-sm hover:bg-white/10 transition-colors"
            style={{ color: '#cdd6f4' }}
            title="Export terminal logs"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export
          </button>
          {/* Connection status */}
          <div className="flex items-center gap-2 ml-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm" style={{ color: '#a6adc8' }}>
              {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>
      )}

      {/* Terminal */}
      <div className="flex-1 p-2">
        <div
          ref={terminalRef}
          className="h-full w-full"
          style={{ backgroundColor: '#1e1e2e' }}
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
