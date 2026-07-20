import { useEffect, useState } from 'react'
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { Conversation } from '@/types'

interface ConversationListProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

interface MenuState {
  conversationId: string
  x: number
  y: number
}

const MENU_WIDTH = 128
const MENU_HEIGHT = 64

function clampMenuPosition(x: number, y: number) {
  const maxX = window.innerWidth - MENU_WIDTH - 8
  const maxY = window.innerHeight - MENU_HEIGHT - 8
  return { x: Math.min(Math.max(x, 8), Math.max(8, maxX)), y: Math.min(Math.max(y, 8), Math.max(8, maxY)) }
}

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onRename,
  onDelete,
}: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  // Menu opened via the "⋯" button (positioned relative to the button).
  const [buttonMenuId, setButtonMenuId] = useState<string | null>(null)
  // Menu opened via right-click (positioned at the cursor, fixed).
  const [contextMenu, setContextMenu] = useState<MenuState | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const openMenu = (conversation: Conversation, x: number, y: number) => {
    setButtonMenuId(null)
    setContextMenu({ conversationId: conversation.id, ...clampMenuPosition(x, y) })
  }

  const closeMenus = () => {
    setButtonMenuId(null)
    setContextMenu(null)
  }

  // Close menus on outside click / Escape. We listen for mousedown and check
  // whether the target is inside a menu; clicking a menu item must NOT close
  // the menu before its onClick fires (mousedown precedes click), so we only
  // close when the press lands outside any menu element.
  useEffect(() => {
    if (!buttonMenuId && !contextMenu) return
    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (target.closest('[data-menu]')) return
      closeMenus()
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMenus()
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKey)
    }
  }, [buttonMenuId, contextMenu])

  const startRename = (conversation: Conversation) => {
    setEditingId(conversation.id)
    setEditTitle(conversation.title)
    closeMenus()
  }

  const submitRename = () => {
    if (editingId && editTitle.trim()) {
      onRename(editingId, editTitle.trim())
    }
    setEditingId(null)
  }

  const requestDelete = (id: string) => {
    closeMenus()
    setConfirmDeleteId(id)
  }

  const confirmDelete = () => {
    if (confirmDeleteId) {
      onDelete(confirmDeleteId)
    }
    setConfirmDeleteId(null)
  }

  // Shared menu item list — used by both the "⋯" button menu and the
  // right-click context menu so behavior stays consistent.
  const renderMenuItems = (conversation: Conversation) => (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation()
          startRename(conversation)
        }}
        className="flex w-full items-center rounded-sm px-2 py-1 text-xs hover:bg-accent"
      >
        <Pencil className="mr-2 h-3 w-3" />
        重命名
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation()
          requestDelete(conversation.id)
        }}
        className="flex w-full items-center rounded-sm px-2 py-1 text-xs text-destructive hover:bg-accent"
      >
        <Trash2 className="mr-2 h-3 w-3" />
        删除
      </button>
    </>
  )

  return (
    <div className="flex-1 overflow-auto p-2">
      {conversations.length === 0 ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">暂无会话</p>
      ) : (
        <ul className="space-y-1">
          {conversations.map((conversation) => (
            <li key={conversation.id} className="relative group">
              {editingId === conversation.id ? (
                <Input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onBlur={submitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') submitRename()
                    if (e.key === 'Escape') setEditingId(null)
                  }}
                  autoFocus
                  className="h-8 text-xs"
                />
              ) : (
                <button
                  onClick={() => onSelect(conversation.id)}
                  onContextMenu={(e) => {
                    e.preventDefault()
                    openMenu(conversation, e.clientX, e.clientY)
                  }}
                  className={cn(
                    'flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors',
                    activeId === conversation.id
                      ? 'bg-accent text-accent-foreground'
                      : 'hover:bg-muted',
                  )}
                >
                  <span className="min-w-0 flex-1 truncate pr-2" title={conversation.title}>{conversation.title}</span>
                  <div className="relative">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 focus:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation()
                        setButtonMenuId(buttonMenuId === conversation.id ? null : conversation.id)
                        setContextMenu(null)
                      }}
                    >
                      <MoreHorizontal className="h-3 w-3" />
                    </Button>
                    {buttonMenuId === conversation.id && (
                      <div
                        data-menu
                        className="absolute right-0 top-6 z-10 w-32 rounded-md border bg-background p-1 shadow-md"
                        style={{ backgroundColor: 'rgb(255, 255, 255)' }}
                      >
                        {renderMenuItems(conversation)}
                      </div>
                    )}
                  </div>
                </button>
              )}
              <p className="px-3 text-[10px] text-muted-foreground">
                {conversation.updatedAt && !isNaN(new Date(conversation.updatedAt).getTime())
                  ? formatDistanceToNow(new Date(conversation.updatedAt), {
                      addSuffix: true,
                      locale: zhCN,
                    })
                  : ''}
              </p>
            </li>
          ))}
        </ul>
      )}

      {/* Right-click context menu (fixed positioning at cursor) */}
      {contextMenu && (
        <div
          data-menu
          className="fixed z-50 w-32 rounded-md border bg-background p-1 shadow-md"
          style={{ left: contextMenu.x, top: contextMenu.y, backgroundColor: 'rgb(255, 255, 255)' }}
        >
          {conversations.find((c) => c.id === contextMenu.conversationId) &&
            renderMenuItems(conversations.find((c) => c.id === contextMenu.conversationId)!)}
        </div>
      )}

      {/* Delete confirmation dialog */}
      {confirmDeleteId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: 'rgba(0, 0, 0, 0.4)' }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setConfirmDeleteId(null)
          }}
        >
          <div
            className="w-72 rounded-lg border p-4 shadow-lg"
            style={{ backgroundColor: 'rgb(255, 255, 255)' }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <p className="text-sm font-medium">删除该会话？</p>
            <p className="mt-1 text-xs text-muted-foreground">此操作不可撤销，会话及其所有消息将被删除。</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmDeleteId(null)}>
                取消
              </Button>
              <Button variant="destructive" size="sm" onClick={confirmDelete}>
                确认删除
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
