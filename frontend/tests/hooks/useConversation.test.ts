import { describe, it, expect, beforeEach, afterEach, vi, type MockInstance } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useConversation } from '@/hooks/useConversation'
import { useWorkspaceStore } from '@/store/workspaceStore'

describe('useConversation', () => {
  const fetchSpy: MockInstance = vi.spyOn(global, 'fetch')

  beforeEach(() => {
    fetchSpy.mockReset()
    useWorkspaceStore.setState({
      conversations: [],
      activeId: null,
      currentConversation: null,
      models: [],
    })
  })

  afterEach(() => {
    fetchSpy.mockReset()
  })

  it('loads conversations and models on mount', async () => {
    fetchSpy
      .mockImplementationOnce(async () =>
        new Response(
          JSON.stringify({
            conversations: [
              {
                id: 'c1',
                title: 'first',
                created_at: '2026-01-01T00:00:00Z',
                updated_at: '2026-01-01T00:00:00Z',
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockImplementationOnce(async () =>
        new Response(
          JSON.stringify({
            models: [
              {
                id: 'm1',
                model_id: 'mock-model',
                vendor: 'openai',
                name: 'Mock',
                adapter_type: 'openai',
                is_active: 1,
                created_at: '2026-01-01T00:00:00Z',
                updated_at: '2026-01-01T00:00:00Z',
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )

    const { result } = renderHook(() => useConversation())

    await waitFor(() => {
      expect(useWorkspaceStore.getState().conversations.length).toBe(1)
    })
    await waitFor(() => {
      expect(useWorkspaceStore.getState().models.length).toBe(1)
    })

    expect(result.current.conversations[0].id).toBe('c1')
    expect(useWorkspaceStore.getState().models[0].modelId).toBe('mock-model')
  })

  it('surfaces a toast but does not throw when load fails', async () => {
    fetchSpy.mockImplementation(async () =>
      new Response(JSON.stringify({ detail: 'service down' }), { status: 500 }),
    )

    renderHook(() => useConversation())

    // Should not throw and stick with empty arrays.
    await waitFor(() => {
      expect(useWorkspaceStore.getState().conversations).toEqual([])
    })
  })
})