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

    // Read mode + KB fresh from the store (not the captured snapshot) so a
    // toggle / KB change between renders isn't missed. agentMode is hoisted
    // before the placeholder so the agent message is tagged at creation.
    const agentMode = useWorkspaceStore.getState().agentMode
    const ragKnowledgeBaseId = useWorkspaceStore.getState().selectedKbId || undefined

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
      // Phase 2b-ii: agent messages are tagged `metadata.agent` + an empty
      // steps array so MessageItem renders AgentTrace from the first
      // step_start event. Plain chat leaves metadata unset.
      ...(agentMode ? { metadata: { agent: true, steps: [] } } : {}),
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

    // Agent mode (phase 2a/2b-ii) routes to /api/agent-chat. The transcript
    // is accumulated into `metadata.steps` (one AgentStep per step_start) and
    // rendered by AgentTrace; the assistant body keeps ONLY the final answer
    // (lifted from the step whose finish==="final", minus the "Final Answer:"
    // prefix). `thinking` stays empty for agent messages — the trace is the
    // whole reasoning surface.
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
          onStepStart: (step) => {
            store.appendAgentStep(step, `第 ${step} 步`)
          },
          onThinking: (text) => {
            store.appendAgentStepThinking(text)
          },
          onText: (text) => {
            store.appendAgentStepText(text)
          },
          onAction: (name, input) => {
            store.setAgentStepAction(name, input)
          },
          onObservation: (name, content) => {
            store.setAgentStepObservation(name, content)
          },
          onRetrieved: (_step, docs) => {
            store.setAgentStepRetrieved(docs)
          },
          onStepEnd: (step, finish) => {
            store.completeAgentStep(step, finish)
            // Lift the final answer into the message body. The backend emits
            // a `text` event for every step (Thought/Action/Final Answer),
            // so only the finish==="final" step's accumulated text becomes
            // the visible reply — after stripping the "Final Answer:" prefix.
            if (finish === 'final') {
              const conv = useWorkspaceStore.getState().currentConversation
              const last = conv?.messages?.[conv.messages.length - 1]
              const steps = ((last?.metadata as Record<string, unknown> | undefined)?.steps as
                | { text?: string }[]
                | undefined) ?? []
              const cur = steps[steps.length - 1]
              const body = (cur?.text ?? '').replace(/^[\s\S]*?Final Answer:\s*/i, '')
              if (body) store.appendToAssistant(body)
            }
          },
          onWarning: (message) => {
            const msg = message || 'agent-limit'
            useToastStore.getState().addToast(`Agent: ${msg}`, 'warning')
            store.appendToAssistant(`\n\n**Agent ⚠️:** ${msg}`)
          },
          onDone: () => {
            store.setAssistantStatus('done')
            // Fire-and-forget refresh: a failed list reload is non-fatal and
            // must not surface as an unhandled rejection.
            store.loadConversations().catch(() => {})
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
          // Fire-and-forget refresh: a failed list reload is non-fatal and
          // must not surface as an unhandled rejection.
          store.loadConversations().catch(() => {})
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
