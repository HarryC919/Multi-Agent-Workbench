import { useState } from 'react'
import { Database, Settings2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ModelManager } from './ModelManager'
import type { ModelConfig } from '@/types'

interface ChatHeaderProps {
  title: string
  models: ModelConfig[]
  selectedModel: string
  onModelChange: (modelId: string) => void
}

export function ChatHeader({ title, models = [], selectedModel, onModelChange }: ChatHeaderProps) {
  const [managerOpen, setManagerOpen] = useState(false)

  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <h2 className="min-w-0 truncate pr-3 text-sm font-medium" title={title}>{title}</h2>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled>
          <Database className="mr-1 h-4 w-4" />
          知识库
        </Button>
        <Button variant="outline" size="sm" disabled>
          <Sparkles className="mr-1 h-4 w-4" />
          Skills
        </Button>
        <Button variant="outline" size="sm" onClick={() => setManagerOpen(true)}>
          <Settings2 className="mr-1 h-4 w-4" />
          模型管理
        </Button>
        <select
          value={selectedModel}
          onChange={(e) => onModelChange(e.target.value)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs"
        >
          {models.map((model) => (
            <option key={model.modelId} value={model.modelId}>
              {model.name}
            </option>
          ))}
        </select>
      </div>
      <ModelManager open={managerOpen} onClose={() => setManagerOpen(false)} />
    </header>
  )
}
