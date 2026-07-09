export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export interface Message {
  id: string
  conversationId: string
  role: 'system' | 'user' | 'assistant'
  content: string
  model?: string
  effort: number
  status: 'pending' | 'streaming' | 'done' | 'error'
  createdAt: string
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
  adapterType: 'openai' | 'anthropic' | 'gemini' | 'openai_compatible'
  baseUrl?: string
  isActive: boolean
  createdAt: string
  updatedAt: string
}
