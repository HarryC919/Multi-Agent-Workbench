import { apiFetch } from './client'
import type { ModelConfig } from '@/types'

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

export async function createModel(model: Omit<ModelConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<ModelConfig> {
  return apiFetch<ModelConfig>('/api/models', {
    method: 'POST',
    body: JSON.stringify({
      model_id: model.modelId,
      vendor: model.vendor,
      name: model.name,
      adapter_type: model.adapterType,
      base_url: model.baseUrl,
      is_active: model.isActive,
    }),
  })
}

export async function updateModel(
  modelId: string,
  updates: Partial<Omit<ModelConfig, 'id' | 'modelId' | 'createdAt' | 'updatedAt'>>,
): Promise<ModelConfig> {
  return apiFetch<ModelConfig>(`/api/models/${modelId}`, {
    method: 'PUT',
    body: JSON.stringify({
      vendor: updates.vendor,
      name: updates.name,
      adapter_type: updates.adapterType,
      base_url: updates.baseUrl,
      is_active: updates.isActive,
    }),
  })
}

export async function deleteModel(modelId: string): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/models/${modelId}`, {
    method: 'DELETE',
  })
}
