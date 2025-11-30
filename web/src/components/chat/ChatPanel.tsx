'use client'

import { useState, useRef, useEffect } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import type { ChatMessage, LLMStep } from '@/types'

interface PendingToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

interface ChatPanelProps {
  messages: ChatMessage[]
  isLoading: boolean
  pendingTools: PendingToolCall[]
  onSendMessage: (message: string) => void
  onApproveTools: (tools: PendingToolCall[]) => void
  onRejectTools: () => void
  llmProvider: string
  onProviderChange: (provider: string) => void
  toolMode: 'auto' | 'manual' | 'ai_decide'
  onToolModeChange: (mode: 'auto' | 'manual' | 'ai_decide') => void
  onDeleteMessage: (index: number) => void
  onEditMessage: (index: number, newContent: string) => void
  onRerunMessage: (index: number) => void
  onClearHistory: () => void
}

export default function ChatPanel({
  messages,
  isLoading,
  pendingTools,
  onSendMessage,
  onApproveTools,
  onRejectTools,
  llmProvider,
  onProviderChange,
  toolMode,
  onToolModeChange,
  onDeleteMessage,
  onEditMessage,
  onRerunMessage,
  onClearHistory,
}: ChatPanelProps) {
  const [input, setInput] = useState('')
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { theme } = useTheme()

  // Initialize selected tools when pending tools change
  useEffect(() => {
    if (pendingTools.length > 0) {
      setSelectedTools(new Set(pendingTools.map((t) => t.id)))
    }
  }, [pendingTools])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    onSendMessage(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleApprove = () => {
    const approved = pendingTools.filter((t) => selectedTools.has(t.id))
    if (approved.length > 0) {
      onApproveTools(approved)
    }
  }

  const toggleTool = (id: string) => {
    const newSelected = new Set(selectedTools)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedTools(newSelected)
  }

  const startEditing = (index: number, content: string) => {
    setEditingIndex(index)
    setEditContent(content)
  }

  const cancelEditing = () => {
    setEditingIndex(null)
    setEditContent('')
  }

  const saveEdit = () => {
    if (editingIndex !== null && editContent.trim()) {
      onEditMessage(editingIndex, editContent.trim())
      cancelEditing()
    }
  }

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      cancelEditing()
    } else if (e.key === 'Enter' && e.ctrlKey) {
      saveEdit()
    }
  }

  // Find the last user message index
  const lastUserMessageIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return i
    }
    return -1
  })()

  const renderSteps = (steps: LLMStep[]) => {
    if (!steps || steps.length === 0) return null

    const toolNames = [...new Set(steps.filter(s => s.name).map(s => s.name))]
    const summaryText = toolNames.length > 0
      ? `Used ${toolNames.length} tool${toolNames.length > 1 ? 's' : ''}: ${toolNames.join(', ')}`
      : `${steps.length} step${steps.length > 1 ? 's' : ''}`

    return (
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer" style={{ color: 'var(--nb-text-muted)' }}>
          {summaryText}
        </summary>
        <div className="mt-2 space-y-2 pl-2" style={{ borderLeft: '1px solid var(--nb-border-default)' }}>
          {steps.map((step, idx) => (
            <div key={idx} style={{ color: 'var(--nb-text-secondary)' }}>
              <span className="font-medium">
                {step.type === 'tool_call' && '🔧 '}
                {step.type === 'tool_result' && '📤 '}
                {step.type === 'text' && '💭 '}
                {step.name || step.type}
              </span>
              <pre
                className="mt-1 text-xs rounded p-2 whitespace-pre-wrap break-words overflow-hidden"
                style={{ backgroundColor: 'var(--nb-bg-output)', color: 'var(--nb-text-primary)' }}
              >
                {step.content.slice(0, 500)}
                {step.content.length > 500 && '...'}
              </pre>
            </div>
          ))}
        </div>
      </details>
    )
  }

  return (
    <div
      className="flex flex-col h-full"
      style={{
        backgroundColor: 'var(--nb-bg-secondary)',
        borderLeft: '1px solid var(--nb-border-default)',
      }}
    >
      {/* Header */}
      <div className="p-3" style={{ borderBottom: '1px solid var(--nb-border-default)' }}>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--nb-text-primary)' }}>AI Assistant</h2>
          <div className="flex items-center gap-2">
            <select
              value={llmProvider}
              onChange={(e) => onProviderChange(e.target.value)}
              className="text-xs rounded px-2 py-1"
              style={{
                backgroundColor: 'var(--nb-bg-cell)',
                border: '1px solid var(--nb-border-default)',
                color: 'var(--nb-text-secondary)',
              }}
            >
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <button
              onClick={onClearHistory}
              className="text-xs px-2 py-1 rounded hover:bg-red-500/20"
              style={{ color: 'var(--nb-text-muted)' }}
              title="Clear chat history"
            >
              Clear
            </button>
          </div>
        </div>

        {/* Tool mode */}
        <div className="flex items-center gap-2 text-xs">
          <span style={{ color: 'var(--nb-text-muted)' }}>Tools:</span>
          {(['auto', 'manual', 'ai_decide'] as const).map((mode) => (
            <label key={mode} className="flex items-center gap-1 cursor-pointer">
              <input
                type="radio"
                name="toolMode"
                value={mode}
                checked={toolMode === mode}
                onChange={() => onToolModeChange(mode)}
                className="w-3 h-3"
                style={{ accentColor: 'var(--nb-accent-code)' }}
              />
              <span style={{ color: toolMode === mode ? 'var(--nb-text-primary)' : 'var(--nb-text-muted)' }}>
                {mode === 'auto' ? 'Auto' : mode === 'manual' ? 'Approval' : 'AI Decides'}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4" style={{ backgroundColor: 'var(--nb-bg-secondary)' }}>
        {messages.length === 0 && !isLoading && (
          <div className="text-center py-8" style={{ color: 'var(--nb-text-muted)' }}>
            <p className="mb-2">Welcome! I can help with your notebook:</p>
            <ul className="text-sm space-y-1">
              <li>• Answer questions about selected cells</li>
              <li>• Write and edit code</li>
              <li>• Execute cells automatically</li>
              <li>• Create documentation</li>
            </ul>
            <p className="text-xs mt-4" style={{ color: 'var(--nb-text-muted)', opacity: 0.7 }}>
              Select cells with checkboxes to include in context.
            </p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`group flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className="flex items-start gap-1 max-w-[90%]">
              {/* Message content */}
              <div
                className="rounded-lg px-3 py-2"
                style={{
                  backgroundColor: msg.role === 'user' ? '#3b82f6' : 'var(--nb-bg-cell)',
                  color: msg.role === 'user' ? '#ffffff' : 'var(--nb-text-primary)',
                }}
              >
                {editingIndex === idx ? (
                  <div className="min-w-[200px]">
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      onKeyDown={handleEditKeyDown}
                      className="w-full text-sm rounded p-2 resize-none focus:outline-none"
                      style={{
                        backgroundColor: 'var(--nb-bg-output)',
                        color: 'var(--nb-text-primary)',
                      }}
                      rows={3}
                      autoFocus
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={saveEdit}
                        className="text-xs px-2 py-1 bg-green-600 hover:bg-green-500 text-white rounded"
                      >
                        Save
                      </button>
                      <button
                        onClick={cancelEditing}
                        className="text-xs px-2 py-1 bg-gray-600 hover:bg-gray-500 text-white rounded"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                    {msg.role === 'assistant' && msg.steps && renderSteps(msg.steps)}
                  </>
                )}
              </div>

              {/* Action buttons */}
              {editingIndex !== idx && (
                <div className="opacity-0 group-hover:opacity-100 flex flex-col gap-1 transition-opacity">
                  {/* Re-run button - only for last user message */}
                  {msg.role === 'user' && idx === lastUserMessageIndex && (
                    <button
                      onClick={() => onRerunMessage(idx)}
                      className="text-xs p-1 rounded"
                      style={{ color: 'var(--nb-text-muted)' }}
                      title="Re-run this message"
                    >
                      ↻
                    </button>
                  )}
                  {/* Edit button */}
                  <button
                    onClick={() => startEditing(idx, msg.content)}
                    className="text-xs p-1 rounded"
                    style={{ color: 'var(--nb-text-muted)' }}
                    title="Edit message"
                  >
                    ✎
                  </button>
                  {/* Delete button - only for user messages */}
                  {msg.role === 'user' && (
                    <button
                      onClick={() => onDeleteMessage(idx)}
                      className="text-xs p-1 rounded hover:text-red-400"
                      style={{ color: 'var(--nb-text-muted)' }}
                      title="Delete message and responses"
                    >
                      ×
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Tool approval UI */}
        {pendingTools.length > 0 && (
          <div
            className="rounded-lg p-3"
            style={{
              backgroundColor: 'var(--nb-bg-cell)',
              border: '1px solid var(--nb-accent-warning)',
            }}
          >
            <div className="text-sm font-medium mb-2" style={{ color: 'var(--nb-accent-warning)' }}>
              The assistant wants to use these tools:
            </div>
            <div className="space-y-2 mb-3">
              {pendingTools.map((tool) => (
                <div
                  key={tool.id}
                  className="flex items-start gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={selectedTools.has(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                    className="mt-1"
                    style={{ accentColor: 'var(--nb-accent-success)' }}
                  />
                  <div className="flex-1">
                    <div className="font-medium" style={{ color: 'var(--nb-text-primary)' }}>{tool.name}</div>
                    <details className="text-xs" style={{ color: 'var(--nb-text-muted)' }}>
                      <summary className="cursor-pointer">Arguments</summary>
                      <pre
                        className="mt-1 rounded p-2 whitespace-pre-wrap break-words overflow-hidden"
                        style={{ backgroundColor: 'var(--nb-bg-output)', color: 'var(--nb-text-primary)' }}
                      >
                        {JSON.stringify(tool.arguments, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleApprove}
                disabled={selectedTools.size === 0}
                className="flex-1 px-3 py-1.5 text-sm bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded"
              >
                Approve ({selectedTools.size})
              </button>
              <button
                onClick={onRejectTools}
                className="flex-1 px-3 py-1.5 text-sm bg-red-600 hover:bg-red-500 text-white rounded"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div
              className="rounded-lg px-3 py-2 flex items-center gap-2"
              style={{ backgroundColor: 'var(--nb-bg-cell)', color: 'var(--nb-text-muted)' }}
            >
              <div
                className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{ borderColor: 'var(--nb-accent-code)', borderTopColor: 'transparent' }}
              />
              Thinking...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-3" style={{ borderTop: '1px solid var(--nb-border-default)' }}>
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask AI for help... (Enter to send)"
            className="flex-1 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1"
            style={{
              backgroundColor: 'var(--nb-bg-cell)',
              border: '1px solid var(--nb-border-default)',
              color: 'var(--nb-text-primary)',
            }}
            rows={2}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex-shrink-0"
            title="Send message"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  )
}
