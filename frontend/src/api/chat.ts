import type { ChatChunk, ChatRequest } from '@/types'

export interface ChatStreamCallbacks {
  onChunk?: (chunk: ChatChunk) => void
  onText?: (text: string) => void
  onThinking?: (text: string) => void
  onDone?: (finishReason: string) => void
  onError?: (error: Error) => void
  onFinally?: () => void
}

export function sendChatStream(
  request: ChatRequest,
  callbacks: ChatStreamCallbacks,
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
    effort: request.effort,
    files: request.files,
    stream: true,
    thinking: request.thinking ?? false,
    rag_knowledge_base_id: request.ragKnowledgeBaseId,
  }

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const error = (await response.json().catch(() => ({ detail: 'Chat request failed' }))) as {
          detail: string
        }
        throw new Error(error.detail || `HTTP ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is empty')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let sawDone = false

      const processStream = async (): Promise<void> => {
        const { done, value } = await reader.read()
        if (done) {
          if (!sawDone) {
            // Stream closed without an explicit done event; treat as finished.
            callbacks.onDone?.('stop')
          }
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

            if (chunk.type === 'text' && chunk.content) {
              callbacks.onText?.(chunk.content)
            } else if (chunk.type === 'thinking' && chunk.content) {
              callbacks.onThinking?.(chunk.content)
            } else if (chunk.type === 'done') {
              sawDone = true
              callbacks.onDone?.(chunk.finishReason || 'stop')
            } else if (chunk.type === 'error' && chunk.message) {
              callbacks.onError?.(new Error(chunk.message))
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
