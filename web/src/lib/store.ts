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
  dirtyCellIds: Set<string>  // Track which specific cells have unsaved local changes
  setCells: (cells: Cell[]) => void
  setSelectedCell: (id: string | null) => void
  addCell: (cell: Cell, index?: number) => void
  updateCell: (id: string, updates: Partial<Cell>) => void
  // Functional update for ai_data - gets fresh cell state to avoid stale closures
  updateCellAiData: (id: string, updater: (currentCell: Cell) => Partial<Cell['ai_data']>) => void
  updateCellFromServer: (id: string, updates: Partial<Cell>) => void  // Update without marking dirty
  deleteCell: (id: string) => void
  deleteCellFromServer: (id: string) => void  // Delete without marking dirty
  moveCell: (id: string, direction: 'up' | 'down') => void
  setDirty: (dirty: boolean) => void
  markCellClean: (id: string) => void  // Mark specific cell as saved
  isCellDirty: (id: string) => boolean  // Check if specific cell has unsaved changes
}

export const useNotebookStore = create<NotebookState>((set, get) => ({
  cells: [],
  selectedCellId: null,
  isDirty: false,
  dirtyCellIds: new Set<string>(),
  setCells: (cells) => set({ cells, isDirty: false, dirtyCellIds: new Set<string>() }),
  setSelectedCell: (selectedCellId) => set({ selectedCellId }),
  addCell: (cell, index) =>
    set((state) => {
      const newCells = [...state.cells]
      if (index !== undefined) {
        newCells.splice(index, 0, cell)
      } else {
        newCells.push(cell)
      }
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.add(cell.id)
      return { cells: newCells, isDirty: true, dirtyCellIds: newDirtyCellIds }
    }),
  updateCell: (id, updates) =>
    set((state) => {
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.add(id)
      return {
        cells: state.cells.map((c) => (c.id === id ? { ...c, ...updates } : c)),
        isDirty: true,
        dirtyCellIds: newDirtyCellIds,
      }
    }),
  // Functional update for ai_data - avoids stale closure issues in SSE callbacks
  updateCellAiData: (id, updater) =>
    set((state) => {
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.add(id)
      return {
        cells: state.cells.map((c): Cell => {
          if (c.id !== id) return c
          const aiDataUpdates = updater(c)
          // Merge with existing ai_data, ensuring required fields have defaults
          const existingAiData = c.ai_data || { user_prompt: '', llm_response: '', status: 'idle' as const }
          return {
            ...c,
            ai_data: { ...existingAiData, ...aiDataUpdates } as Cell['ai_data']
          }
        }),
        isDirty: true,
        dirtyCellIds: newDirtyCellIds,
      }
    }),
  // Update cell from server (WebSocket) - doesn't mark as dirty, only updates if cell isn't locally dirty
  updateCellFromServer: (id, updates) =>
    set((state) => {
      // If cell has local unsaved changes, don't overwrite with server data
      if (state.dirtyCellIds.has(id)) {
        console.log(`[Store] Skipping server update for dirty cell ${id}`)
        return state
      }
      return {
        cells: state.cells.map((c) => (c.id === id ? { ...c, ...updates } : c)),
      }
    }),
  deleteCell: (id) =>
    set((state) => {
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.delete(id)  // Remove from dirty set since it's deleted
      return {
        cells: state.cells.filter((c) => c.id !== id),
        isDirty: true,
        dirtyCellIds: newDirtyCellIds,
      }
    }),
  // Delete cell from server (WebSocket) - doesn't mark notebook as dirty
  deleteCellFromServer: (id) =>
    set((state) => {
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.delete(id)
      return {
        cells: state.cells.filter((c) => c.id !== id),
        dirtyCellIds: newDirtyCellIds,
      }
    }),
  moveCell: (id, direction) =>
    set((state) => {
      const idx = state.cells.findIndex((c) => c.id === id)
      if (idx === -1) return state
      const newIdx = direction === 'up' ? idx - 1 : idx + 1
      if (newIdx < 0 || newIdx >= state.cells.length) return state
      const newCells = [...state.cells]
      ;[newCells[idx], newCells[newIdx]] = [newCells[newIdx], newCells[idx]]
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.add(id)
      return { cells: newCells, isDirty: true, dirtyCellIds: newDirtyCellIds }
    }),
  setDirty: (isDirty) => set((state) => ({
    isDirty,
    dirtyCellIds: isDirty ? state.dirtyCellIds : new Set<string>()
  })),
  markCellClean: (id) =>
    set((state) => {
      const newDirtyCellIds = new Set(state.dirtyCellIds)
      newDirtyCellIds.delete(id)
      return {
        dirtyCellIds: newDirtyCellIds,
        isDirty: newDirtyCellIds.size > 0,
      }
    }),
  isCellDirty: (id) => get().dirtyCellIds.has(id),
}))
