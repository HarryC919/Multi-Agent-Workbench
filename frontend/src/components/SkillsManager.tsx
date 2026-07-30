import { useEffect, useState } from 'react'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useToastStore } from '@/store/toastStore'
import {
  fetchSkills,
  fetchMarkdownSkill,
  createMarkdownSkill,
  updateMarkdownSkill,
  deleteMarkdownSkill,
} from '@/api/skills'
import type { SkillManifestItem } from '@/types'

interface SkillsManagerProps {
  open: boolean
  onClose: () => void
}

const EMPTY_FORM = { name: '', description: '', content: '' }

export function SkillsManager({ open, onClose }: SkillsManagerProps) {
  const [skills, setSkills] = useState<SkillManifestItem[]>([])
  const [selected, setSelected] = useState<SkillManifestItem | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<SkillManifestItem | null>(null)

  const loadSkills = async () => {
    try {
      setSkills(await fetchSkills())
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '加载技能失败', 'error')
    }
  }

  useEffect(() => {
    if (open) {
      setSelected(null)
      setShowCreate(false)
      setForm(EMPTY_FORM)
      loadSkills()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const openEdit = async (skill: SkillManifestItem) => {
    if (skill.source !== 'markdown') return
    try {
      const src = await fetchMarkdownSkill(skill.name)
      setForm({ name: src.name, description: src.description, content: src.content })
      setSelected(skill)
      setShowCreate(false)
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '加载技能内容失败', 'error')
    }
  }

  const submitCreate = async () => {
    if (!form.name.trim() || !form.content.trim()) {
      useToastStore.getState().addToast('名称和内容不能为空', 'warning')
      return
    }
    setSaving(true)
    try {
      await createMarkdownSkill({
        name: form.name.trim(),
        description: form.description.trim(),
        content: form.content,
      })
      useToastStore.getState().addToast('技能已创建', 'success')
      setShowCreate(false)
      setForm(EMPTY_FORM)
      await loadSkills()
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '创建失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const submitUpdate = async () => {
    if (!selected || !form.content.trim()) return
    setSaving(true)
    try {
      await updateMarkdownSkill(selected.name, {
        description: form.description.trim(),
        content: form.content,
      })
      useToastStore.getState().addToast('技能已保存', 'success')
      setSelected(null)
      await loadSkills()
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '保存失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const doDelete = async () => {
    if (!confirmDelete) return
    try {
      await deleteMarkdownSkill(confirmDelete.name)
      useToastStore.getState().addToast('技能已删除', 'success')
      setSelected(null)
      setConfirmDelete(null)
      await loadSkills()
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '删除失败', 'error')
      setConfirmDelete(null)
    }
  }

  const isEditing = selected !== null
  const title = isEditing ? `编辑：${selected!.name}` : showCreate ? '新建技能' : 'Skills 管理'

  return (
    <Modal open={open} onClose={onClose} title={title} className="max-w-2xl">
      {/* ---- list view ---- */}
      {!isEditing && !showCreate && (
        <>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">共 {skills.length} 个技能</p>
            <Button size="sm" onClick={() => { setForm(EMPTY_FORM); setShowCreate(true) }}>
              <Plus className="mr-1 h-3 w-3" />
              新建技能
            </Button>
          </div>
          <ul className="space-y-1">
            {skills.map((skill) => (
              <li
                key={skill.name}
                className="flex items-center justify-between rounded-md border px-3 py-2"
              >
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => openEdit(skill)}
                  disabled={skill.source !== 'markdown'}
                >
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium">{skill.name}</span>
                    <span
                      className="shrink-0 rounded px-1.5 py-0.5 text-[10px]"
                      style={{
                        backgroundColor:
                          skill.source === 'markdown' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(100, 116, 139, 0.15)',
                        color: skill.source === 'markdown' ? 'rgb(37, 99, 235)' : 'rgb(100, 116, 139)',
                      }}
                    >
                      {skill.source === 'markdown' ? 'MD' : 'Python'}
                    </span>
                  </div>
                  {skill.description && (
                    <div className="truncate text-[11px] text-muted-foreground">{skill.description}</div>
                  )}
                </button>
              </li>
            ))}
            {skills.length === 0 && (
              <li className="px-3 py-6 text-center text-xs text-muted-foreground">
                暂无技能，点击右上角新建。
              </li>
            )}
          </ul>
        </>
      )}

      {/* ---- create form ---- */}
      {showCreate && !isEditing && (
        <div className="space-y-3">
          <Field label="名称" hint="仅字母/数字/下划线/连字符，创建后不可修改">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：translator"
              className="h-8 text-xs"
            />
          </Field>
          <Field label="描述" hint="可选">
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="一句话说明这个技能做什么"
              className="h-8 text-xs"
            />
          </Field>
          <Field label="指令内容">
            <textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="技能的 system prompt，告诉模型如何执行这个技能..."
              rows={8}
              className="w-full resize-y rounded-md border border-input bg-transparent p-3 font-mono text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>
              取消
            </Button>
            <Button variant="outline" size="sm" disabled={saving} onClick={submitCreate}>
              {saving ? '保存中...' : '保存'}
            </Button>
          </div>
        </div>
      )}

      {/* ---- edit view ---- */}
      {isEditing && (
        <div className="space-y-3">
          <div className="mb-1 flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
              <ArrowLeft className="mr-1 h-3 w-3" />
              返回
            </Button>
            <span className="text-xs text-muted-foreground">Markdown 技能</span>
          </div>
          <Field label="名称">
            <Input value={form.name} disabled className="h-8 text-xs" />
          </Field>
          <Field label="描述">
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="h-8 text-xs"
            />
          </Field>
          <Field label="指令内容">
            <textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              rows={10}
              className="w-full resize-y rounded-md border border-input bg-transparent p-3 font-mono text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </Field>
          <div className="flex justify-between pt-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive"
              onClick={() => setConfirmDelete(selected)}
            >
              <Trash2 className="mr-1 h-3 w-3" />
              删除
            </Button>
            <Button variant="outline" size="sm" disabled={saving} onClick={submitUpdate}>
              {saving ? '保存中...' : '保存'}
            </Button>
          </div>
        </div>
      )}

      {/* ---- delete confirmation (nested overlay; inline styles because Tailwind
           v4 @theme makes bg-* transparent - see ui/modal.tsx comment) ---- */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
        >
          <div
            className="w-72 rounded-lg border p-4 shadow-lg"
            style={{ backgroundColor: 'rgb(255, 255, 255)' }}
          >
            <p className="text-sm font-medium">删除该技能？</p>
            <p className="mt-1 text-xs text-muted-foreground">
              将删除「{confirmDelete.name}」的 .md 文件，此操作不可撤销。
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
