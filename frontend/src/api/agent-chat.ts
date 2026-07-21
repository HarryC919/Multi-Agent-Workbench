import type { AgentChatRequest, ChatChunk } from '@/types'

export interface AgentStreamCallbacks {
  onChunk?: (chunk: ChatChunk) => void
  onText?: (text: string, step?: number) => void
  onThinking?: (text: string, step?: number) => void
  onAction?: (name: string, input: string, step: number) => void
  onObservation?: (name: string, content: string, step: number) => void
  onWarning?: (message: string, maxSteps?: number) => void
  onDone?: (finishReason: string) => void
  onError?: (error: Error) => void
  onFinally?: () => void
}

/**
 * Streams an `/api/agent-chat` SSE response. Phase 2a of AgentService:
 * emits `text` / `thinking` / `action` / `observation` / `warning` / `done`
 * / `error` events. The chunk parser mirrors chat.ts so that abort / stream
 * close trailing fallbacks behave identically.
 */
export function sendAgentChatStream(
  request: AgentChatRequest,
  callbacks: AgentStreamCallbacks,
): { abort: () => void } {
  const abortController = new AbortController()
  let finished = false

  const finalize = () => {
    if (finished) return
    finished = true
    callbacks.onFinally?.()
  }

  const payload: Record<string, unknown> = {
    conversation_id: request.conversationId,
    model: request.model,
    messages: request.messages,
    files: request.files,
    stream: true,
    thinking: request.thinking ?? false,
    max_steps: request.maxSteps,
    step_temperature: request.stepTemperature,
    final_temperature: request.finalTemperature,
    enable_skills: request.enableSkills,
    rag_knowledge_base_id: request.ragKnowledgeBaseId,
  }

  fetch('/api/agent-chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = (await response.json().catch(() => ({ detail: 'Agent chat request failed' }))) as {
          detail: string
        }
        throw new Error(error.detail || `HTTP ${response.status}`)
      }
      if (!response.body) throw new Error('Response body is empty')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let sawDone = false

      const processStream = async (): Promise<void> => {
        const { done, value } = await reader.read()
        if (done) {
          if (!sawDone) callbacks.onDone?.('stop')
          return
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const data = trimmed.slice(6)
          if (data === '[DONE]') continue

          try {
            const chunk = JSON.parse(data) as ChatChunk
            callbacks.onChunk?.(chunk)

            switch (chunk.type) {
              case 'text':
                if (chunk.content) callbacks.onText?.(chunk.content, chunk.step)
                break
              case 'thinking':
                if (chunk.content) callbacks.onThinking?.(chunk.content, chunk.step)
                break
              case 'action':
                if (chunk.name) callbacks.onAction?.(chunk.name, chunk.input ?? '', chunk.step ?? 0)
                break
              case 'observation':
                if (chunk.name) callbacks.onObservation?.(chunk.name, chunk.content ?? '', chunk.step ?? 0)
                break
              case 'warning':
                callbacks.onWarning?.(chunk.message ?? '', chunk.maxSteps)
                break
              case 'done':
                sawDone = true
                callbacks.onDone?.(chunk.finishReason || 'stop')
                break
              case 'error':
                if (chunk.message) callbacks.onError?.(new Error(chunk.message))
                break
            }
          } catch {
            // Ignore malformed SSE lines
          }
        }

        return processStream()
      }

      await processStream()
    })
    .catch((error) => {
      if (error.name === 'AbortError') return
      callbacks.onError?.(error instanceof Error ? error : new Error(String(error)))
    })
    .finally(finalize)

  return {
    abort: () => {
      if (finished) return
      abortController.abort()
      finalize()
    },
  }
}