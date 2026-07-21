import { apiFetch } from './client'
import { snakeToCamel } from '@/lib/case'
import type { KnowledgeBase, KnowledgeDoc, DocumentUploadResponse } from '@/types'

// ---------------------------------------------------------------------------
// Knowledge base CRUD (mirrors api/models.ts). The backend stores snake_case;
// apiFetch applies snakeToCamel to responses automatically.
// ---------------------------------------------------------------------------

export interface KnowledgeBasesResponse {
  knowledgeBases: KnowledgeBase[]
}

export async function fetchKnowledgeBases(): Promise<KnowledgeBase[]> {
  const data = await apiFetch<KnowledgeBasesResponse>('/api/knowledge-bases')
  return data.knowledgeBases
}

export interface KnowledgeBaseCreatePayload {
  name: string
  description?: string
}

export async function createKnowledgeBase(
  payload: KnowledgeBaseCreatePayload,
): Promise<KnowledgeBase> {
  return apiFetch<KnowledgeBase>('/api/knowledge-bases', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? '',
    }),
  })
}

export async function deleteKnowledgeBase(
  kbId: string,
): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/knowledge-bases/${kbId}`, {
    method: 'DELETE',
  })
}

// ---------------------------------------------------------------------------
// Document management.
// ---------------------------------------------------------------------------

export interface KnowledgeDocsResponse {
  documents: KnowledgeDoc[]
}

export async function listDocuments(kbId: string): Promise<KnowledgeDoc[]> {
  const data = await apiFetch<KnowledgeDocsResponse>(
    `/api/knowledge-bases/${kbId}/documents`,
  )
  return data.documents
}

export async function deleteDocument(
  kbId: string,
  docId: string,
): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(
    `/api/knowledge-bases/${kbId}/documents/${docId}`,
    { method: 'DELETE' },
  )
}

/** Upload a markdown/text document. Bypasses apiFetch because it forces
 *  Content-Type: application/json, which would break the multipart boundary.
 *  Mirrors api/upload.ts. The backend accepts .md/.markdown/.txt only. */
export async function uploadDocument(
  kbId: string,
  file: File,
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`/api/knowledge-bases/${kbId}/documents`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = (await response.json().catch(() => ({ detail: 'Upload failed' }))) as {
      detail: string
    }
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const data = (await response.json()) as unknown
  return snakeToCamel<DocumentUploadResponse>(data)
}
