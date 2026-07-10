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
  model?: string
  effort: number
  status: MessageStatus
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
  effort: number
  files: FileContent[]
  stream: boolean
  ragKnowledgeBaseId?: string
}

export interface ChatChunk {
  type: 'text' | 'done' | 'error'
  content?: string
  finishReason?: string
  message?: string
}

export interface UploadFileResponse {
  fileId: string
  name: string
  textContent: string
}
