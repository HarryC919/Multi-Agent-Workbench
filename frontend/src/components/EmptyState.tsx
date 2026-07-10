import { MessageSquarePlus } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface EmptyStateProps {
  onNewConversation: () => void
}

export function EmptyState({ onNewConversation }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="rounded-full bg-muted p-4">
        <MessageSquarePlus className="h-8 w-8 text-muted-foreground" />
      </div>
      <div>
        <h3 className="text-lg font-medium">开始新对话</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          选择模型，输入消息，或上传文本文件作为上下文
        </p>
      </div>
      <Button onClick={onNewConversation}>新建会话</Button>
    </div>
  )
}
