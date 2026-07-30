import { useState } from 'react'
import { Database, Settings2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ModelManager } from './ModelManager'
import { KnowledgeBaseManager } from './KnowledgeBaseManager'
import { SkillsManager } from './SkillsManager'
import { useWorkspaceStore } from '@/store/workspaceStore'
import type { ModelConfig } from '@/types'

interface ChatHeaderProps {
  title: string
  models: ModelConfig[]
  selectedModel: string
  onModelChange: (modelId: string) => void
}

export function ChatHeader({ title, models = [], selectedModel, onModelChange }: ChatHeaderProps) {
  const [managerOpen, setManagerOpen] = useState(false)
  const [kbManagerOpen, setKbManagerOpen] = useState(false)
  const [skillsManagerOpen, setSkillsManagerOpen] = useState(false)
  // Read KB state directly from the store so the dropdown stays in sync with
  // selection changes made elsewhere (and avoids prop-drilling through
  // WorkspaceLayout).
  const knowledgeBases = useWorkspaceStore((s) => s.knowledgeBases)
  const selectedKbId = useWorkspaceStore((s) => s.selectedKbId)
  const setSelectedKbId = useWorkspaceStore((s) => s.setSelectedKbId)

  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <h2 className="min-w-0 truncate pr-3 text-sm font-medium" title={title}>{title}</h2>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => setKbManagerOpen(true)}>
          <Database className="mr-1 h-4 w-4" />
          知识库
        </Button>
        <select
          value={selectedKbId}
          onChange={(e) => setSelectedKbId(e.target.value)}
          disabled={knowledgeBases.length === 0}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs disabled:opacity-50"
          title={knowledgeBases.length === 0 ? '请先在知识库管理中创建' : '选择对话使用的知识库'}
        >
          <option value="">--无--</option>
          {knowledgeBases.map((kb) => (
            <option key={kb.id} value={kb.id}>
              {kb.name}
            </option>
          ))}
        </select>
        <Button variant="outline" size="sm" onClick={() => setSkillsManagerOpen(true)}>
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
      <KnowledgeBaseManager open={kbManagerOpen} onClose={() => setKbManagerOpen(false)} />
      <SkillsManager open={skillsManagerOpen} onClose={() => setSkillsManagerOpen(false)} />
    </header>
  )
}
