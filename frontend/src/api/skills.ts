import { apiFetch } from './client'
import type { SkillManifestItem, MarkdownSkillSource } from '@/types'

// ---------------------------------------------------------------------------
// Skills API client. All endpoints return JSON (no multipart), so apiFetch
// handles snake_case -> camelCase conversion automatically.
// ---------------------------------------------------------------------------

export interface SkillsResponse {
  skills: SkillManifestItem[]
}

export async function fetchSkills(): Promise<SkillManifestItem[]> {
  const data = await apiFetch<SkillsResponse>('/api/skills')
  return data.skills
}

export async function fetchMarkdownSkill(name: string): Promise<MarkdownSkillSource> {
  return apiFetch<MarkdownSkillSource>(`/api/skills/md/${name}`)
}

export interface MarkdownSkillCreatePayload {
  name: string
  description: string
  content: string
}

export async function createMarkdownSkill(
  payload: MarkdownSkillCreatePayload,
): Promise<{ name: string }> {
  return apiFetch<{ name: string }>('/api/skills/md', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export interface MarkdownSkillUpdatePayload {
  description?: string
  content: string
}

export async function updateMarkdownSkill(
  name: string,
  payload: MarkdownSkillUpdatePayload,
): Promise<{ name: string }> {
  return apiFetch<{ name: string }>(`/api/skills/md/${name}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteMarkdownSkill(name: string): Promise<{ deleted: string }> {
  return apiFetch<{ deleted: string }>(`/api/skills/md/${name}`, {
    method: 'DELETE',
  })
}

export async function reloadSkills(): Promise<{ reloaded: number }> {
  return apiFetch<{ reloaded: number }>('/api/skills/reload', {
    method: 'POST',
  })
}
