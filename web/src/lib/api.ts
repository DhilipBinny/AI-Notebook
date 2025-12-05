import axios from 'axios'
import type { User, Project, Workspace, Playground, AuthTokens, ChatMessage } from '@/types'

// Types for chat API - now just cell IDs (backend loads content from S3)

interface PendingToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
  validation_reason?: string
}

interface LLMStep {
  type: 'tool_call' | 'tool_result' | 'text'
  name?: string
  content: string
  timestamp?: string
}

interface ChatResponse {
  success: boolean
  response: string
  error?: string
  pending_tool_calls: PendingToolCall[]
  steps: LLMStep[]
  updates: Record<string, unknown>[]
}

interface ChatHistoryResponse {
  success: boolean
  project_id: string
  messages: ChatMessage[]
}

// Types for notebook API
interface NotebookCell {
  id?: string
  type?: string
  cell_type?: string  // Jupyter standard format
  source: string
  outputs: Record<string, unknown>[]
  execution_count?: number
  metadata?: Record<string, unknown>
}

interface NotebookData {
  cells: NotebookCell[]
  metadata: Record<string, unknown>
  nbformat: number
  nbformat_minor: number
}

interface NotebookResponse {
  project_id: string
  notebook: NotebookData
  last_modified: string
  version: number
}

interface NotebookSaveResult {
  success: boolean
  version: number
  saved_at: string
  size_bytes: number
}

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/auth/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const auth = {
  register: async (email: string, password: string): Promise<AuthTokens> => {
    const { data } = await api.post('/auth/register', { email, password })
    return data
  },

  login: async (email: string, password: string): Promise<AuthTokens> => {
    const { data } = await api.post('/auth/login', { email, password })
    return data
  },

  logout: async (): Promise<void> => {
    const refreshToken = localStorage.getItem('refresh_token')
    if (refreshToken) {
      await api.post('/auth/logout', { refresh_token: refreshToken })
    }
  },

  getMe: async (): Promise<User> => {
    const { data } = await api.get('/users/me')
    return data
  },
}

// Projects API
export const projects = {
  list: async (): Promise<{ projects: Project[]; total: number }> => {
    const { data } = await api.get('/projects')
    return data
  },

  get: async (id: string): Promise<Project> => {
    const { data } = await api.get(`/projects/${id}`)
    return data
  },

  create: async (project: { name: string; description?: string; workspace_id?: string }): Promise<Project> => {
    const { data } = await api.post('/projects', project)
    return data
  },

  update: async (id: string, project: Partial<Project>): Promise<Project> => {
    const { data } = await api.patch(`/projects/${id}`, project)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/projects/${id}`)
  },
}

// Workspaces API
export const workspaces = {
  list: async (): Promise<{ workspaces: Workspace[]; uncategorized_count: number }> => {
    const { data } = await api.get('/workspaces')
    return data
  },

  get: async (id: string): Promise<Workspace> => {
    const { data } = await api.get(`/workspaces/${id}`)
    return data
  },

  create: async (workspace: { name: string; description?: string; color?: string; icon?: string }): Promise<Workspace> => {
    const { data } = await api.post('/workspaces', workspace)
    return data
  },

  update: async (id: string, workspace: Partial<Workspace>): Promise<Workspace> => {
    const { data } = await api.patch(`/workspaces/${id}`, workspace)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/workspaces/${id}`)
  },

  moveProject: async (workspaceId: string, projectId: string): Promise<void> => {
    await api.post(`/workspaces/${workspaceId}/projects/${projectId}`)
  },

  removeProject: async (workspaceId: string, projectId: string): Promise<void> => {
    await api.delete(`/workspaces/${workspaceId}/projects/${projectId}`)
  },
}

// Playground API
export const playgrounds = {
  get: async (projectId: string): Promise<Playground | null> => {
    const { data } = await api.get(`/projects/${projectId}/playground`)
    return data
  },

  start: async (projectId: string): Promise<{ playground: Playground; message: string }> => {
    const { data } = await api.post(`/projects/${projectId}/playground/start`)
    return data
  },

  stop: async (projectId: string): Promise<{ message: string }> => {
    const { data } = await api.post(`/projects/${projectId}/playground/stop`)
    return data
  },

  getLogs: async (projectId: string, tail = 100): Promise<{ logs: string }> => {
    const { data } = await api.get(`/projects/${projectId}/playground/logs?tail=${tail}`)
    return data
  },

  updateActivity: async (projectId: string): Promise<void> => {
    await api.post(`/projects/${projectId}/playground/activity`)
  },
}

// Chat API
export const chat = {
  getHistory: async (projectId: string): Promise<ChatHistoryResponse> => {
    const { data } = await api.get(`/projects/${projectId}/chat`)
    return data
  },

  saveHistory: async (projectId: string, messages: ChatMessage[]): Promise<{ success: boolean }> => {
    const { data } = await api.post(`/projects/${projectId}/chat/history`, { messages })
    return data
  },

  sendMessage: async (
    projectId: string,
    message: string,
    contextCellIds: string[],
    toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
    llmProvider: string = 'gemini',
    contextFormat: 'xml' | 'plain' = 'xml'
  ): Promise<ChatResponse> => {
    const { data } = await api.post(`/projects/${projectId}/chat?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
      message,
      context_cell_ids: contextCellIds,
    })
    return data
  },

  executeTools: async (
    projectId: string,
    approvedTools: PendingToolCall[],
    toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
    llmProvider: string = 'gemini',
    contextFormat: 'xml' | 'plain' = 'xml'
  ): Promise<ChatResponse> => {
    const { data } = await api.post(`/projects/${projectId}/chat/execute-tools?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
      approved_tools: approvedTools,
    })
    return data
  },

  clearHistory: async (projectId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}/chat`)
  },

  runAICell: async (
    projectId: string,
    prompt: string,
    contextCellIds: string[],
    llmProvider: string = 'gemini',
    aiCellId?: string,
    aiCellIndex?: number,
    contextFormat: 'xml' | 'plain' = 'xml'
  ): Promise<{ success: boolean; response: string; model: string; error?: string }> => {
    const { data } = await api.post(`/projects/${projectId}/chat/ai-cell/run?llm_provider=${llmProvider}&context_format=${contextFormat}`, {
      prompt,
      context_cell_ids: contextCellIds,
      ai_cell_id: aiCellId,
      ai_cell_index: aiCellIndex,
    })
    return data
  },
}

// Notebook API
export const notebooks = {
  get: async (projectId: string, version?: number): Promise<NotebookResponse> => {
    const url = version
      ? `/projects/${projectId}/notebook?version=${version}`
      : `/projects/${projectId}/notebook`
    const { data } = await api.get(url)
    return data
  },

  save: async (projectId: string, cells: NotebookCell[]): Promise<NotebookSaveResult> => {
    const { data } = await api.put(`/projects/${projectId}/notebook`, { cells })
    return data
  },

  listVersions: async (projectId: string): Promise<{ version: number; saved_at: string; size_bytes: number }[]> => {
    const { data } = await api.get(`/projects/${projectId}/notebook/versions`)
    return data
  },

  export: async (projectId: string): Promise<Record<string, unknown>> => {
    const { data } = await api.post(`/projects/${projectId}/notebook/export`)
    return data
  },

  import: async (projectId: string, ipynbData: Record<string, unknown>): Promise<{ success: boolean; version: number; cells_imported: number }> => {
    const { data } = await api.post(`/projects/${projectId}/notebook/import`, { ipynb_data: ipynbData })
    return data
  },

  summarize: async (projectId: string, llmProvider: string = 'gemini'): Promise<{ success: boolean; summary: string; error?: string }> => {
    const { data } = await api.post(`/projects/${projectId}/notebook/summarize?llm_provider=${llmProvider}`)
    return data
  },
  // Note: syncToPlayground removed - LLM tools now fetch from Master API directly
}

export default api
