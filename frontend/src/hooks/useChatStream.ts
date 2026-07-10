import { nanoid } from 'nanoid'
import { sendChatStream } from '@/api/chat'
import { useToastStore } from '@/store/toastStore'
import { useWorkspaceStore } from '@/store/workspaceStore'
import type { ChatMessage, FileContent, Message, UploadedFile } from '@/types'

export interface UseChatStreamReturn {
  sendMessage: (content: string, attachedFiles: UploadedFile[]) => void
  abort: (() => void) | null
}

export function useChatStream(): UseChatStreamReturn {
  const store = useWorkspaceStore()

  const sendMessage = (content: string, attachedFiles: UploadedFile[]) => {
    const conversationId = store.activeId
    if (!conversationId) return

    const conversation = store.currentConversation
    if (!conversation) return

    const history: ChatMessage[] = conversation.messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    const userMessage: Message = {
      id: nanoid(),
      conversationId,
      role: 'user',
      content,
      model: store.selectedModel,
      effort: store.effort,
      status: 'done',
      createdAt: new Date().toISOString(),
    }

    store.addMessage(userMessage)
    store.setStreaming(true)
    store.setAssistantStatus('streaming')

    const files: FileContent[] = attachedFiles.map((f) => ({
      name: f.name,
      content: f.textContent,
    }))

    sendChatStream(
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
          store.setStreaming(false)
          store.loadConversations()
        },
        onError: (error) => {
          store.appendToAssistant(`\n\n**Error:** ${error.message}`)
          store.setAssistantStatus('error')
          store.setStreaming(false)
          useToastStore.getState().addToast(error.message, 'error')
        },
      },
    )

    store.setStreaming(true)
  }

  return {
    sendMessage,
    abort: null,
  }
}
