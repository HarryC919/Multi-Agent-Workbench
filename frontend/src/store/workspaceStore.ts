import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { nanoid } from 'nanoid'
import type {
  Conversation,
  ConversationDetail,
  Message,
  ModelConfig,
  UploadedFile,
} from '@/types'

interface WorkspaceState {
  // Conversations
  conversations: Conversation[]
  activeId: string | null
  currentConversation: ConversationDetail | null
  isLoadingConversation: boolean

  // Input area state
  inputText: string
  attachedFiles: UploadedFile[]
  selectedModel: string
  thinkingEnabled: boolean

  // Streaming state
  isStreaming: boolean

  // Models
  models: ModelConfig[]
  isLoadingModels: boolean

  // Actions
  setActive: (id: string | null) => void
  loadConversations: () => Promise<void>
  createConversation: () => Promise<string>
  loadConversation: (id: string) => Promise<void>
  renameConversation: (id: string, title: string) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  setInputText: (text: string) => void
  setSelectedModel: (model: string) => void
  setThinkingEnabled: (value: boolean) => void
  attachFile: (file: UploadedFile) => void
  removeFile: (fileId: string) => void
  clearInput: () => void
  addMessage: (message: Message) => void
  appendToAssistant: (content: string) => void
  appendToAssistantThinking: (thinking: string) => void
  setAssistantStatus: (status: Message['status']) => void
  setStreaming: (streaming: boolean) => void
  loadModels: () => Promise<void>
  addModel: (model: ModelConfig) => void
  updateModel: (model: ModelConfig) => void
  removeModel: (modelId: string) => void
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeId: null,
      currentConversation: null,
      isLoadingConversation: false,

      inputText: '',
      attachedFiles: [],
      selectedModel: '',
      thinkingEnabled: false,

      isStreaming: false,

      models: [],
      isLoadingModels: false,

      setActive: (id) => {
        set({ activeId: id, currentConversation: null })
        if (id) {
          get().loadConversation(id)
        }
      },

      loadConversations: async () => {
        const { fetchConversations } = await import('@/api/conversations')
        const conversations = await fetchConversations()
        set({ conversations: conversations || [] })
      },

      createConversation: async () => {
        const { createConversation: apiCreate } = await import('@/api/conversations')
        const conversation = await apiCreate()
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          activeId: conversation.id,
          currentConversation: { ...conversation, messages: [] },
          inputText: '',
          attachedFiles: [],
        }))
        return conversation.id
      },

      loadConversation: async (id) => {
        set({ isLoadingConversation: true })
        try {
          const { fetchConversation } = await import('@/api/conversations')
          const conversation = await fetchConversation(id)
          set({ currentConversation: conversation, activeId: id })
        } finally {
          set({ isLoadingConversation: false })
        }
      },

      renameConversation: async (id, title) => {
        const { renameConversation: apiRename } = await import('@/api/conversations')
        const updated = await apiRename(id, title)
        set((state) => ({
          conversations: state.conversations.map((c) => (c.id === id ? updated : c)),
          currentConversation:
            state.currentConversation?.id === id
              ? { ...state.currentConversation, title: updated.title }
              : state.currentConversation,
        }))
      },

      deleteConversation: async (id) => {
        const { deleteConversation: apiDelete } = await import('@/api/conversations')
        await apiDelete(id)
        set((state) => {
          const conversations = state.conversations.filter((c) => c.id !== id)
          const activeId = state.activeId === id ? (conversations[0]?.id ?? null) : state.activeId
          return {
            conversations,
            activeId,
            currentConversation: state.activeId === id ? null : state.currentConversation,
          }
        })
      },

      setInputText: (text) => set({ inputText: text }),

      setSelectedModel: (model) => set({ selectedModel: model }),

      setThinkingEnabled: (value) => set({ thinkingEnabled: value }),

      attachFile: (file) =>
        set((state) => ({ attachedFiles: [...state.attachedFiles, file] })),

      removeFile: (fileId) =>
        set((state) => ({
          attachedFiles: state.attachedFiles.filter((f) => f.id !== fileId),
        })),

      clearInput: () => set({ inputText: '', attachedFiles: [] }),

      addMessage: (message) => {
        set((state) => {
          if (!state.currentConversation) return state
          return {
            currentConversation: {
              ...state.currentConversation,
              messages: [...(state.currentConversation.messages || []), message],
            },
          }
        })
      },

      appendToAssistant: (content) => {
        set((state) => {
          if (!state.currentConversation) return state
          const messages = [...(state.currentConversation.messages || [])]
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.role === 'assistant' && lastMessage.status === 'streaming') {
            lastMessage.content += content
          } else {
            messages.push({
              id: nanoid(),
              conversationId: state.currentConversation.id,
              role: 'assistant',
              content,
              model: state.selectedModel,
              status: 'streaming',
              createdAt: new Date().toISOString(),
            })
          }
          return {
            currentConversation: { ...state.currentConversation, messages },
          }
        })
      },

      appendToAssistantThinking: (thinking) => {
        set((state) => {
          if (!state.currentConversation) return state
          const messages = [...(state.currentConversation.messages || [])]
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.role === 'assistant' && lastMessage.status === 'streaming') {
            lastMessage.thinking = (lastMessage.thinking || '') + thinking
          } else {
            messages.push({
              id: nanoid(),
              conversationId: state.currentConversation.id,
              role: 'assistant',
              content: '',
              thinking,
              model: state.selectedModel,
              status: 'streaming',
              createdAt: new Date().toISOString(),
            })
          }
          return {
            currentConversation: { ...state.currentConversation, messages },
          }
        })
      },

      setAssistantStatus: (status) => {
        set((state) => {
          if (!state.currentConversation) return state
          const messages = [...(state.currentConversation.messages || [])]
          const lastMessage = messages[messages.length - 1]
          if (lastMessage && lastMessage.role === 'assistant' && lastMessage.status === 'streaming') {
            lastMessage.status = status
          }
          return {
            currentConversation: { ...state.currentConversation, messages },
          }
        })
      },

      setStreaming: (streaming) => set({ isStreaming: streaming }),

      loadModels: async () => {
        set({ isLoadingModels: true })
        try {
          const { fetchModels } = await import('@/api/models')
          const models = await fetchModels()
          set({ models: models || [] })
          if (models && models.length > 0 && !get().selectedModel) {
            set({ selectedModel: models[0].modelId })
          }
        } finally {
          set({ isLoadingModels: false })
        }
      },

      addModel: (model) =>
        set((state) => ({
          models: [...state.models, model],
        })),

      updateModel: (model) =>
        set((state) => ({
          models: state.models.map((m) => (m.id === model.id ? model : m)),
        })),

      removeModel: (modelId) =>
        set((state) => ({
          models: state.models.filter((m) => m.modelId !== modelId),
        })),
    }),
    {
      name: 'chat-workbench-storage',
      version: 3,
      partialize: (state) => ({
        selectedModel: state.selectedModel,
        thinkingEnabled: state.thinkingEnabled,
      }),
      skipHydration: true,
      merge: (persistedState, currentState) => {
        // Merge persisted fields into the full initial state to avoid undefined arrays
        const persisted = (persistedState || {}) as Partial<WorkspaceState>
        return {
          ...currentState,
          selectedModel: persisted.selectedModel ?? currentState.selectedModel,
          thinkingEnabled: persisted.thinkingEnabled ?? currentState.thinkingEnabled,
        }
      },
    },
  ),
)

export function rehydrateWorkspaceStore(): Promise<void> {
  const result = useWorkspaceStore.persist.rehydrate()
  return result instanceof Promise ? result : Promise.resolve()
}
