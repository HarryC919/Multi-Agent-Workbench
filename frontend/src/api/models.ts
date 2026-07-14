import { apiFetch } from './client'
import type { AdapterType, ModelConfig } from '@/types'

export interface ModelsResponse {
  models: ModelConfig[]
}

export async function fetchModels(): Promise<ModelConfig[]> {
  const data = await apiFetch<ModelsResponse>('/api/models')
  return data.models
}

export async function fetchAllModels(): Promise<ModelConfig[]> {
  const data = await apiFetch<ModelsResponse>('/api/models/all')
  return data.models
}

export interface ModelCreatePayload {
  modelId: string
  vendor: string
  name: string
  adapterType: AdapterType
  baseUrl?: string
  apiKey?: string
  isActive: boolean
}

export async function createModel(model: ModelCreatePayload): Promise<ModelConfig> {
  return apiFetch<ModelConfig>('/api/models', {
    method: 'POST',
    body: JSON.stringify({
      model_id: model.modelId,
      vendor: model.vendor,
      name: model.name,
      adapter_type: model.adapterType,
      base_url: model.baseUrl,
      api_key: model.apiKey,
      is_active: model.isActive,
    }),
  })
}

export interface ModelUpdatePayload {
  vendor?: string
  name?: string
  adapterType?: AdapterType
  baseUrl?: string
  /** Set to a string to update the key, '' to clear it, or omit to leave
   *  unchanged. undefined is dropped from the request body below. */
  apiKey?: string
  isActive?: boolean
}

export async function updateModel(
  modelId: string,
  updates: ModelUpdatePayload,
): Promise<ModelConfig> {
  // Build the body with snake_case keys, dropping undefined so the backend's
  // exclude_unset semantics treat absent fields as "leave unchanged".
  const body: Record<string, unknown> = {}
  if (updates.vendor !== undefined) body.vendor = updates.vendor
  if (updates.name !== undefined) body.name = updates.name
  if (updates.adapterType !== undefined) body.adapter_type = updates.adapterType
  if (updates.baseUrl !== undefined) body.base_url = updates.baseUrl
  if (updates.apiKey !== undefined) body.api_key = updates.apiKey
  if (updates.isActive !== undefined) body.is_active = updates.isActive

  return apiFetch<ModelConfig>(`/api/models/${modelId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function deleteModel(modelId: string): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/models/${modelId}`, {
    method: 'DELETE',
  })
}
