export type MessageRole = 'system' | 'user' | 'assistant'
export type MessageStatus = 'pending' | 'streaming' | 'done' | 'error'
export type AdapterType = 'openai' | 'anthropic' | 'gemini' | 'openai_compatible' | 'anthropic_compatible'

export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export interface Message {
  id: string
  conversationId: string
  role: MessageRole
  content: string
  thinking?: string
  model?: string
  status: MessageStatus
  metadata?: Record<string, unknown>
  createdAt: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface UploadedFile {
  id: string
  name: string
  textContent: string
}

export interface ModelConfig {
  id: string
  modelId: string
  vendor: string
  name: string
  adapterType: AdapterType
  baseUrl?: string
  /** Whether a per-model API key is configured. The key itself is never sent
   *  to the client. */
  hasApiKey?: boolean
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface ChatMessage {
  role: MessageRole
  content: string
}

export interface FileContent {
  name: string
  content: string
}

export interface ChatRequest {
  conversationId?: string
  model: string
  messages: ChatMessage[]
  files: FileContent[]
  stream: boolean
  thinking?: boolean
  ragKnowledgeBaseId?: string
}

export interface AgentChatRequest extends ChatRequest {
  maxSteps?: number
  stepTemperature?: number
  finalTemperature?: number
  enableSkills?: string[]
}

export interface ChatChunk {
  type: 'text' | 'thinking' | 'done' | 'error' | 'warning' | 'action' | 'observation'
  content?: string
  finishReason?: string
  message?: string
  // Agent mode (phase 2a) action / observation events.
  name?: string
  step?: number
  input?: string
  maxSteps?: number
}

export interface UploadFileResponse {
  fileId: string
  name: string
  textContent: string
}

// ---------------------------------------------------------------------------
// AgentService phase 2b-i — knowledge base / RAG types.
// ---------------------------------------------------------------------------

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  createdAt: string
  updatedAt: string
}

export interface KnowledgeDoc {
  id: string
  kbId: string
  filename: string
  sha256: string
  createdAt: string
}

export interface DocumentUploadResponse {
  docId: string
  filename: string
  chunks: number
  deduplicated: boolean
}

export interface RetrievedChunk {
  docId: string
  filename: string
  heading: string
  score: number
  text: string
}
