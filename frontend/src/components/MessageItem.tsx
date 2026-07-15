import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { ThinkingBlock } from './ThinkingBlock'
import type { Message } from '@/types'

interface MessageItemProps {
  message: Message
}

export function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-3 text-sm',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <>
            {message.thinking && (
              <ThinkingBlock
                thinking={message.thinking}
                isStreaming={message.status === 'streaming'}
                bodyStarted={!!message.content}
              />
            )}
            <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              disallowedElements={['script', 'iframe', 'form']}
              unwrapDisallowed
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const language = match ? match[1] : ''
                  const code = String(children).replace(/\n$/, '')

                  if (language) {
                    return (
                      <SyntaxHighlighter
                        language={language}
                        PreTag="div"
                        className="rounded-md text-xs"
                        {...(props as Record<string, unknown>)}
                      >
                        {code}
                      </SyntaxHighlighter>
                    )
                  }

                  return (
                    <code className="rounded bg-secondary px-1 py-0.5 text-xs" {...props}>
                      {children}
                    </code>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            </div>
          </>
        )}
        {message.status === 'streaming' && (
          <span className="ml-1 inline-block h-2 w-2 animate-pulse rounded-full bg-current opacity-50" />
        )}
        {message.status === 'error' && (
          <p className="mt-1 text-xs text-destructive">发送失败</p>
        )}
      </div>
    </div>
  )
}
