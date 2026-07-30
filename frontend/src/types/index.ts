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
  type:
    | 'text'
    | 'thinking'
    | 'done'
    | 'error'
    | 'warning'
    | 'action'
    | 'observation'
    // Phase 2b-ii: step-bounded event stream (emitted alongside the flat
    // events above for backward compatibility).
    | 'step_start'
    | 'step_end'
    | 'retrieved'
    // Phase 3: per-step user-facing narration lifted to the main chat body.
    | 'narration'
  content?: string
  finishReason?: string
  message?: string
  // Agent mode (phase 2a) action / observation events.
  name?: string
  step?: number
  input?: string
  maxSteps?: number
  // Phase 2b-ii step-bounded event fields.
  finish?: string // step_end: final|tool|empty|max_steps|error
  label?: string // step_start label
  docs?: RetrievedChunkDoc[] // retrieved chunk documents (snake-cased on the wire)
}

export interface RetrievedChunkDoc {
  docId: string
  filename: string
  heading: string | null
  score: number
  text: string
}

export interface AgentStepAction {
  name: string
  input: string
}

export interface AgentStepObservation {
  name: string
  content: string
}

export interface AgentStep {
  step: number
  thinking: string
  text: string
  action: AgentStepAction | null
  observation: AgentStepObservation | null
  retrieved: RetrievedChunkDoc[] | null
  finish: string | null
  // Phase 3: per-step user-facing narration (说明:), rendered interleaved
  // with each step's trace instead of dumped at the bottom.
  narration?: string | null
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
  /** Number of documents in this KB (populated by the list endpoint). */
  documentCount: number
}

export interface KnowledgeDoc {
  id: string
  /** FK column is `knowledge_base_id` on the backend → camelCased by apiFetch. */
  knowledgeBaseId: string
  filename: string
  sha256: string
  createdAt: string
  /** Length of the stored text (full text is not sent in list responses). */
  textLength: number
}

export interface RetrievedChunk {
  docId: string
  filename: string
  heading: string | null
  chunkText: string
  score: number
}
