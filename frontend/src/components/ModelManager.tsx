import { useEffect, useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useToastStore } from '@/store/toastStore'
import {
  createModel,
  deleteModel,
  fetchAllModels,
  updateModel,
} from '@/api/models'
import type { AdapterType, ModelConfig } from '@/types'

interface ModelManagerProps {
  open: boolean
  onClose: () => void
}

const ADAPTER_TYPES: { value: AdapterType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'openai_compatible', label: 'OpenAI 兼容' },
  { value: 'anthropic_compatible', label: 'Anthropic 兼容' },
]

const EMPTY_FORM: ModelFormState = {
  modelId: '',
  name: '',
  vendor: '',
  adapterType: 'openai_compatible',
  baseUrl: '',
  apiKey: '',
  isActive: true,
}

interface ModelFormState {
  modelId: string
  name: string
  vendor: string
  adapterType: AdapterType
  baseUrl: string
  apiKey: string
  isActive: boolean
}

export function ModelManager({ open, onClose }: ModelManagerProps) {
  const store = useWorkspaceStore()
  const [allModels, setAllModels] = useState<ModelConfig[]>([])
  const [editing, setEditing] = useState<ModelConfig | null>(null)
  const [form, setForm] = useState<ModelFormState>(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<ModelConfig | null>(null)
  const [saving, setSaving] = useState(false)

  const loadAll = async () => {
    try {
      const models = await fetchAllModels()
      setAllModels(models || [])
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '加载模型失败', 'error')
    }
  }

  useEffect(() => {
    if (open) loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
  }

  const openEdit = (model: ModelConfig) => {
    setEditing(model)
    setForm({
      modelId: model.modelId,
      name: model.name,
      vendor: model.vendor,
      adapterType: model.adapterType,
      baseUrl: model.baseUrl ?? '',
      // Key is never returned by the API; start empty. Leaving empty on save
      // means "keep existing key" (update drops undefined). Typing anything
      // replaces it.
      apiKey: '',
      isActive: model.isActive,
    })
    setShowForm(true)
  }

  const submitForm = async () => {
    if (!form.modelId.trim() || !form.name.trim() || !form.vendor.trim()) {
      useToastStore.getState().addToast('请填写 model_id、名称、vendor', 'warning')
      return
    }
    const isCompatible =
      form.adapterType === 'openai_compatible' || form.adapterType === 'anthropic_compatible'
    // Compatible adapters typically point at a third-party endpoint whose key
    // is not in .env, so require one on create. On edit, an empty field means
    // "keep existing", so only require it when none is configured yet.
    if (isCompatible && !editing && !form.apiKey.trim()) {
      useToastStore.getState().addToast('兼容适配器需要填写 API Key', 'warning')
      return
    }
    setSaving(true)
    try {
      if (editing) {
        const updated = await updateModel(editing.modelId, {
          name: form.name,
          vendor: form.vendor,
          adapterType: form.adapterType,
          baseUrl: form.baseUrl || undefined,
          // Only send apiKey when the user typed something; empty = keep.
          ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
          isActive: form.isActive,
        })
        store.updateModel(updated)
      } else {
        const created = await createModel({
          modelId: form.modelId,
          name: form.name,
          vendor: form.vendor,
          adapterType: form.adapterType,
          baseUrl: form.baseUrl || undefined,
          apiKey: form.apiKey.trim() || undefined,
          isActive: form.isActive,
        })
        store.addModel(created)
      }
      await loadAll()
      setShowForm(false)
      useToastStore.getState().addToast(editing ? '模型已更新' : '模型已添加', 'success')
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '保存失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (model: ModelConfig) => {
    try {
      const updated = await updateModel(model.modelId, { isActive: !model.isActive })
      store.updateModel(updated)
      await loadAll()
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '更新失败', 'error')
    }
  }

  const doDelete = async () => {
    if (!confirmDelete) return
    try {
      await deleteModel(confirmDelete.modelId)
      store.removeModel(confirmDelete.modelId)
      await loadAll()
      useToastStore.getState().addToast('模型已删除', 'success')
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '删除失败', 'error')
    } finally {
      setConfirmDelete(null)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="模型管理" className="max-w-2xl">
      {!showForm ? (
        <>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">共 {allModels.length} 个模型</p>
            <Button size="sm" onClick={openCreate}>
              <Plus className="mr-1 h-3 w-3" />
              新增模型
            </Button>
          </div>
          <ul className="space-y-1">
            {allModels.map((model) => (
              <li
                key={model.id}
                className="flex items-center justify-between rounded-md border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{model.name}</span>
                    {model.hasApiKey && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        已配Key
                      </span>
                    )}
                    {!model.isActive && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        已禁用
                      </span>
                    )}
                  </div>
                  <div className="truncate text-[11px] text-muted-foreground">
                    {model.modelId} · {model.vendor} · {model.adapterType}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleActive(model)}
                  >
                    {model.isActive ? '禁用' : '启用'}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(model)}>
                    <Pencil className="h-3 w-3" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive"
                    onClick={() => setConfirmDelete(model)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="space-y-3">
          <Field label="Model ID" hint={editing ? '不可修改' : '唯一标识，如 glm-5.2'}>
            <Input
              value={form.modelId}
              disabled={!!editing}
              onChange={(e) => setForm({ ...form, modelId: e.target.value })}
              className="h-8 text-xs"
            />
          </Field>
          <Field label="显示名称">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="h-8 text-xs"
            />
          </Field>
          <Field label="Vendor" hint="厂商标识，需与后端 .env 配置的 key 对应，如 openai / glm / deepseek">
            <Input
              value={form.vendor}
              onChange={(e) => setForm({ ...form, vendor: e.target.value })}
              className="h-8 text-xs"
            />
          </Field>
          <Field label="Adapter Type">
            <select
              value={form.adapterType}
              onChange={(e) => setForm({ ...form, adapterType: e.target.value as AdapterType })}
              className="h-8 w-full rounded-md border border-input bg-transparent px-2 text-xs"
            >
              {ADAPTER_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Base URL" hint="可选，留空使用后端默认">
            <Input
              value={form.baseUrl}
              onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
              placeholder="https://..."
              className="h-8 text-xs"
            />
          </Field>
          <Field
            label="API Key"
            hint={
              editing
                ? editing.hasApiKey
                  ? '已配置。留空保持不变，输入新值则替换。'
                  : '尚未配置。留空则使用 .env 中该 vendor 的 key（若有）。'
                : '可选。兼容适配器（openai/anthropic compatible）建议填写，调用时优先使用此 key。'
            }
          >
            <Input
              type="password"
              value={form.apiKey}
              onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
              placeholder={editing && editing.hasApiKey ? '••••••（留空不改）' : 'sk-...'}
              className="h-8 text-xs"
            />
          </Field>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={form.isActive}
              onChange={(e) => setForm({ ...form, isActive: e.target.checked })}
            />
            启用此模型
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>
              取消
            </Button>
            <Button size="sm" disabled={saving} onClick={submitForm}>
              {saving ? '保存中...' : '保存'}
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirmation (nested inside manager modal) */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
        >
          <div
            className="w-72 rounded-lg border p-4 shadow-lg"
            style={{ backgroundColor: 'rgb(255, 255, 255)' }}
          >
            <p className="text-sm font-medium">删除该模型？</p>
            <p className="mt-1 text-xs text-muted-foreground">
              将删除「{confirmDelete.name}」，此操作不可撤销。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmDelete(null)}>
                取消
              </Button>
              <Button variant="destructive" size="sm" onClick={doDelete}>
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium">{label}</label>
      {children}
      {hint && <p className="mt-1 text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  )
}
