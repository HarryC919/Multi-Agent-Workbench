import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { StoreApi } from 'zustand'
import { nanoid } from 'nanoid'
import type {
  AgentStep,
  Conversation,
  ConversationDetail,
  KnowledgeBase,
  Message,
  ModelConfig,
  RetrievedChunkDoc,
  UploadedFile,
} from '@/types'

/**
 * Mutates the in-flight agent step (tail of the last assistant message's
 * `metadata.steps`) in place. Mirrors the `appendToAssistantThinking` shape:
 * shallow-copy the messages array, mutate the streaming assistant's last
 * step via `mutate`, then commit. No-op when there is no in-flight step.
 *
 * Phase 2b-ii: agent messages keep `thinking` empty — the whole ReAct
 * transcript lives in `metadata.steps`, so this is the only accumulation
 * path the agent branch uses.
 */
function mutateLastStep(
  api: StoreApi<WorkspaceState>,
  mutate: (step: AgentStep) => void,
): void {
  api.setState((state) => {
    if (!state.currentConversation) return state
    const messages = [...(state.currentConversation.messages || [])]
    const lastMessage = messages[messages.length - 1]
    if (!lastMessage || lastMessage.role !== 'assistant') return state
    const meta = (lastMessage.metadata ?? {}) as Record<string, unknown>
    const steps = ((meta.steps as AgentStep[]) ?? []).slice()
    const current = steps[steps.length - 1]
    if (!current) return state
    // Clone the in-flight step so React sees a new reference.
    const next: AgentStep = { ...current }
    mutate(next)
    steps[steps.length - 1] = next
    lastMessage.metadata = { ...meta, agent: true, steps }
    return {
      currentConversation: { ...state.currentConversation, messages },
    }
  })
}

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
  agentMode: boolean

  // Streaming state
  isStreaming: boolean

  // Models
  models: ModelConfig[]
  isLoadingModels: boolean

  // Knowledge bases (phase 2b-i). selectedKbId '' sentinel = no KB selected.
  knowledgeBases: KnowledgeBase[]
  selectedKbId: string

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
  setAgentMode: (value: boolean) => void
  attachFile: (file: UploadedFile) => void
  removeFile: (fileId: string) => void
  clearInput: () => void
  addMessage: (message: Message) => void
  appendToAssistant: (content: string) => void
  appendToAssistantThinking: (thinking: string) => void
  // Phase 2b-ii: agent step transcript actions. These operate on the last
  // assistant message's `metadata.steps` array (in-flight step at the tail).
  appendAgentStep: (step: number, label: string) => void
  appendAgentStepThinking: (text: string) => void
  appendAgentStepText: (text: string) => void
  setAgentStepAction: (name: string, input: string) => void
  setAgentStepObservation: (name: string, content: string) => void
  setAgentStepRetrieved: (docs: RetrievedChunkDoc[]) => void
  completeAgentStep: (step: number, finish: string) => void
  setAssistantStatus: (status: Message['status']) => void
  setStreaming: (streaming: boolean) => void
  loadModels: () => Promise<void>
  addModel: (model: ModelConfig) => void
  updateModel: (model: ModelConfig) => void
  removeModel: (modelId: string) => void
  loadKnowledgeBases: () => Promise<void>
  addKnowledgeBase: (kb: KnowledgeBase) => void
  removeKnowledgeBase: (kbId: string) => void
  setSelectedKbId: (kbId: string) => void
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get, api) => ({
      conversations: [],
      activeId: null,
      currentConversation: null,
      isLoadingConversation: false,

      inputText: '',
      attachedFiles: [],
      selectedModel: '',
      thinkingEnabled: false,
      agentMode: false,

      isStreaming: false,

      models: [],
      isLoadingModels: false,

      knowledgeBases: [],
      selectedKbId: '',

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

      setThinkingEnabled: (value) =>
        // Agent 模式下深度思考是 ReAct 推理的必要输出（trace 依赖它），
        // 强制启用——忽略任何关闭尝试，避免用户手动关掉后 trace 不可见。
        set((state) => (state.agentMode ? state : { thinkingEnabled: value })),

      setAgentMode: (value) =>
        // Agent 模式走 ReAct 多步推理，思考链是推理过程的必要输出——开启时
        // 自动联动深度思考，避免用户忘了开导致 trace 不可见。关闭时不强制
        // 改回 thinkingEnabled，以免覆盖用户随后的手动选择。
        set(value ? { agentMode: true, thinkingEnabled: true } : { agentMode: false }),

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

      // Phase 2b-ii: agent step transcript. Each action mutates the in-flight
      // step (tail of `metadata.steps`) on the streaming assistant message.
      // `appendAgentStep` seeds the agent marker + steps array if absent.
      appendAgentStep: (step, _label) => {
        set((state) => {
          if (!state.currentConversation) return state
          const messages = [...(state.currentConversation.messages || [])]
          const lastMessage = messages[messages.length - 1]
          if (!lastMessage || lastMessage.role !== 'assistant') return state
          const meta = (lastMessage.metadata ?? {}) as Record<string, unknown>
          const steps = ((meta.steps as AgentStep[]) ?? []).slice()
          steps.push({
            step,
            thinking: '',
            text: '',
            action: null,
            observation: null,
            retrieved: null,
            finish: null,
          })
          lastMessage.metadata = { ...meta, agent: true, steps }
          return {
            currentConversation: { ...state.currentConversation, messages },
          }
        })
      },

      appendAgentStepThinking: (text) => {
        mutateLastStep(api, (s) => {
          s.thinking += text
        })
      },

      appendAgentStepText: (text) => {
        mutateLastStep(api, (s) => {
          s.text += text
        })
      },

      setAgentStepAction: (name, input) => {
        mutateLastStep(api, (s) => {
          s.action = { name, input }
        })
      },

      setAgentStepObservation: (name, content) => {
        mutateLastStep(api, (s) => {
          s.observation = { name, content }
        })
      },

      setAgentStepRetrieved: (docs) => {
        mutateLastStep(api, (s) => {
          s.retrieved = docs
        })
      },

      completeAgentStep: (step, finish) => {
        mutateLastStep(api, (s) => {
          if (s.step === step) s.finish = finish
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

      loadKnowledgeBases: async () => {
        const { fetchKnowledgeBases } = await import('@/api/knowledge')
        const knowledgeBases = await fetchKnowledgeBases()
        set((state) => ({
          knowledgeBases: knowledgeBases || [],
          // Clear selection if the selected KB no longer exists.
          selectedKbId:
            state.selectedKbId &&
            !(knowledgeBases || []).some((k) => k.id === state.selectedKbId)
              ? ''
              : state.selectedKbId,
        }))
      },

      addKnowledgeBase: (kb) =>
        set((state) => ({ knowledgeBases: [...state.knowledgeBases, kb] })),

      removeKnowledgeBase: (kbId) =>
        set((state) => ({
          knowledgeBases: state.knowledgeBases.filter((k) => k.id !== kbId),
          selectedKbId: state.selectedKbId === kbId ? '' : state.selectedKbId,
        })),

      setSelectedKbId: (kbId) => set({ selectedKbId: kbId }),
    }),
    {
      name: 'chat-workbench-storage',
      version: 5,
      partialize: (state) => ({
        selectedModel: state.selectedModel,
        thinkingEnabled: state.thinkingEnabled,
        agentMode: state.agentMode,
        selectedKbId: state.selectedKbId,
      }),
      skipHydration: true,
      merge: (persistedState, currentState) => {
        // Merge persisted fields into the full initial state to avoid undefined arrays.
        // NOTE: each persisted field must be listed here explicitly — the spread
        // alone would drop new fields (selectedKbId) from older persisted blobs.
        const persisted = (persistedState || {}) as Partial<WorkspaceState>
        return {
          ...currentState,
          selectedModel: persisted.selectedModel ?? currentState.selectedModel,
          thinkingEnabled: persisted.thinkingEnabled ?? currentState.thinkingEnabled,
          agentMode: persisted.agentMode ?? currentState.agentMode,
          selectedKbId: persisted.selectedKbId ?? currentState.selectedKbId,
        }
      },
    },
  ),
)

export function rehydrateWorkspaceStore(): Promise<void> {
  const result = useWorkspaceStore.persist.rehydrate()
  return result instanceof Promise ? result : Promise.resolve()
}
