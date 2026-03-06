import axios from 'axios'
import type { User, Project, Workspace, Playground, AuthTokens, ChatMessage, ImageInput, Invitation, InvitationDetail, ApiKey, ProviderInfo, CreditBalance, UsageRecord, LLMModel, LLMModelBrief, LLMModelGrouped, NotebookTemplate, PlatformKey, SystemPrompt, AdminUser, AdminUserDetail, AdminUserListResponse, AICellMode } from '@/types'
import { hashPassword } from '@/lib/crypto'

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
  timeout: 300000,  // 5 minutes - matches backend timeout for LLM requests
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// Handle 401 errors with token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If error is 401 and we haven't tried to refresh yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh if this was the refresh request itself
      if (originalRequest.url === '/auth/refresh') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/auth/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')

      if (!refreshToken) {
        // No refresh token, redirect to login
        localStorage.removeItem('access_token')
        window.location.href = '/auth/login'
        return Promise.reject(error)
      }

      try {
        // Call refresh endpoint
        const { data } = await axios.post('/api/auth/refresh', {
          refresh_token: refreshToken,
        })

        // Store new tokens
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)

        // Update authorization header
        api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`

        // Process queued requests
        processQueue(null, data.access_token)

        // Retry the original request
        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed, redirect to login
        processQueue(refreshError, null)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/auth/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// Auth API
export const auth = {
  register: async (email: string, password: string, invite_code?: string): Promise<AuthTokens> => {
    const hashedPassword = await hashPassword(password)
    const { data } = await api.post('/auth/register', { email, password: hashedPassword, invite_code })
    return data
  },

  login: async (email: string, password: string): Promise<AuthTokens> => {
    const hashedPassword = await hashPassword(password)
    const { data } = await api.post('/auth/login', { email, password: hashedPassword })
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

  forgotPassword: async (email: string, base_url: string): Promise<{ message: string }> => {
    const { data } = await api.post('/auth/forgot-password', { email, base_url })
    return data
  },

  validateResetToken: async (token: string): Promise<{ valid: boolean; email: string }> => {
    const { data } = await api.post('/auth/validate-reset-token', { token })
    return data
  },

  resetPassword: async (token: string, newPassword: string): Promise<{ message: string }> => {
    const hashedPassword = await hashPassword(newPassword)
    const { data } = await api.post('/auth/reset-password', { token, new_password: hashedPassword })
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

// Playground API (user-scoped - one container per user)
export const playgrounds = {
  // Get current user's playground status
  getStatus: async (): Promise<Playground | null> => {
    try {
      const { data } = await api.get('/playground')
      return data
    } catch {
      return null
    }
  },

  // Start playground with a project
  start: async (projectId: string): Promise<{ playground: Playground; message: string }> => {
    const { data } = await api.post('/playground/start', { project_id: projectId })
    return data
  },

  // Stop playground
  stop: async (): Promise<{ message: string }> => {
    const { data } = await api.post('/playground/stop')
    return data
  },

  // Switch active project (without restart)
  switchProject: async (projectId: string): Promise<{ playground: Playground; message: string }> => {
    const { data } = await api.post('/playground/switch', { project_id: projectId })
    return data
  },

  // Get container logs
  getLogs: async (tail = 100): Promise<{ logs: string }> => {
    const { data } = await api.get(`/playground/logs?tail=${tail}`)
    return data
  },

  // Update activity timestamp
  updateActivity: async (): Promise<void> => {
    await api.post('/playground/activity')
  },

  // Legacy project-scoped endpoints (for backward compatibility)
  get: async (projectId: string): Promise<Playground | null> => {
    const { data } = await api.get(`/projects/${projectId}/playground`)
    return data
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

  // DEPRECATED: Use sendMessageWithSSE() instead - JSON endpoint replaced by SSE streaming
  // sendMessage: async (
  //   projectId: string,
  //   message: string,
  //   contextCellIds: string[],
  //   toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
  //   llmProvider: string = 'gemini',
  //   contextFormat: 'xml' | 'json' | 'plain' = 'xml',
  //   images?: ImageInput[]
  // ): Promise<ChatResponse> => {
  //   const { data } = await api.post(`/projects/${projectId}/chat?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
  //     message,
  //     context_cell_ids: contextCellIds,
  //     images,
  //   })
  //   return data
  // },

  // DEPRECATED: Use executeToolsWithSSE() instead - JSON endpoint replaced by SSE streaming
  // executeTools: async (
  //   projectId: string,
  //   approvedTools: PendingToolCall[],
  //   toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
  //   llmProvider: string = 'gemini',
  //   contextFormat: 'xml' | 'json' | 'plain' = 'xml'
  // ): Promise<ChatResponse> => {
  //   const { data } = await api.post(`/projects/${projectId}/chat/execute-tools?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
  //     approved_tools: approvedTools,
  //   })
  //   return data
  // },

  clearHistory: async (projectId: string): Promise<void> => {
    await api.delete(`/projects/${projectId}/chat`)
  },

  // SSE Streaming version of sendMessage - provides real-time progress events
  sendMessageWithSSE: (
    projectId: string,
    message: string,
    contextCellIds: string[],
    sessionId: string,
    toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
    llmProvider: string = 'gemini',
    contextFormat: 'xml' | 'json' | 'plain' = 'xml',
    images?: ImageInput[],
    onEvent?: (event: { type: string; data: Record<string, unknown> }) => void,
    onDone?: (result: ChatResponse & { has_pending_tools?: boolean }) => void,
    onError?: (error: string) => void
  ): AbortController => {
    const controller = new AbortController()
    const token = localStorage.getItem('access_token')

    const body = JSON.stringify({
      message,
      context_cell_ids: contextCellIds,
      session_id: sessionId,
      tool_mode: toolMode,
      images: images || undefined,
    })

    fetch(`/api/projects/${projectId}/chat/stream?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body,
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''
        let currentData = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7)
            } else if (line.startsWith('data: ')) {
              currentData = line.slice(6)
            } else if (line === '' && currentEvent && currentData) {
              try {
                const data = JSON.parse(currentData)

                if (currentEvent === 'done') {
                  onDone?.({
                    success: data.success ?? true,
                    response: data.response || '',
                    pending_tool_calls: data.pending_tool_calls || [],
                    steps: data.steps || [],
                    updates: data.updates || [],
                    has_pending_tools: data.has_pending_tools || false,
                  })
                } else if (currentEvent === 'error') {
                  onError?.(data.error || 'Unknown error')
                } else {
                  console.log('[Chat SSE] Event:', currentEvent, data)
                  onEvent?.({ type: currentEvent, data })
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', currentData, e)
              }

              currentEvent = ''
              currentData = ''
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err.message || 'Connection failed')
        }
      })

    return controller
  },

  // SSE Streaming version of executeTools - provides real-time progress events
  executeToolsWithSSE: (
    projectId: string,
    approvedTools: PendingToolCall[],
    sessionId: string,
    toolMode: 'auto' | 'manual' | 'ai_decide' = 'manual',
    llmProvider: string = 'gemini',
    contextFormat: 'xml' | 'json' | 'plain' = 'xml',
    onEvent?: (event: { type: string; data: Record<string, unknown> }) => void,
    onDone?: (result: ChatResponse & { has_pending_tools?: boolean }) => void,
    onError?: (error: string) => void
  ): AbortController => {
    const controller = new AbortController()
    const token = localStorage.getItem('access_token')

    const body = JSON.stringify({
      session_id: sessionId,
      approved_tools: approvedTools,
    })

    fetch(`/api/projects/${projectId}/chat/execute-tools/stream?tool_mode=${toolMode}&llm_provider=${llmProvider}&context_format=${contextFormat}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body,
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''
        let currentData = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7)
            } else if (line.startsWith('data: ')) {
              currentData = line.slice(6)
            } else if (line === '' && currentEvent && currentData) {
              try {
                const data = JSON.parse(currentData)

                if (currentEvent === 'done') {
                  onDone?.({
                    success: data.success ?? true,
                    response: data.response || '',
                    pending_tool_calls: data.pending_tool_calls || [],
                    steps: data.steps || [],
                    updates: data.updates || [],
                    has_pending_tools: data.has_pending_tools || false,
                  })
                } else if (currentEvent === 'error') {
                  onError?.(data.error || 'Unknown error')
                } else {
                  console.log('[Chat Execute SSE] Event:', currentEvent, data)
                  onEvent?.({ type: currentEvent, data })
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', currentData, e)
              }

              currentEvent = ''
              currentData = ''
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err.message || 'Connection failed')
        }
      })

    return controller
  },

  // Run AI Cell with unified SSE streaming response
  // The backend always returns SSE events - real-time progress depends on playground config
  runAICell: (
    projectId: string,
    prompt: string,
    contextCellIds: string[],
    llmProvider: string = 'gemini',
    aiCellId?: string,
    aiCellIndex?: number,
    contextFormat: 'xml' | 'json' | 'plain' = 'xml',
    images?: { data: string; mime_type: string; filename?: string }[],
    onEvent?: (event: { type: string; data: Record<string, unknown> }) => void,
    onDone?: (result: { success: boolean; response: string; model: string; steps: LLMStep[]; cancelled?: boolean; thinking?: string }) => void,
    onError?: (error: string) => void,
    mode?: string
  ): AbortController => {
    const controller = new AbortController()
    const token = localStorage.getItem('access_token')

    // Build request body
    const body = JSON.stringify({
      prompt,
      context_cell_ids: contextCellIds,
      ai_cell_id: aiCellId,
      ai_cell_index: aiCellIndex,
      images: images || undefined,
    })

    // Use fetch with streaming response (unified endpoint - always returns SSE)
    const modeParam = mode ? `&mode=${encodeURIComponent(mode)}` : ''
    fetch(`/api/projects/${projectId}/chat/ai-cell/run?llm_provider=${llmProvider}&context_format=${contextFormat}${modeParam}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body,
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('No response body')
        }

        const decoder = new TextDecoder()
        let buffer = ''
        // Track current event and data across read() chunks
        let currentEvent = ''
        let currentData = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Parse SSE events from buffer
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7)
            } else if (line.startsWith('data: ')) {
              currentData = line.slice(6)
            } else if (line === '' && currentEvent && currentData) {
              // End of event, process it
              try {
                const data = JSON.parse(currentData)

                if (currentEvent === 'done') {
                  onDone?.({
                    success: data.success ?? true,
                    response: data.response || '',
                    model: data.model || llmProvider,
                    steps: data.steps || [],
                    cancelled: data.cancelled,
                    thinking: data.thinking || undefined,
                  })
                } else if (currentEvent === 'error') {
                  onError?.(data.error || 'Unknown error')
                } else {
                  console.log('[API] SSE event received:', currentEvent, data)
                  onEvent?.({ type: currentEvent, data })
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', currentData, e)
              }

              currentEvent = ''
              currentData = ''
            }
          }
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err.message || 'Connection failed')
        }
      })

    return controller
  },

  cancelAICell: async (projectId: string): Promise<{ success: boolean; message: string }> => {
    const { data } = await api.post(`/projects/${projectId}/chat/ai-cell/cancel`)
    return data
  },

  getAICellModes: async (): Promise<AICellMode[]> => {
    const { data } = await api.get('/ai-cell-modes')
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

// File info from backend
interface FileInfo {
  name: string
  path: string
  size: number
  is_directory: boolean
  modified_at: string | null
}

interface FileListResponse {
  success: boolean
  project_id: string
  files: FileInfo[]
  total_size: number
}

interface FileUploadResponse {
  success: boolean
  project_id: string
  files: { name: string; path: string; size: number }[]
  message: string
}

interface FileSaveResponse {
  success: boolean
  project_id: string
  files_saved: number
  total_size: number
  message: string
}

interface FileRestoreResponse {
  success: boolean
  project_id: string
  files_restored: number
  message: string
}

export const files = {
  // List files in workspace
  list: async (projectId: string, path?: string): Promise<FileListResponse> => {
    const url = path
      ? `/projects/${projectId}/files?path=${encodeURIComponent(path)}`
      : `/projects/${projectId}/files`
    const { data } = await api.get(url)
    return data
  },

  // Upload a single file
  upload: async (projectId: string, file: File, path?: string): Promise<FileUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    if (path) {
      formData.append('path', path)
    }
    const { data } = await api.post(`/projects/${projectId}/files`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // Upload multiple files
  uploadMultiple: async (projectId: string, files: File[], path?: string): Promise<FileUploadResponse> => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (path) {
      formData.append('path', path)
    }
    const { data } = await api.post(`/projects/${projectId}/files/upload-multiple`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // Download a file - returns blob URL
  download: async (projectId: string, filePath: string): Promise<string> => {
    const response = await api.get(`/projects/${projectId}/files/download/${encodeURIComponent(filePath)}`, {
      responseType: 'blob',
    })
    return URL.createObjectURL(response.data)
  },

  // Delete files
  delete: async (projectId: string, paths: string[]): Promise<{ success: boolean; deleted: string[]; message: string }> => {
    const { data } = await api.delete(`/projects/${projectId}/files`, {
      data: { paths },
    })
    return data
  },

  // Save workspace to S3
  saveToS3: async (projectId: string): Promise<FileSaveResponse> => {
    const { data } = await api.post(`/projects/${projectId}/files/save`)
    return data
  },

  // Restore workspace from S3
  restoreFromS3: async (projectId: string): Promise<FileRestoreResponse> => {
    const { data } = await api.post(`/projects/${projectId}/files/restore`)
    return data
  },

  // List saved files in S3 (works without running playground)
  listSaved: async (projectId: string): Promise<FileListResponse> => {
    const { data } = await api.get(`/projects/${projectId}/files/saved`)
    return data
  },
}

// API Keys
export const apiKeys = {
  list: async (): Promise<ApiKey[]> => {
    const { data } = await api.get('/users/me/api-keys/')
    return data
  },

  create: async (params: { provider: string; api_key: string; label?: string; model_override?: string; base_url?: string }): Promise<ApiKey> => {
    const { data } = await api.post('/users/me/api-keys/', params)
    return data
  },

  activate: async (keyId: string): Promise<ApiKey> => {
    const { data } = await api.post(`/users/me/api-keys/${keyId}/activate`)
    return data
  },

  deactivate: async (keyId: string): Promise<ApiKey> => {
    const { data } = await api.post(`/users/me/api-keys/${keyId}/deactivate`)
    return data
  },

  update: async (keyId: string, params: { api_key?: string; model_override?: string; base_url?: string; is_active?: boolean }): Promise<ApiKey> => {
    const { data } = await api.put(`/users/me/api-keys/${keyId}`, params)
    return data
  },

  delete: async (keyId: string): Promise<void> => {
    await api.delete(`/users/me/api-keys/${keyId}`)
  },

  validate: async (keyId: string): Promise<{ valid: boolean; message: string }> => {
    const { data } = await api.post(`/users/me/api-keys/${keyId}/validate`)
    return data
  },

  getProviders: async (): Promise<ProviderInfo[]> => {
    const { data } = await api.get('/users/me/api-keys/providers')
    return data
  },
}

// Credits & Usage
export const credits = {
  getBalance: async (): Promise<CreditBalance> => {
    const { data } = await api.get('/credits/balance')
    return data
  },

  getUsageHistory: async (page = 1, pageSize = 50): Promise<{ records: UsageRecord[]; total: number; page: number; page_size: number }> => {
    const { data } = await api.get('/credits/usage', { params: { page, page_size: pageSize } })
    return data
  },

  getPricing: async (): Promise<LLMModel[]> => {
    const { data } = await api.get('/credits/pricing')
    return data
  },
}

// LLM Models (registry)
export const models = {
  list: async (): Promise<LLMModelGrouped[]> => {
    const { data } = await api.get('/models')
    return data
  },

  listByProvider: async (provider: string): Promise<LLMModelBrief[]> => {
    const { data } = await api.get(`/models/${provider}`)
    return data
  },
}

// Templates
export const templates = {
  list: async (category?: string): Promise<NotebookTemplate[]> => {
    const { data } = await api.get('/templates', { params: category ? { category } : {} })
    return data
  },

  get: async (id: string): Promise<NotebookTemplate> => {
    const { data } = await api.get(`/templates/${id}`)
    return data
  },

  fork: async (id: string, name?: string): Promise<{ project_id: string; project_name: string; message: string }> => {
    const { data } = await api.post(`/templates/${id}/fork`, { name })
    return data
  },
}

// Admin APIs
export const admin = {
  users: {
    list: async (params?: { page?: number; page_size?: number; search?: string; status?: string; role?: string; created_from?: string; created_to?: string; sort_by?: string; sort_order?: string }): Promise<AdminUserListResponse> => {
      const { data } = await api.get('/admin/users/', { params })
      return data
    },

    get: async (userId: string): Promise<AdminUserDetail> => {
      const { data } = await api.get(`/admin/users/${userId}`)
      return data
    },

    toggleActive: async (userId: string, isActive: boolean): Promise<{ id: string; email: string; is_active: boolean }> => {
      const { data } = await api.patch(`/admin/users/${userId}/active`, { is_active: isActive })
      return data
    },

    toggleAdmin: async (userId: string, isAdmin: boolean): Promise<{ id: string; email: string; is_admin: boolean }> => {
      const { data } = await api.patch(`/admin/users/${userId}/admin`, { is_admin: isAdmin })
      return data
    },

    resetPassword: async (userId: string, newPassword: string): Promise<{ id: string; email: string; message: string }> => {
      const { data } = await api.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
      return data
    },

    updateMaxProjects: async (userId: string, maxProjects: number): Promise<{ id: string; email: string; max_projects: number }> => {
      const { data } = await api.patch(`/admin/users/${userId}/max-projects`, { max_projects: maxProjects })
      return data
    },
  },

  invitations: {
    list: async (params?: { page?: number; page_size?: number; search?: string; active_only?: boolean }): Promise<{ invitations: Invitation[]; total: number; page: number; page_size: number }> => {
      const { data } = await api.get('/admin/invitations/', { params })
      return data
    },

    create: async (params: { email?: string; expires_at?: string; note?: string; base_url?: string }): Promise<Invitation> => {
      const { data } = await api.post('/admin/invitations/', params)
      return data
    },

    batchCreate: async (params: { emails: string[]; note?: string; expires_at?: string; base_url?: string }): Promise<Invitation[]> => {
      const { data } = await api.post('/admin/invitations/batch', params)
      return data
    },

    get: async (id: string): Promise<InvitationDetail> => {
      const { data } = await api.get(`/admin/invitations/${id}`)
      return data
    },

    deactivate: async (id: string): Promise<Invitation> => {
      const { data } = await api.patch(`/admin/invitations/${id}/deactivate`)
      return data
    },

    delete: async (id: string): Promise<void> => {
      await api.delete(`/admin/invitations/${id}`)
    },

    reinvite: async (id: string, baseUrl: string): Promise<Invitation> => {
      const { data } = await api.post(`/admin/invitations/${id}/reinvite`, null, { params: { base_url: baseUrl } })
      return data
    },
  },

  credits: {
    adjust: async (params: { user_id: string; amount_cents: number; reason?: string }): Promise<CreditBalance> => {
      const { data } = await api.post('/admin/credits/adjust', params)
      return data
    },
  },

  models: {
    list: async (): Promise<LLMModel[]> => {
      const { data } = await api.get('/admin/models')
      return data
    },

    create: async (params: { provider: string; model_id: string; display_name: string; context_window?: number; max_output_tokens?: number; supports_vision?: boolean; supports_function_calling?: boolean; input_cost_per_1m_cents?: number; output_cost_per_1m_cents?: number; margin_multiplier?: number; is_custom?: boolean; sort_order?: number }): Promise<LLMModel> => {
      const { data } = await api.post('/admin/models', params)
      return data
    },

    update: async (id: number, params: { model_id?: string; display_name?: string; context_window?: number; max_output_tokens?: number; supports_vision?: boolean; supports_function_calling?: boolean; input_cost_per_1m_cents?: number; output_cost_per_1m_cents?: number; margin_multiplier?: number; is_active?: boolean; sort_order?: number }): Promise<LLMModel> => {
      const { data } = await api.put(`/admin/models/${id}`, params)
      return data
    },

    delete: async (id: number): Promise<void> => {
      await api.delete(`/admin/models/${id}`)
    },

    getWarnings: async (): Promise<{ warnings: { provider: string; model_id: string; display_name: string }[] }> => {
      const { data } = await api.get('/admin/models/warnings')
      return data
    },
  },

  templates: {
    create: async (params: { name: string; description?: string; category?: string; difficulty_level?: string; tags?: string[]; is_public?: boolean }): Promise<NotebookTemplate> => {
      const { data } = await api.post('/admin/templates', params)
      return data
    },

    createFromProject: async (projectId: string, params: { name: string; description?: string; category?: string; difficulty_level?: string; tags?: string[]; is_public?: boolean }): Promise<NotebookTemplate> => {
      const { data } = await api.post(`/admin/templates/from-project/${projectId}`, params)
      return data
    },

    update: async (id: string, params: Partial<NotebookTemplate>): Promise<NotebookTemplate> => {
      const { data } = await api.put(`/admin/templates/${id}`, params)
      return data
    },

    delete: async (id: string): Promise<void> => {
      await api.delete(`/admin/templates/${id}`)
    },
  },

  platformKeys: {
    list: async (provider?: string): Promise<PlatformKey[]> => {
      const { data } = await api.get('/admin/platform-keys/', { params: provider ? { provider } : {} })
      return data
    },

    create: async (params: { provider: string; label: string; api_key: string; auth_type?: string; model_name?: string; base_url?: string }): Promise<PlatformKey> => {
      const { data } = await api.post('/admin/platform-keys/', params)
      return data
    },

    update: async (id: string, params: { label?: string; api_key?: string; auth_type?: string; model_name?: string; base_url?: string }): Promise<PlatformKey> => {
      const { data } = await api.put(`/admin/platform-keys/${id}`, params)
      return data
    },

    delete: async (id: string): Promise<void> => {
      await api.delete(`/admin/platform-keys/${id}`)
    },

    activate: async (id: string): Promise<PlatformKey> => {
      const { data } = await api.post(`/admin/platform-keys/${id}/activate`)
      return data
    },

    deactivate: async (id: string): Promise<PlatformKey> => {
      const { data } = await api.post(`/admin/platform-keys/${id}/deactivate`)
      return data
    },

    setDefault: async (id: string): Promise<PlatformKey> => {
      const { data } = await api.post(`/admin/platform-keys/${id}/set-default`)
      return data
    },

    validate: async (id: string): Promise<{ valid: boolean; error?: string }> => {
      const { data } = await api.post(`/admin/platform-keys/${id}/validate`)
      return data
    },

    toggleProviderVisibility: async (provider: string, visible: boolean): Promise<{ provider: string; user_visible: boolean }> => {
      const { data } = await api.post(`/admin/platform-keys/provider/${provider}/visibility`, null, { params: { visible } })
      return data
    },
  },

  systemPrompts: {
    list: async (promptType?: string): Promise<SystemPrompt[]> => {
      const { data } = await api.get('/admin/system-prompts/', { params: promptType ? { prompt_type: promptType } : {} })
      return data
    },

    create: async (params: { prompt_type: string; label: string; content: string; mode_name?: string; tools?: string[] }): Promise<SystemPrompt> => {
      const { data } = await api.post('/admin/system-prompts/', params)
      return data
    },

    update: async (id: string, params: { label?: string; content?: string; mode_name?: string; tools?: string[] }): Promise<SystemPrompt> => {
      const { data } = await api.put(`/admin/system-prompts/${id}`, params)
      return data
    },

    delete: async (id: string): Promise<void> => {
      await api.delete(`/admin/system-prompts/${id}`)
    },

    activate: async (id: string): Promise<SystemPrompt> => {
      const { data } = await api.post(`/admin/system-prompts/${id}/activate`)
      return data
    },

    deactivate: async (id: string): Promise<SystemPrompt> => {
      const { data } = await api.post(`/admin/system-prompts/${id}/deactivate`)
      return data
    },

    getToolCatalog: async (): Promise<{ category: string; tools: { name: string; category: string; description?: string; is_active: boolean }[] }[]> => {
      const { data } = await api.get('/admin/system-prompts/tool-catalog')
      return data
    },

    addTool: async (params: { name: string; category: string; description?: string }): Promise<void> => {
      await api.post('/admin/system-prompts/tool-catalog', params)
    },

    updateTool: async (name: string, params: { category?: string; description?: string; is_active?: boolean }): Promise<void> => {
      await api.put(`/admin/system-prompts/tool-catalog/${name}`, params)
    },

    deleteTool: async (name: string): Promise<void> => {
      await api.delete(`/admin/system-prompts/tool-catalog/${name}`)
    },
  },
}

export default api
