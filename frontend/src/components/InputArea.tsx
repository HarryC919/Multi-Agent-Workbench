import { useCallback, useRef, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Paperclip, Send, Square, X, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { uploadFile } from '@/api/upload'
import { useToastStore } from '@/store/toastStore'
import { cn } from '@/lib/utils'
import type { ModelConfig, UploadedFile } from '@/types'

// Keep in sync with backend: app/services/file_parser.py
const SUPPORTED_EXTENSIONS = new Set([
  '.txt', '.md', '.markdown',
  '.json', '.yaml', '.yml', '.xml', '.html', '.htm', '.css', '.scss', '.less',
  '.js', '.jsx', '.ts', '.tsx', '.py', '.pyw', '.java', '.c', '.cpp', '.cc',
  '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.sql', '.sh',
  '.bash', '.zsh', '.ps1', '.bat', '.cmd', '.csv', '.log', '.ini', '.cfg',
  '.toml',
  '.pdf', '.docx',
])

function isSupportedFile(file: File): boolean {
  const name = file.name.toLowerCase()
  for (const ext of SUPPORTED_EXTENSIONS) {
    if (name.endsWith(ext)) return true
  }
  return false
}

interface InputAreaProps {
  models: ModelConfig[]
  selectedModel: string
  effort: number
  thinkingEnabled: boolean
  attachedFiles: UploadedFile[]
  isStreaming: boolean
  onModelChange: (modelId: string) => void
  onEffortChange: (value: number) => void
  onThinkingToggle: (value: boolean) => void
  onAttachFile: (file: UploadedFile) => void
  onRemoveFile: (fileId: string) => void
  onSend: (content: string) => void
  onAbort?: () => void
}

export function InputArea({
  models = [],
  selectedModel,
  effort,
  thinkingEnabled,
  attachedFiles,
  isStreaming,
  onModelChange,
  onEffortChange,
  onThinkingToggle,
  onAttachFile,
  onRemoveFile,
  onSend,
  onAbort,
}: InputAreaProps) {
  const [text, setText] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setIsUploading(true)
      try {
        for (const file of acceptedFiles) {
          const uploaded = await uploadFile(file)
          onAttachFile({
            id: uploaded.fileId,
            name: uploaded.name,
            textContent: uploaded.textContent,
          })
        }
      } catch (error) {
        useToastStore
          .getState()
          .addToast(error instanceof Error ? error.message : 'Upload failed', 'error')
      } finally {
        setIsUploading(false)
      }
    },
    [onAttachFile],
  )

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    noClick: true,
    noKeyboard: true,
    validator: (file) => {
      return isSupportedFile(file) ? null : { code: 'file-invalid-type', message: '不支持的文件类型' }
    },
  })

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setText('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      {...getRootProps()}
      className={cn(
        'border-t bg-background p-4',
        isDragActive && 'bg-accent/50',
      )}
    >
      <input {...getInputProps()} />

      {attachedFiles.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachedFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs"
            >
              <Paperclip className="h-3 w-3" />
              <span className="max-w-[150px] truncate">{file.name}</span>
              <button
                onClick={() => onRemoveFile(file.id)}
                className="ml-1 rounded-full hover:bg-muted-foreground/20"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
        rows={3}
        className="w-full resize-none rounded-md border border-input bg-transparent p-3 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />

      <div className="mt-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={open}
            disabled={isUploading}
          >
            <Paperclip className="mr-1 h-4 w-4" />
            {isUploading ? '上传中...' : '附件'}
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

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">思考强度</span>
            <Slider
              value={effort}
              min={0}
              max={1}
              step={0.1}
              onChange={onEffortChange}
              className="w-24"
            />
            <span className="w-8 text-xs tabular-nums">{effort.toFixed(1)}</span>
          </div>

          <button
            type="button"
            onClick={() => onThinkingToggle(!thinkingEnabled)}
            className={cn(
              'flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-medium transition-colors',
              thinkingEnabled
                ? 'border-blue-500 bg-background text-blue-600 dark:border-blue-400 dark:bg-background dark:text-blue-400'
                : 'border-input bg-background text-muted-foreground hover:border-blue-400 hover:text-blue-500',
            )}
            title={thinkingEnabled ? '关闭深度思考' : '开启深度思考'}
          >
            <Brain className={cn('h-3.5 w-3.5', thinkingEnabled && 'fill-blue-100 dark:fill-blue-100')} />
            深度思考
          </button>
        </div>

        {isStreaming ? (
          <Button variant="destructive" onClick={onAbort} size="sm">
            <Square className="mr-1 h-4 w-4" />
            停止
          </Button>
        ) : (
          <Button onClick={handleSend} disabled={!text.trim()} size="sm">
            <Send className="mr-1 h-4 w-4" />
            发送
          </Button>
        )}
      </div>
    </div>
  )
}
