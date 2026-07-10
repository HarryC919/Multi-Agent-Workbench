import { Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface SidebarHeaderProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  onNewConversation: () => void
}

export function SidebarHeader({ searchQuery, onSearchChange, onNewConversation }: SidebarHeaderProps) {
  return (
    <div className="space-y-2 p-3">
      <Button onClick={onNewConversation} className="w-full" size="sm">
        <Plus className="mr-1 h-4 w-4" />
        新会话
      </Button>
      <div className="relative">
        <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="搜索会话..."
          className="h-8 pl-8 text-xs"
        />
      </div>
    </div>
  )
}
