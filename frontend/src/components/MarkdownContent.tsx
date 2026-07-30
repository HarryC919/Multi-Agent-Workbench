import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import remarkGfm from 'remark-gfm'

/**
 * Shared markdown renderer used for assistant body content (final answer) and
 * per-step narration outputs, so they render with identical styling.
 */
export function MarkdownContent({ children }: { children: string }) {
  return (
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
        {children}
      </ReactMarkdown>
    </div>
  )
}
