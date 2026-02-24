'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export type NotebookTheme = 'dark' | 'light'
export type DensityMode = 'standard' | 'cozy' | 'compact'

// Theme metadata for dropdown display
export const themeOptions: { value: NotebookTheme; label: string; description: string }[] = [
  { value: 'dark', label: 'Dark', description: 'Cozy dark theme with warm accents' },
  { value: 'light', label: 'Light', description: 'Clean modern light theme' },
]

// Density mode metadata for dropdown display
export const densityOptions: { value: DensityMode; label: string; description: string }[] = [
  { value: 'standard', label: 'Standard', description: 'Balanced readability (default)' },
  { value: 'cozy', label: 'Cozy', description: 'Larger text for reading/tutorials' },
  { value: 'compact', label: 'Compact', description: 'Dense layout for data analysis' },
]

interface ThemeContextType {
  theme: NotebookTheme
  setTheme: (theme: NotebookTheme) => void
  density: DensityMode
  setDensity: (density: DensityMode) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const validThemes: NotebookTheme[] = ['dark', 'light']
const validDensities: DensityMode[] = ['standard', 'cozy', 'compact']

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<NotebookTheme>('dark')
  const [density, setDensity] = useState<DensityMode>('standard')

  // Load theme and density from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('notebook-theme') as NotebookTheme
    if (savedTheme && validThemes.includes(savedTheme)) {
      setTheme(savedTheme)
    }
    const savedDensity = localStorage.getItem('notebook-density') as DensityMode
    if (savedDensity && validDensities.includes(savedDensity)) {
      setDensity(savedDensity)
    }
  }, [])

  // Save theme to localStorage and apply to document
  useEffect(() => {
    localStorage.setItem('notebook-theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // Save density to localStorage and apply to document
  useEffect(() => {
    localStorage.setItem('notebook-density', density)
    // Only set data-density for non-standard modes
    if (density === 'standard') {
      document.documentElement.removeAttribute('data-density')
    } else {
      document.documentElement.setAttribute('data-density', density)
    }
  }, [density])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, density, setDensity }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

// Theme color definitions for use in components (Catppuccin Mocha & Solarized Light)
export const themeColors = {
  dark: {
    name: 'Dark (Catppuccin)',
    // Background colors
    bg: {
      primary: '#1e1e2e',
      secondary: '#313244',
      tertiary: '#181825',
      cell: '#1e1e2e',
      codeCell: '#181825',
      markdownCell: '#1e1e2e',
      output: '#11111b',
      header: '#313244',
      card: 'rgba(255, 255, 255, 0.05)',
      input: 'rgba(255, 255, 255, 0.05)',
      aiCell: '#2a2a2e',
    },
    // Border colors
    border: {
      default: '#45475a',
      subtle: 'rgba(255, 255, 255, 0.05)',
      selected: '#89b4fa',
      code: '#45475a',
      markdown: '#45475a',
      focus: '#89b4fa',
    },
    // Text colors
    text: {
      primary: '#cdd6f4',
      secondary: '#bac2de',
      muted: '#7f849c',
      code: '#89b4fa',
      markdown: '#cdd6f4',
      placeholder: '#7f849c',
    },
    // Accent colors (Catppuccin Mocha palette)
    accent: {
      primary: '#89b4fa',    // Blue
      secondary: '#94e2d5',  // Teal
      code: '#89b4fa',       // Blue
      markdown: '#cba6f7',   // Mauve
      success: '#a6e3a1',    // Green
      error: '#f38ba8',      // Red
      warning: '#fab387',    // Peach
      info: '#89dceb',       // Sky
      ai: '#a8a29e',         // Stone 400
    },
    // Syntax highlighting
    syntax: {
      keyword: '#cba6f7',    // Mauve
      string: '#a6e3a1',     // Green
      number: '#fab387',     // Peach
      comment: '#7f849c',    // Overlay0
      function: '#89b4fa',   // Blue
      variable: '#cdd6f4',   // Text
      operator: '#f38ba8',   // Red
      class: '#f9e2af',      // Yellow
    },
  },
  light: {
    name: 'Light (Clean)',
    bg: {
      primary: '#f8fafc',
      secondary: '#f1f5f9',
      tertiary: '#e2e8f0',
      cell: '#ffffff',
      codeCell: '#ffffff',
      markdownCell: '#ffffff',
      output: '#f8fafc',
      header: '#f1f5f9',
      card: 'rgba(255, 255, 255, 0.8)',
      input: '#ffffff',
      aiCell: '#fafaf9',
    },
    border: {
      default: '#e2e8f0',
      subtle: 'rgba(148, 163, 184, 0.2)',
      selected: '#3b82f6',
      code: '#e2e8f0',
      markdown: '#e2e8f0',
      focus: '#3b82f6',
    },
    text: {
      primary: '#1e293b',
      secondary: '#475569',
      muted: '#94a3b8',
      code: '#2563eb',
      markdown: '#1e293b',
      placeholder: '#94a3b8',
    },
    // Accent colors (Modern Tailwind palette)
    accent: {
      primary: '#3b82f6',    // Blue 500
      secondary: '#14b8a6',  // Teal 500
      code: '#2563eb',       // Blue 600
      markdown: '#7c3aed',   // Violet 600
      success: '#22c55e',    // Green 500
      error: '#ef4444',      // Red 500
      warning: '#f59e0b',    // Amber 500
      info: '#0ea5e9',       // Sky 500
      ai: '#78716c',         // Stone 500
    },
    // Syntax highlighting
    syntax: {
      keyword: '#7c3aed',    // Violet
      string: '#16a34a',     // Green
      number: '#0891b2',     // Cyan
      comment: '#94a3b8',    // Slate 400
      function: '#2563eb',   // Blue
      variable: '#1e293b',   // Slate 800
      operator: '#dc2626',   // Red
      class: '#d97706',      // Amber
    },
  },
}
