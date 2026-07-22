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
      agentMode: false,
      selectedKbId: '',
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

  it('routes to /api/agent-chat when agentMode is on and accumulates steps into metadata', async () => {
    useWorkspaceStore.setState({ agentMode: true })

    fetchSpy.mockResolvedValue(
      mockResponse(
        sseStream([
          'data: {"type":"step_start","step":1,"label":"第 1 步"}\n',
          'data: {"type":"thinking","content":"t1","step":1}\n',
          'data: {"type":"text","content":"Action: echo","step":1}\n',
          'data: {"type":"action","name":"echo","input":"hello","step":1}\n',
          'data: {"type":"observation","name":"echo","content":"Observation: hello","step":1}\n',
          'data: {"type":"step_end","step":1,"finish":"tool"}\n',
          'data: {"type":"step_start","step":2,"label":"第 2 步"}\n',
          'data: {"type":"text","content":"Final Answer: Final answer.","step":2}\n',
          'data: {"type":"step_end","step":2,"finish":"final"}\n',
          'data: {"type":"done","finish_reason":"agent"}\n',
        ]),
      ),
    )

    const { result } = renderHook(() => useChatStream())
    act(() => {
      result.current.sendMessage('hi', [])
    })

    // fetch should target the agent endpoint.
    await vi.waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
      const url = (fetchSpy.mock.calls[0][0] as string) ?? ''
      expect(url).toBe('/api/agent-chat')
    })

    await vi.waitFor(() => {
      expect(useWorkspaceStore.getState().isStreaming).toBe(false)
    })

    const assistant = useWorkspaceStore
      .getState()
      .currentConversation!.messages.find((m) => m.role === 'assistant')
    expect(assistant?.status).toBe('done')
    // Phase 2b-ii: the body keeps only the final answer, prefix stripped.
    expect(assistant?.content).toBe('Final answer.')
    // thinking stays empty for agent messages — the trace lives in steps.
    expect(assistant?.thinking ?? '').toBe('')
    const meta = (assistant?.metadata ?? {}) as Record<string, unknown>
    expect(meta.agent).toBe(true)
    const steps = meta.steps as { finish: string; action?: { input: string } }[]
    expect(steps.length).toBe(2)
    expect(steps[0].finish).toBe('tool')
    expect(steps[0].action?.input).toBe('hello')
    expect(steps[1].finish).toBe('final')
  })

  it('agent mode persists retrieved chunks into the current step and a step_end error keeps the partial step', async () => {
    useWorkspaceStore.setState({ agentMode: true })

    fetchSpy.mockResolvedValue(
      mockResponse(
        sseStream([
          'data: {"type":"step_start","step":1,"label":"第 1 步"}\n',
          'data: {"type":"action","name":"retrieve_notes","input":"q","step":1}\n',
          'data: {"type":"retrieved","step":1,"docs":[{"doc_id":"d1","filename":"notes.md","heading":"安装","score":0.87,"text":"用 uv 安装。"}]}\n',
          'data: {"type":"step_end","step":1,"finish":"error"}\n',
          'data: {"type":"error","message":"boom"}\n',
        ]),
      ),
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
      expect(assistant?.content).toContain('Agent Error')
    })

    const assistant = useWorkspaceStore
      .getState()
      .currentConversation!.messages.find((m) => m.role === 'assistant')!
    const meta = assistant.metadata as Record<string, unknown>
    const steps = meta.steps as {
      finish: string
      retrieved?: { docId: string; filename: string; text: string }[] | null
    }[]
    // Partial step retained with its retrieved chunks + error finish.
    expect(steps.length).toBe(1)
    expect(steps[0].finish).toBe('error')
    expect(steps[0].retrieved?.[0].docId).toBe('d1')
    expect(steps[0].retrieved?.[0].filename).toBe('notes.md')
    expect(steps[0].retrieved?.[0].text).toBe('用 uv 安装。')
  })

  it('agent mode persists isStreaming=false and surfaces errors on error events', async () => {
    useWorkspaceStore.setState({ agentMode: true })

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
      expect(assistant?.content).toContain('Agent Error')
    })
    expect(useWorkspaceStore.getState().isStreaming).toBe(false)
  })

  it('sends rag_knowledge_base_id in the chat request body when a KB is selected', async () => {
    useWorkspaceStore.setState({ selectedKbId: 'kb-1' })

    fetchSpy.mockResolvedValue(
      mockResponse(sseStream(['data: {"type":"done","finish_reason":"stop"}\n'])),
    )

    const { result } = renderHook(() => useChatStream())
    act(() => {
      result.current.sendMessage('hi', [])
    })

    await vi.waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body.rag_knowledge_base_id).toBe('kb-1')
    expect(fetchSpy.mock.calls[0][0]).toBe('/api/chat')
  })

  it('sends rag_knowledge_base_id in the agent-chat request body when a KB is selected', async () => {
    useWorkspaceStore.setState({ agentMode: true, selectedKbId: 'kb-2' })

    fetchSpy.mockResolvedValue(
      mockResponse(sseStream(['data: {"type":"done","finish_reason":"agent"}\n'])),
    )

    const { result } = renderHook(() => useChatStream())
    act(() => {
      result.current.sendMessage('hi', [])
    })

    await vi.waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
    })
    const init = fetchSpy.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body.rag_knowledge_base_id).toBe('kb-2')
    expect(fetchSpy.mock.calls[0][0]).toBe('/api/agent-chat')
  })
})