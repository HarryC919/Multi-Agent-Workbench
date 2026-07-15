import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface ThinkingBlockProps {
  thinking: string
  isStreaming: boolean
  bodyStarted: boolean
}

/**
 * Renders the model's chain-of-thought / reasoning content as a collapsible
 * block, visually distinct from the main reply body (smaller, muted text).
 *
 * Folding behavior (per the feature spec): the block auto-expands while
 * thinking tokens stream in, then auto-collapses once the main body starts
 * streaming (or when the stream ends). The user can still toggle it manually.
 */
export function ThinkingBlock({ thinking, isStreaming, bodyStarted }: ThinkingBlockProps) {
  const [open, setOpen] = useState(true)
  // While still streaming thought and the body hasn't started, keep it open so
  // the user watches the reasoning arrive. Once the body begins (or the stream
  // ends), auto-collapse. Subsequent user clicks still override this.
  const autoCollapse = bodyStarted || !isStreaming

  useEffect(() => {
    if (autoCollapse) setOpen(false)
    else setOpen(true)
  }, [autoCollapse])

  // Still streaming thought but no body yet: stay open.
  const streamingThought = isStreaming && !bodyStarted

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted-foreground/80 hover:text-muted-foreground"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span>思考过程</span>
        {streamingThought && (
          <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground/60" />
        )}
      </button>

      {open && (
        <div className="mt-1 max-h-60 overflow-y-auto border-l-2 border-muted pl-2 text-xs text-muted-foreground/70 whitespace-pre-wrap">
          {thinking}
        </div>
      )}
    </div>
  )
}
