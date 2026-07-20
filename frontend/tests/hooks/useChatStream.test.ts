import { describe, it, expect, beforeEach, afterEach, vi, type MockInstance } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useChatStream } from '@/hooks/useChatStream'
import { useWorkspaceStore } from '@/store/workspaceStore'

// Build a fake SSE response body as a ReadableStream.
function sseStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

function mockResponse(body: ReadableStream<Uint8Array>, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    body,
    json: async () => ({ detail: 'Chat request failed' }),
  } as unknown as Response
}

describe('useChatStream', () => {
  let fetchSpy: MockInstance

  beforeEach(() => {
    fetchSpy = vi.spyOn(global, 'fetch')

    // Seed the store with an active conversation + model.
    useWorkspaceStore.setState({
      conversations: [
        {
          id: 'conv1',
          title: 'test',
          createdAt: '2026-01-01T00:00:00Z',
          updatedAt: '2026-01-01T00:00:00Z',
        },
      ],
      activeId: 'conv1',
      currentConversation: {
        id: 'conv1',
        title: 'test',
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
        messages: [],
      },
      selectedModel: 'mock-model',
      isStreaming: false,
    })
  })

  afterEach(() => {
    fetchSpy.mockRestore()
    useWorkspaceStore.setState({
      conversations: [],
      activeId: null,
      currentConversation: null,
      isStreaming: false,
    })
  })

  it('appends text chunks to the assistant message and marks done on stream end', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(
        sseStream([
          'data: {"type":"text","content":"Hel"}\n',
          'data: {"type":"text","content":"lo"}\n',
          'data: {"type":"done","finish_reason":"stop"}\n',
        ]),
      ),
    )

    const { result } = renderHook(() => useChatStream())

    act(() => {
      result.current.sendMessage('hi', [])
    })

    // Wait for the async stream to drain.
    await vi.waitFor(() => {
      const msgs = useWorkspaceStore.getState().currentConversation?.messages ?? []
      expect(msgs.some((m) => m.role === 'assistant' && m.content === 'Hello')).toBe(true)
    })

    expect(useWorkspaceStore.getState().isStreaming).toBe(false)
    const assistant = useWorkspaceStore
      .getState()
      .currentConversation!.messages.find((m) => m.role === 'assistant')
    expect(assistant?.status).toBe('done')
  })

  it('resets isStreaming via onFinally even when only a done event arrives', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(sseStream(['data: {"type":"done","finish_reason":"stop"}\n'])),
    )

    const { result } = renderHook(() => useChatStream())

    act(() => {
      result.current.sendMessage('hi', [])
    })

    await vi.waitFor(() => {
      expect(useWorkspaceStore.getState().isStreaming).toBe(false)
    })
  })

  it('marks assistant as error on error chunks and still resets isStreaming', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(sseStream(['data: {"type":"error","message":"boom"}\n'])),
    )

    const { result } = renderHook(() => useChatStream())

    act(() => {
      result.current.sendMessage('hi', [])
    })

    await vi.waitFor(() => {
      const assistant = useWorkspaceStore
        .getState()
        .currentConversation!.messages.find((m) => m.role === 'assistant')
      expect(assistant?.status).toBe('error')
      expect(assistant?.content).toContain('boom')
    })
    expect(useWorkspaceStore.getState().isStreaming).toBe(false)
  })

  it('aborts the in-flight request without throwing an unhandled rejection', async () => {
    fetchSpy.mockImplementation((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        const signal = (init as RequestInit | undefined)?.signal
        signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
      })
    })

    const { result } = renderHook(() => useChatStream())

    act(() => {
      result.current.sendMessage('hi', [])
    })

    await act(async () => {
      result.current.abort()
      // Allow microtasks to drain.
      await Promise.resolve()
    })

    expect(useWorkspaceStore.getState().isStreaming).toBe(false)
  })
})