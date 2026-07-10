import { apiFetch } from './client'
import type { Conversation, ConversationDetail } from '@/types'

export interface ConversationsResponse {
  conversations: Conversation[]
}

export async function fetchConversations(query?: string): Promise<Conversation[]> {
  const params = query ? `?q=${encodeURIComponent(query)}` : ''
  const data = await apiFetch<ConversationsResponse>(`/api/conversations${params}`)
  return data.conversations
}

export async function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/conversations/${id}`)
}

export async function renameConversation(id: string, title: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export async function deleteConversation(id: string): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/conversations/${id}`, {
    method: 'DELETE',
  })
}
