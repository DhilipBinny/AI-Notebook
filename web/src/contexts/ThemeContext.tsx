'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

export type NotebookTheme = 'dark' | 'light' | 'monokai'

interface ThemeContextType {
  theme: NotebookTheme
  setTheme: (theme: NotebookTheme) => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<NotebookTheme>('dark')

  // Load theme from localStorage on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('notebook-theme') as NotebookTheme
    if (savedTheme && ['dark', 'light', 'monokai'].includes(savedTheme)) {
      setTheme(savedTheme)
    }
  }, [])

  // Save theme to localStorage and apply to document
  useEffect(() => {
    localStorage.setItem('notebook-theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
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

// Theme color definitions for use in components
export const themeColors = {
  dark: {
    name: 'Dark',
    // Background colors
    bg: {
      primary: '#1e1e2e',
      secondary: '#181825',
      cell: '#1e1e2e',
      codeCell: '#11111b',
      markdownCell: '#1e1e2e',
      output: '#11111b',
      header: '#181825',
    },
    // Border colors
    border: {
      default: '#313244',
      selected: '#89b4fa',
      code: '#45475a',
      markdown: '#6c7086',
    },
    // Text colors
    text: {
      primary: '#cdd6f4',
      secondary: '#a6adc8',
      muted: '#6c7086',
      code: '#89dceb',
      markdown: '#cdd6f4',
    },
    // Accent colors
    accent: {
      code: '#89b4fa',
      markdown: '#cba6f7',
      success: '#a6e3a1',
      error: '#f38ba8',
      warning: '#f9e2af',
    },
  },
  light: {
    name: 'Light',
    bg: {
      primary: '#ffffff',
      secondary: '#f8f9fa',
      cell: '#ffffff',
      codeCell: '#f7f7f7',
      markdownCell: '#ffffff',
      output: '#f5f5f5',
      header: '#f8f9fa',
    },
    border: {
      default: '#e0e0e0',
      selected: '#2196f3',
      code: '#e3e3e3',
      markdown: '#d0d0d0',
    },
    text: {
      primary: '#212121',
      secondary: '#616161',
      muted: '#9e9e9e',
      code: '#0d47a1',
      markdown: '#212121',
    },
    accent: {
      code: '#1976d2',
      markdown: '#7b1fa2',
      success: '#388e3c',
      error: '#d32f2f',
      warning: '#f57c00',
    },
  },
  monokai: {
    name: 'Monokai',
    bg: {
      primary: '#272822',
      secondary: '#1e1f1c',
      cell: '#272822',
      codeCell: '#1e1f1c',
      markdownCell: '#2d2e27',
      output: '#1e1f1c',
      header: '#1e1f1c',
    },
    border: {
      default: '#49483e',
      selected: '#f92672',
      code: '#49483e',
      markdown: '#75715e',
    },
    text: {
      primary: '#f8f8f2',
      secondary: '#cfcfc2',
      muted: '#75715e',
      code: '#a6e22e',
      markdown: '#f8f8f2',
    },
    accent: {
      code: '#66d9ef',
      markdown: '#ae81ff',
      success: '#a6e22e',
      error: '#f92672',
      warning: '#e6db74',
    },
  },
}
