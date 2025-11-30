import { create } from 'zustand'
import type { User, Project, Cell } from '@/types'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({ user: null, isAuthenticated: false })
  },
}))

interface ProjectsState {
  projects: Project[]
  currentProject: Project | null
  isLoading: boolean
  setProjects: (projects: Project[]) => void
  setCurrentProject: (project: Project | null) => void
  setLoading: (loading: boolean) => void
  addProject: (project: Project) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  removeProject: (id: string) => void
}

export const useProjectsStore = create<ProjectsState>((set) => ({
  projects: [],
  currentProject: null,
  isLoading: false,
  setProjects: (projects) => set({ projects }),
  setCurrentProject: (currentProject) => set({ currentProject }),
  setLoading: (isLoading) => set({ isLoading }),
  addProject: (project) =>
    set((state) => ({ projects: [project, ...state.projects] })),
  updateProject: (id, updates) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === id ? { ...p, ...updates } : p
      ),
      currentProject:
        state.currentProject?.id === id
          ? { ...state.currentProject, ...updates }
          : state.currentProject,
    })),
  removeProject: (id) =>
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      currentProject:
        state.currentProject?.id === id ? null : state.currentProject,
    })),
}))

interface NotebookState {
  cells: Cell[]
  selectedCellId: string | null
  isDirty: boolean
  setCells: (cells: Cell[]) => void
  setSelectedCell: (id: string | null) => void
  addCell: (cell: Cell, index?: number) => void
  updateCell: (id: string, updates: Partial<Cell>) => void
  deleteCell: (id: string) => void
  moveCell: (id: string, direction: 'up' | 'down') => void
  setDirty: (dirty: boolean) => void
}

export const useNotebookStore = create<NotebookState>((set) => ({
  cells: [],
  selectedCellId: null,
  isDirty: false,
  setCells: (cells) => set({ cells, isDirty: false }),
  setSelectedCell: (selectedCellId) => set({ selectedCellId }),
  addCell: (cell, index) =>
    set((state) => {
      const newCells = [...state.cells]
      if (index !== undefined) {
        newCells.splice(index, 0, cell)
      } else {
        newCells.push(cell)
      }
      return { cells: newCells, isDirty: true }
    }),
  updateCell: (id, updates) =>
    set((state) => ({
      cells: state.cells.map((c) => (c.id === id ? { ...c, ...updates } : c)),
      isDirty: true,
    })),
  deleteCell: (id) =>
    set((state) => ({
      cells: state.cells.filter((c) => c.id !== id),
      isDirty: true,
    })),
  moveCell: (id, direction) =>
    set((state) => {
      const idx = state.cells.findIndex((c) => c.id === id)
      if (idx === -1) return state
      const newIdx = direction === 'up' ? idx - 1 : idx + 1
      if (newIdx < 0 || newIdx >= state.cells.length) return state
      const newCells = [...state.cells]
      ;[newCells[idx], newCells[newIdx]] = [newCells[newIdx], newCells[idx]]
      return { cells: newCells, isDirty: true }
    }),
  setDirty: (isDirty) => set({ isDirty }),
}))
