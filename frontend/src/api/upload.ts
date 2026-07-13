import { snakeToCamel } from '@/lib/case'
import type { UploadFileResponse } from '@/types'

export async function uploadFile(file: File): Promise<UploadFileResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = (await response.json().catch(() => ({ detail: 'Upload failed' }))) as { detail: string }
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  const data = (await response.json()) as unknown
  return snakeToCamel<UploadFileResponse>(data)
}
