export interface User {
  id: string
  email: string
  name?: string
  avatar_url?: string
  max_projects: number
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  created_at: string
  updated_at: string
}

export interface Invitation {
  id: string
  code_prefix: string
  email?: string
  is_used: boolean
  created_by: string
  expires_at?: string
  is_active: boolean
  note?: string
  created_at: string
  updated_at: string
}

export interface InvitationUse {
  id: string
  invitation_id: string
  user_id: string
  used_at: string
}

export interface InvitationDetail extends Invitation {
  uses: InvitationUse[]
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
  user_id?: string
  project_id?: string
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

export interface ApiKey {
  id: string
  provider: string
  label?: string
  api_key_hint: string
  model_override?: string
  base_url?: string
  is_active: boolean
  is_validated: boolean
  last_validated_at?: string
  created_at: string
  updated_at: string
}

export interface ProviderInfo {
  provider: string
  display_name: string
  has_key: boolean
  is_default: boolean
  active_model?: string
  models: string[]
}

export interface CreditBalance {
  user_id: string
  balance_cents: number
  balance_dollars: number
  total_deposited_cents: number
  total_consumed_cents: number
  last_charged_at?: string
}

export interface UsageRecord {
  id: number
  provider: string
  model: string
  request_type: string
  input_tokens: number
  output_tokens: number
  cost_cents: number
  is_own_key: boolean
  created_at: string
}

export interface LLMModel {
  id: number
  provider: string
  model_id: string
  display_name: string
  context_window?: number
  max_output_tokens?: number
  supports_vision: boolean
  supports_function_calling: boolean
  input_cost_per_1m_cents: number
  output_cost_per_1m_cents: number
  margin_multiplier: number
  is_active: boolean
  is_custom: boolean
  sort_order: number
}

// Backward compat alias
export type LLMPricing = LLMModel & { model: string }

export interface LLMModelBrief {
  id: number
  model_id: string
  display_name: string
  context_window?: number
  max_output_tokens?: number
  supports_vision: boolean
  supports_function_calling: boolean
}

export interface LLMModelGrouped {
  provider: string
  provider_display_name: string
  models: LLMModelBrief[]
}

export interface NotebookTemplate {
  id: string
  name: string
  description?: string
  category?: string
  thumbnail_url?: string
  difficulty_level: 'beginner' | 'intermediate' | 'advanced'
  estimated_minutes?: number
  tags?: string[]
  is_public: boolean
  created_by?: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface AdminUser {
  id: string
  email: string
  name?: string
  avatar_url?: string
  oauth_provider: string
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  max_projects: number
  created_at: string
  last_login_at?: string
  credit_balance_cents?: number
  total_deposited_cents?: number
  total_consumed_cents?: number
  project_count?: number
}

export interface AdminUserDetail extends AdminUser {
  active_sessions_count: number
  api_keys_count: number
  total_consumed_cents: number
  total_deposited_cents: number
}

export interface AdminUserListResponse {
  users: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface PlatformKey {
  id: string
  provider: string
  label: string
  api_key_hint: string
  auth_type: 'api_key' | 'oauth_token'
  model_name?: string
  base_url?: string
  is_active: boolean
  is_default: boolean
  user_visible: boolean
  priority: number
  created_by?: string
  created_at: string
  updated_at: string
}

export interface SystemPrompt {
  id: string
  prompt_type: 'chat_panel' | 'ai_cell'
  label: string
  content: string
  mode_name?: string
  tools?: string[]
  is_active: boolean
  created_by?: string
  created_at: string
  updated_at: string
}

export interface AICellMode {
  mode_name: string
  label: string
}

// Image input for AI Cell (pasted or uploaded images)
export interface ImageInput {
  data: string  // Base64 encoded image data
  mime_type: string  // MIME type (image/png, image/jpeg, etc.)
  filename?: string  // Original filename for display
}

// AI Cell streaming state for real-time updates
export interface AICellStreamState {
  thinkingMessage?: string  // Current thinking/status message (e.g., "Iteration 1...")
  currentIteration?: number  // Current iteration number
  thinkingSteps: ThinkingStep[]  // Accumulated thinking from each iteration
  currentToolCall?: { name: string; args: Record<string, unknown> }  // Tool being executed
  streamingSteps: LLMStep[]  // Steps accumulated during streaming
}

// AI Cell data stored in metadata
export interface AICellData {
  user_prompt: string
  llm_response: string
  status: 'idle' | 'running' | 'completed' | 'error'
  model?: string
  error?: string
  timestamp?: string
  images?: ImageInput[]  // Attached images
  steps?: LLMStep[]  // Tool call steps
  thinking?: ThinkingStep[]  // LLM thinking/reasoning steps (persisted to ipynb)
  streamState?: AICellStreamState  // Real-time streaming state (only during running)
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
  images?: ImageInput[]  // Attached images (only for user messages)
}

export interface LLMStep {
  type: 'tool_call' | 'tool_result' | 'text'
  name?: string
  content: string
  timestamp?: string
}

// LLM thinking step (for extended thinking / reasoning)
export interface ThinkingStep {
  iteration: number  // Which iteration this thinking is from
  content: string    // The thinking/reasoning content
  timestamp?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}
