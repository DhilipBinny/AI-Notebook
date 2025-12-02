'use client'

import { useEffect, useRef, useState, use } from 'react'
import { useRouter } from 'next/navigation'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'

export default function TerminalPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params)
  const router = useRouter()
  const terminalRef = useRef<HTMLDivElement>(null)
  const terminalInstance = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!terminalRef.current) return

    // Get token from localStorage
    const token = localStorage.getItem('token')
    if (!token) {
      setError('Not authenticated')
      return
    }

    // Initialize terminal
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

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      terminal.writeln('\x1b[32mConnected!\x1b[0m')
      terminal.writeln('')

      // Send initial resize
      const { cols, rows } = terminal
      ws.send(JSON.stringify({ type: 'resize', cols, rows }))
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
      } else {
        terminal.writeln('\x1b[33mDisconnected\x1b[0m')
      }
    }

    // Handle terminal input
    terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'input', data }))
      }
    })

    // Handle resize
    const handleResize = () => {
      fitAddon.fit()
      if (ws.readyState === WebSocket.OPEN) {
        const { cols, rows } = terminal
        ws.send(JSON.stringify({ type: 'resize', cols, rows }))
      }
    }

    window.addEventListener('resize', handleResize)

    // Focus terminal
    terminal.focus()

    return () => {
      window.removeEventListener('resize', handleResize)
      ws.close()
      terminal.dispose()
    }
  }, [projectId])

  return (
    <div className="h-screen w-screen flex flex-col" style={{ backgroundColor: '#1e1e2e' }}>
      {/* Header */}
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
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm" style={{ color: '#a6adc8' }}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

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
