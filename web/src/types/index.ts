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
  llm_provider: 'ollama' | 'openai' | 'anthropic' | 'gemini'
  llm_model?: string
  is_archived: boolean
  created_at: string
  updated_at: string
  last_opened_at?: string
  playground?: Playground
}

export interface Playground {
  id: string
  project_id: string
  container_id: string
  container_name: string
  status: 'starting' | 'running' | 'stopping' | 'stopped' | 'error'
  error_message?: string
  started_at: string
  last_activity_at: string
  url?: string
}

export interface Cell {
  id: string
  type: 'code' | 'markdown'
  source: string
  outputs: CellOutput[]
  execution_count?: number
  metadata?: Record<string, unknown>
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
