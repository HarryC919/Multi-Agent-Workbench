import { useEffect, useRef, useState } from 'react'
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
 *
 * Auto-scroll: while streaming reasoning, the inner container keeps its
 * bottom pinned to the latest token so the user can follow along. If the
 * user scrolls up to read earlier reasoning, auto-scroll is paused until
 * they jump back to the bottom (sticky-bottom), matching conventional
 * chat UX so the reader isn't fought while skimming.
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

  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  // Pin to bottom whenever new thinking arrives (and the user is still
  // pinned to the bottom). Dependency on `thinking` keeps this cheap and
  // runs only when content actually grew.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !open || !streamingThought) return
    if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [thinking, open, streamingThought])

  // When reopening while idle, also jump to bottom so the latest content is visible.
  useEffect(() => {
    const el = scrollRef.current
    if (el && open) {
      el.scrollTop = el.scrollHeight
    }
  }, [open])

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
        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget
            // Re-enable auto-scroll when the user is within ~20px of the bottom
            // (avoids flicker from sub-pixel scrollbar positions). Disable it
            // as soon as they scroll up to reread earlier reasoning.
            const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
            stickToBottom.current = distanceFromBottom < 20
          }}
          className="mt-1 max-h-60 overflow-y-auto border-l-2 border-muted pl-2 text-xs text-muted-foreground/70 whitespace-pre-wrap"
        >
          {thinking}
        </div>
      )}
    </div>
  )
}
