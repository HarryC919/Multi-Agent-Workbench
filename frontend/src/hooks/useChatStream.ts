import { useRef } from 'react'
import { nanoid } from 'nanoid'
import { sendChatStream } from '@/api/chat'
import { sendAgentChatStream } from '@/api/agent-chat'
import { useToastStore } from '@/store/toastStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import type { ChatMessage, FileContent, Message, UploadedFile } from '@/types'

export interface UseChatStreamReturn {
  sendMessage: (content: string, attachedFiles: UploadedFile[], conversationId?: string) => void
  abort: () => void
}

export function useChatStream(): UseChatStreamReturn {
  const store = useWorkspaceStore()
  const abortRef = useRef<(() => void) | null>(null)

  const sendMessage = (content: string, attachedFiles: UploadedFile[], conversationId?: string) => {
    // conversationId may be passed explicitly to bypass the stale-closure trap:
    // when called right after `await createConversation()` inside handleSend,
    // the `store` captured here still holds the previous (pre-creation) values.
    const resolvedId = conversationId ?? useWorkspaceStore.getState().activeId
    if (!resolvedId) return

    // Always read the freshest conversation from the store to avoid acting on
    // a stale snapshot captured at hook-render time. Right after
    // createConversation(), currentConversation may not yet match resolvedId;
    // in that case history is empty and the user message below seeds it.
    const conversation =
      useWorkspaceStore.getState().currentConversation ?? store.currentConversation

    // Reset any previous streaming state before starting a new turn.
    if (abortRef.current) {
      abortRef.current()
      abortRef.current = null
    }
    store.setStreaming(false)

    const history: ChatMessage[] =
      conversation && conversation.id === resolvedId
        ? conversation.messages.map((m) => ({
            role: m.role,
            content: m.content,
          }))
        : []

    const now = new Date().toISOString()

    const userMessage: Message = {
      id: nanoid(),
      conversationId: resolvedId,
      role: 'user',
      content,
      model: store.selectedModel,
      status: 'done',
      createdAt: now,
    }

    const assistantPlaceholder: Message = {
      id: nanoid(),
      conversationId: resolvedId,
      role: 'assistant',
      content: '',
      model: store.selectedModel,
      status: 'streaming',
      createdAt: now,
    }

    store.addMessage(userMessage)
    store.addMessage(assistantPlaceholder)
    store.setStreaming(true)

    const files: FileContent[] = attachedFiles
      .filter((f) => f.name && f.textContent)
      .map((f) => ({
        name: f.name,
        content: f.textContent,
      }))

    // Agent mode (phase 2a) routes to /api/agent-chat — emits the same
    // text/thinking stream plus action/observation events. We render the
    // ReAct transcript as the assistant's body+thinking so the existing
    // MessageItem / ThinkingBlock components work without changes.
    const agentMode = useWorkspaceStore.getState().agentMode
    // Read KB id fresh from the store (not the captured snapshot) so a KB
    // selection change in ChatHeader between renders isn't missed.
    const ragKnowledgeBaseId = useWorkspaceStore.getState().selectedKbId || undefined

    if (agentMode) {
      const { abort } = sendAgentChatStream(
        {
          conversationId: resolvedId,
          model: store.selectedModel,
          messages: [...history, { role: 'user', content }],
          files,
          stream: true,
          thinking: store.thinkingEnabled,
          ragKnowledgeBaseId,
        },
        {
          onText: (text) => {
            store.appendToAssistant(text)
          },
          onThinking: (text) => {
            store.appendToAssistantThinking(text)
          },
          onAction: (name, input, step) => {
            const line = `\n[Step ${step}] Action: ${name}(${input})\n`
            store.appendToAssistantThinking(line)
          },
          onObservation: (name, observation, step) => {
            const line = `\n[Step ${step}] Observation(${name}): ${observation}\n`
            store.appendToAssistantThinking(line)
          },
          onWarning: (message) => {
            const msg = message || 'agent-limit'
            useToastStore.getState().addToast(`Agent: ${msg}`, 'warning')
            store.appendToAssistant(`\n\n**Agent ⚠️:** ${msg}`)
          },
          onDone: () => {
            store.setAssistantStatus('done')
            store.loadConversations()
          },
          onError: (error) => {
            store.appendToAssistant(`\n\n**Agent Error:** ${error.message}`)
            store.setAssistantStatus('error')
            useToastStore.getState().addToast(error.message, 'error')
          },
          onFinally: () => {
            store.setStreaming(false)
            abortRef.current = null
          },
        },
      )
      abortRef.current = abort
      return
    }

    const { abort } = sendChatStream(
      {
        conversationId: resolvedId,
        model: store.selectedModel,
        messages: [...history, { role: 'user', content }],
        files,
        stream: true,
        thinking: store.thinkingEnabled,
        ragKnowledgeBaseId,
      },
      {
        onText: (text) => {
          store.appendToAssistant(text)
        },
        onThinking: (text) => {
          store.appendToAssistantThinking(text)
        },
        onWarning: (message) => {
          if (message) useToastStore.getState().addToast(message, 'warning')
        },
        onDone: () => {
          store.setAssistantStatus('done')
          store.loadConversations()
        },
        onError: (error) => {
          store.appendToAssistant(`\n\n**Error:** ${error.message}`)
          store.setAssistantStatus('error')
          useToastStore.getState().addToast(error.message, 'error')
        },
        onFinally: () => {
          store.setStreaming(false)
          abortRef.current = null
        },
      },
    )

    abortRef.current = abort
  }

  const abort = () => {
    abortRef.current?.()
  }

  return {
    sendMessage,
    abort,
  }
}
