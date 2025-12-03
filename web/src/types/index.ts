export interface User {
  id: string
  email: string
  name?: string
  avatar_url?: string
  max_projects: number
  is_active: boolean
  is_verified: boolean
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  name: string
  description?: string
  workspace_id?: string
  is_archived: boolean
  created_at: string
  updated_at: string
  last_opened_at?: string
  playground?: Playground
}

export interface Workspace {
  id: string
  user_id: string
  name: string
  description?: string
  color: string
  icon?: string
  is_default: boolean
  sort_order: string
  created_at: string
  updated_at: string
  project_count: number
}

export interface Playground {
  id: string
  project_id: string
  container_id: string
  container_name: string
  status: 'starting' | 'running' | 'stopping' | 'stopped' | 'error'
  error_message?: string
  memory_limit_mb: number
  cpu_limit: number
  started_at: string
  last_activity_at: string
  url?: string
}

// AI Cell data stored in metadata
export interface AICellData {
  user_prompt: string
  llm_response: string
  status: 'idle' | 'running' | 'completed' | 'error'
  model?: string
  error?: string
  timestamp?: string
}

// Frontend cell type (for React state)
export interface Cell {
  id: string  // Derived from metadata.cell_id when loading
  type: 'code' | 'markdown' | 'raw' | 'ai'
  source: string
  outputs: CellOutput[]
  execution_count?: number
  metadata?: Record<string, unknown>
  ai_data?: AICellData  // Only present for AI cells
}

// API cell type (Jupyter .ipynb standard format)
export interface ApiCell {
  cell_type: string  // "code", "markdown", or "raw" (Jupyter standard)
  source: string
  outputs: Record<string, unknown>[]
  execution_count?: number
  metadata: {
    cell_id: string  // Jupyter standard location for cell ID
    [key: string]: unknown
  }
}

export interface CellOutput {
  output_type: 'stream' | 'execute_result' | 'display_data' | 'error'
  text?: string | string[]
  data?: Record<string, unknown>
  ename?: string
  evalue?: string
  traceback?: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  steps?: LLMStep[]
}

export interface LLMStep {
  type: 'tool_call' | 'tool_result' | 'text'
  name?: string
  content: string
  timestamp?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}
