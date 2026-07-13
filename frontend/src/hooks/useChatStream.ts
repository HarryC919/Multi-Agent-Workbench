import { useRef } from 'react'
import { nanoid } from 'nanoid'
import { sendChatStream } from '@/api/chat'
import { useToastStore } from '@/store/toastStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import type { ChatMessage, FileContent, Message, UploadedFile } from '@/types'

export interface UseChatStreamReturn {
  sendMessage: (content: string, attachedFiles: UploadedFile[]) => void
  abort: () => void
}

export function useChatStream(): UseChatStreamReturn {
  const store = useWorkspaceStore()
  const abortRef = useRef<(() => void) | null>(null)

  const sendMessage = (content: string, attachedFiles: UploadedFile[]) => {
    const conversationId = store.activeId
    if (!conversationId) return

    const conversation = store.currentConversation
    if (!conversation) return

    // Reset any previous streaming state before starting a new turn.
    if (abortRef.current) {
      abortRef.current()
      abortRef.current = null
    }
    store.setStreaming(false)

    const history: ChatMessage[] = conversation.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    const now = new Date().toISOString()

    const userMessage: Message = {
      id: nanoid(),
      conversationId,
      role: 'user',
      content,
      model: store.selectedModel,
      effort: store.effort,
      status: 'done',
      createdAt: now,
    }

    const assistantPlaceholder: Message = {
      id: nanoid(),
      conversationId,
      role: 'assistant',
      content: '',
      model: store.selectedModel,
      effort: store.effort,
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

    const { abort } = sendChatStream(
      {
        conversationId,
        model: store.selectedModel,
        messages: [...history, { role: 'user', content }],
        effort: store.effort,
        files,
        stream: true,
      },
      {
        onText: (text) => {
          store.appendToAssistant(text)
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
