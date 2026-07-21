import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, FileText, Plus, Trash2 } from 'lucide-react'
import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useWorkspaceStore } from '@/store/workspaceStore'
import { useToastStore } from '@/store/toastStore'
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  deleteDocument,
  listDocuments,
  uploadDocument,
} from '@/api/knowledge'
import type { KnowledgeBase, KnowledgeDoc } from '@/types'

interface KnowledgeBaseManagerProps {
  open: boolean
  onClose: () => void
}

const EMPTY_FORM = { name: '', description: '' }

export function KnowledgeBaseManager({ open, onClose }: KnowledgeBaseManagerProps) {
  const store = useWorkspaceStore()
  // Local copy of KBs so the list refreshes after create/delete without
  // mutating the global store mid-flow.
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [selectedKb, setSelectedKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<KnowledgeDoc[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [confirmDeleteKb, setConfirmDeleteKb] = useState<KnowledgeBase | null>(null)
  const [confirmDeleteDoc, setConfirmDeleteDoc] = useState<KnowledgeDoc | null>(null)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadKbs = async () => {
    try {
      await store.loadKnowledgeBases()
      // Read fresh from the store — the captured `store` snapshot above is
      // stale after loadKnowledgeBases' internal set().
      setKbs(useWorkspaceStore.getState().knowledgeBases)
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '加载知识库失败', 'error')
    }
  }

  const loadDocs = async (kbId: string) => {
    try {
      const result = await listDocuments(kbId)
      setDocs(result || [])
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '加载文档失败', 'error')
    }
  }

  useEffect(() => {
    if (open) {
      setSelectedKb(null)
      setShowCreate(false)
      setForm(EMPTY_FORM)
      loadKbs()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // When a KB is selected, load its documents.
  useEffect(() => {
    if (selectedKb) loadDocs(selectedKb.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKb])

  const submitCreate = async () => {
    if (!form.name.trim()) {
      useToastStore.getState().addToast('请填写知识库名称', 'warning')
      return
    }
    setSaving(true)
    try {
      const created = await createKnowledgeBase({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      store.addKnowledgeBase(created)
      setKbs((prev) => [...prev, created])
      setShowCreate(false)
      setForm(EMPTY_FORM)
      useToastStore.getState().addToast('知识库已创建', 'success')
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '创建失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  const doDeleteKb = async () => {
    if (!confirmDeleteKb) return
    try {
      await deleteKnowledgeBase(confirmDeleteKb.id)
      store.removeKnowledgeBase(confirmDeleteKb.id)
      setKbs((prev) => prev.filter((k) => k.id !== confirmDeleteKb.id))
      if (selectedKb?.id === confirmDeleteKb.id) setSelectedKb(null)
      useToastStore.getState().addToast('知识库已删除', 'success')
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '删除失败', 'error')
    } finally {
      setConfirmDeleteKb(null)
    }
  }

  const doDeleteDoc = async () => {
    if (!confirmDeleteDoc || !selectedKb) return
    try {
      await deleteDocument(selectedKb.id, confirmDeleteDoc.id)
      setDocs((prev) => prev.filter((d) => d.id !== confirmDeleteDoc.id))
      useToastStore.getState().addToast('文档已删除', 'success')
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '删除失败', 'error')
    } finally {
      setConfirmDeleteDoc(null)
    }
  }

  const handleFile = async (file: File | undefined) => {
    if (!file || !selectedKb) return
    setUploading(true)
    try {
      const doc = await uploadDocument(selectedKb.id, file)
      useToastStore
        .getState()
        .addToast(`已上传「${doc.filename}」(${doc.textLength} 字符)`, 'success')
      await loadDocs(selectedKb.id)
    } catch (err) {
      useToastStore
        .getState()
        .addToast(err instanceof Error ? err.message : '上传失败', 'error')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={selectedKb ? selectedKb.name : '知识库管理'}
      className="max-w-2xl"
    >
      {!selectedKb ? (
        !showCreate ? (
          <>
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs text-muted-foreground">共 {kbs.length} 个知识库</p>
              <Button size="sm" onClick={() => setShowCreate(true)}>
                <Plus className="mr-1 h-3 w-3" />
                新建知识库
              </Button>
            </div>
            <ul className="space-y-1">
              {kbs.map((kb) => (
                <li
                  key={kb.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => setSelectedKb(kb)}
                  >
                    <div className="truncate text-sm font-medium">{kb.name}</div>
                    {kb.description && (
                      <div className="truncate text-[11px] text-muted-foreground">
                        {kb.description}
                      </div>
                    )}
                  </button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive"
                    onClick={() => setConfirmDeleteKb(kb)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </li>
              ))}
              {kbs.length === 0 && (
                <li className="px-3 py-6 text-center text-xs text-muted-foreground">
                  暂无知识库，点击右上角新建。
                </li>
              )}
            </ul>
          </>
        ) : (
          <div className="space-y-3">
            <Field label="名称">
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="如：我的笔记"
                className="h-8 text-xs"
              />
            </Field>
            <Field label="描述" hint="可选">
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="h-8 text-xs"
              />
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>
                取消
              </Button>
              <Button size="sm" disabled={saving} onClick={submitCreate}>
                {saving ? '保存中...' : '保存'}
              </Button>
            </div>
          </div>
        )
      ) : (
        <>
          <div className="mb-3 flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelectedKb(null)}>
              <ArrowLeft className="mr-1 h-3 w-3" />
              返回
            </Button>
            <span className="text-xs text-muted-foreground">
              共 {docs.length} 个文档
            </span>
          </div>

          <div className="mb-3 flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.txt"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            <Button
              size="sm"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              <Plus className="mr-1 h-3 w-3" />
              {uploading ? '上传中...' : '上传文档'}
            </Button>
            <span className="text-[10px] text-muted-foreground">
              仅支持 .md / .markdown / .txt
            </span>
          </div>

          <ul className="space-y-1">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between rounded-md border px-3 py-2"
              >
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <FileText className="h-3 w-3 shrink-0 text-muted-foreground" />
                  <span className="truncate text-sm">{doc.filename}</span>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => setConfirmDeleteDoc(doc)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </li>
            ))}
            {docs.length === 0 && (
              <li className="px-3 py-6 text-center text-xs text-muted-foreground">
                暂无文档，上传 markdown / txt 笔记后即可在对话中检索。
              </li>
            )}
          </ul>
        </>
      )}

      {/* Delete KB confirmation (nested overlay; inline styles because Tailwind
          v4 @theme makes bg-* transparent — see ui/modal.tsx comment). */}
      {confirmDeleteKb && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
        >
          <div
            className="w-72 rounded-lg border p-4 shadow-lg"
            style={{ backgroundColor: 'rgb(255, 255, 255)' }}
          >
            <p className="text-sm font-medium">删除该知识库？</p>
            <p className="mt-1 text-xs text-muted-foreground">
              将删除「{confirmDeleteKb.name}」及其全部文档与向量索引，此操作不可撤销。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmDeleteKb(null)}>
                取消
              </Button>
              <Button variant="destructive" size="sm" onClick={doDeleteKb}>
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete document confirmation */}
      {confirmDeleteDoc && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
        >
          <div
            className="w-72 rounded-lg border p-4 shadow-lg"
            style={{ backgroundColor: 'rgb(255, 255, 255)' }}
          >
            <p className="text-sm font-medium">删除该文档？</p>
            <p className="mt-1 text-xs text-muted-foreground">
              将删除「{confirmDeleteDoc.filename}」及其向量索引。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmDeleteDoc(null)}>
                取消
              </Button>
              <Button variant="destructive" size="sm" onClick={doDeleteDoc}>
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
