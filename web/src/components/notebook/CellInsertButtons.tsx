'use client'

import { useState } from 'react'

interface CellInsertButtonsProps {
  onInsertCode: () => void
  onInsertMarkdown: () => void
  onInsertNotes: () => void
  onInsertAI?: () => void
}

export default function CellInsertButtons({
  onInsertCode,
  onInsertMarkdown,
  onInsertNotes,
  onInsertAI,
}: CellInsertButtonsProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div
      className="relative h-6 flex items-center justify-center group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Hover line */}
      <div
        className={`absolute inset-x-4 h-[2px] transition-all duration-200 ${
          isHovered ? 'opacity-100' : 'opacity-0'
        }`}
        style={{ backgroundColor: 'var(--nb-border-selected)' }}
      />

      {/* Buttons container */}
      <div
        className={`flex items-center gap-1 px-2 py-1 rounded-full transition-all duration-200 z-10 ${
          isHovered ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
        }`}
        style={{
          backgroundColor: 'var(--nb-bg-cell)',
          border: '1px solid var(--nb-border-default)',
        }}
      >
        <button
          onClick={(e) => {
            e.stopPropagation()
            onInsertCode()
          }}
          className="flex items-center gap-1 px-2 py-0.5 text-xs rounded hover:opacity-80 transition-colors"
          style={{
            backgroundColor: 'var(--nb-accent-code)',
            color: '#11111b',
          }}
          title="Insert Code cell"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Code
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onInsertMarkdown()
          }}
          className="flex items-center gap-1 px-2 py-0.5 text-xs rounded hover:opacity-80 transition-colors"
          style={{
            backgroundColor: 'var(--nb-accent-markdown)',
            color: '#11111b',
          }}
          title="Insert Markdown cell"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Markdown
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onInsertNotes()
          }}
          className="flex items-center gap-1 px-2 py-0.5 text-xs rounded hover:opacity-80 transition-colors"
          style={{
            backgroundColor: 'var(--nb-accent-notes)',
            color: '#11111b',
          }}
          title="Insert Notes cell"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Notes
        </button>
        {onInsertAI && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onInsertAI()
            }}
            className="flex items-center gap-1 px-2 py-0.5 text-xs rounded hover:opacity-80 transition-colors"
            style={{
              backgroundColor: '#a855f7',
              color: '#ffffff',
            }}
            title="Insert AI cell - ask questions about your notebook"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            AI
          </button>
        )}
      </div>
    </div>
  )
}
