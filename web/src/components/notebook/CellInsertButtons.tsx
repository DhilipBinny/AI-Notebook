'use client'

import { useState } from 'react'
import { Plus, Lightbulb } from 'lucide-react'

interface CellInsertButtonsProps {
  onInsertCode: () => void
  onInsertMarkdown: () => void
  onInsertAI?: () => void
}

export default function CellInsertButtons({
  onInsertCode,
  onInsertMarkdown,
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
            color: 'var(--nb-bg-primary)',
          }}
          title="Insert Code cell"
        >
          <Plus className="w-3 h-3" />
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
            color: 'var(--nb-bg-primary)',
          }}
          title="Insert Markdown cell"
        >
          <Plus className="w-3 h-3" />
          Markdown
        </button>
        {onInsertAI && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onInsertAI()
            }}
            className="flex items-center gap-1 px-2 py-0.5 text-xs rounded hover:opacity-80 transition-colors"
            style={{
              backgroundColor: 'var(--nb-accent-ai)',
              color: 'white',
            }}
            title="Insert AI cell - ask questions about your notebook"
          >
            <Lightbulb className="w-3 h-3" />
            AI
          </button>
        )}
      </div>
    </div>
  )
}
