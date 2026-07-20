import { useState } from 'react'
import { PanelLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConversationList } from './ConversationList'
import { SidebarHeader } from './SidebarHeader'
import type { Conversation } from '@/types'

interface SidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewConversation: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}

export function Sidebar({
  conversations = [],
  activeId,
  onSelect,
  onNewConversation,
  onRename,
  onDelete,
}: SidebarProps) {
  const [width, setWidth] = useState(260)
  const [searchQuery, setSearchQuery] = useState('')
  const [isCollapsed, setIsCollapsed] = useState(false)

  const conversationList = conversations ?? []
  const filteredConversations = conversationList.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase()),
  )

  if (isCollapsed) {
    return (
      <div className="flex h-full w-12 flex-col items-center border-r py-2">
        <Button variant="ghost" size="icon" onClick={() => setIsCollapsed(false)}>
          <PanelLeft className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex h-full shrink-0 overflow-hidden" style={{ width }}>
      <div className="flex min-w-0 flex-1 flex-col border-r bg-background">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-semibold">AI Workbench</span>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setIsCollapsed(true)}>
            <PanelLeft className="h-4 w-4" />
          </Button>
        </div>
        <SidebarHeader
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onNewConversation={onNewConversation}
        />
        <ConversationList
          conversations={filteredConversations}
          activeId={activeId}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
        />
      </div>
      <div
        className="w-1 cursor-col-resize hover:bg-border"
        onMouseDown={(e) => {
          const startX = e.clientX
          const startWidth = width

          const handleMouseMove = (moveEvent: MouseEvent) => {
            const newWidth = Math.min(Math.max(startWidth + moveEvent.clientX - startX, 200), 400)
            setWidth(newWidth)
          }

          const handleMouseUp = () => {
            document.removeEventListener('mousemove', handleMouseMove)
            document.removeEventListener('mouseup', handleMouseUp)
          }

          document.addEventListener('mousemove', handleMouseMove)
          document.addEventListener('mouseup', handleMouseUp)
        }}
      />
    </div>
  )
}
