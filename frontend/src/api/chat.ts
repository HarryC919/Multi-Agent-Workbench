import type { ChatChunk, ChatRequest } from '@/types'

export interface ChatStreamCallbacks {
  onChunk?: (chunk: ChatChunk) => void
  onText?: (text: string) => void
  onDone?: (finishReason: string) => void
  onError?: (error: Error) => void
}

export function sendChatStream(
  request: ChatRequest,
  callbacks: ChatStreamCallbacks,
): { abort: () => void } {
  const abortController = new AbortController()

  const payload: Record<string, unknown> = {
    conversation_id: request.conversationId,
    model: request.model,
    messages: request.messages,
    effort: request.effort,
    files: request.files,
    stream: true,
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

      const processStream = async (): Promise<void> => {
        const { done, value } = await reader.read()
        if (done) return

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
            } else if (chunk.type === 'done' && chunk.finishReason) {
              callbacks.onDone?.(chunk.finishReason)
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

  return {
    abort: () => abortController.abort(),
  }
}
