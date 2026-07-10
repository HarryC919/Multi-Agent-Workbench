import { useState } from 'react'
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

export function ConversationList({
  conversations,
  activeId,
  onSelect,
  onRename,
  onDelete,
}: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  const startRename = (conversation: Conversation) => {
    setEditingId(conversation.id)
    setEditTitle(conversation.title)
    setMenuOpenId(null)
  }

  const submitRename = () => {
    if (editingId && editTitle.trim()) {
      onRename(editingId, editTitle.trim())
    }
    setEditingId(null)
  }

  return (
    <div className="flex-1 overflow-auto p-2">
      {conversations.length === 0 ? (
        <p className="px-3 py-2 text-xs text-muted-foreground">暂无会话</p>
      ) : (
        <ul className="space-y-1">
          {conversations.map((conversation) => (
            <li key={conversation.id} className="relative">
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
                  className={cn(
                    'flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors',
                    activeId === conversation.id
                      ? 'bg-accent text-accent-foreground'
                      : 'hover:bg-muted',
                  )}
                >
                  <span className="flex-1 truncate pr-2">{conversation.title}</span>
                  <div className="relative">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 focus:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation()
                        setMenuOpenId(menuOpenId === conversation.id ? null : conversation.id)
                      }}
                    >
                      <MoreHorizontal className="h-3 w-3" />
                    </Button>
                    {menuOpenId === conversation.id && (
                      <div className="absolute right-0 top-6 z-10 w-32 rounded-md border bg-background p-1 shadow-md">
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
                            onDelete(conversation.id)
                            setMenuOpenId(null)
                          }}
                          className="flex w-full items-center rounded-sm px-2 py-1 text-xs text-destructive hover:bg-accent"
                        >
                          <Trash2 className="mr-2 h-3 w-3" />
                          删除
                        </button>
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
    </div>
  )
}
