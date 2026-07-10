import { snakeToCamel } from '@/lib/case'

const API_BASE = ''

export interface ApiError {
  detail: string
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = (await response.json().catch(() => ({ detail: 'Unknown error' }))) as ApiError
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const data = (await response.json()) as unknown
  return snakeToCamel<T>(data)
}
