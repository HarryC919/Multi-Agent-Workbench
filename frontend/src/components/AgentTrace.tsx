import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { AgentStep } from '@/types'

interface AgentTraceProps {
  steps: AgentStep[]
  isStreaming: boolean
  bodyStarted: boolean
}

const FINISH_LABEL: Record<string, string> = {
  final: '完成',
  tool: '工具',
  empty: '空',
  max_steps: '上限',
  error: '错误',
}

/**
 * Phase 2b-ii: renders the agent's ReAct transcript as a stack of per-step
 * cards (thought / action / observation / retrieved chunks), replacing the
 * old flat `ThinkingBlock` rendering for agent messages.
 *
 * Folding behavior mirrors `ThinkingBlock`: auto-expanded while streaming and
 * no body has started, auto-collapsed once the final answer body begins (or
 * the stream ends); the user can still toggle manually.
 *
 * Tailwind v4 pitfall: `@theme` defines bare HSL colors, which makes `bg-*`
 * utilities render transparent (see ui/modal.tsx). Backgrounds for the
 * collapse header and badges use inline `rgba()` styles instead.
 */
export function AgentTrace({ steps, isStreaming, bodyStarted }: AgentTraceProps) {
  const [open, setOpen] = useState(true)
  const autoCollapse = bodyStarted || !isStreaming

  useEffect(() => {
    if (autoCollapse) setOpen(false)
    else setOpen(true)
  }, [autoCollapse])

  const streamingTrace = isStreaming && !bodyStarted

  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  useEffect(() => {
    const el = scrollRef.current
    if (!el || !open || !streamingTrace) return
    if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [steps, open, streamingTrace])

  useEffect(() => {
    const el = scrollRef.current
    if (el && open) {
      el.scrollTop = el.scrollHeight
    }
  }, [open])

  if (!steps || steps.length === 0) return null

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted-foreground/80 hover:text-muted-foreground"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span>Agent 推理过程</span>
        {streamingTrace && (
          <span className="ml-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground/60" />
        )}
      </button>

      {open && (
        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget
            const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
            stickToBottom.current = distanceFromBottom < 20
          }}
          className="mt-1 max-h-80 space-y-2 overflow-y-auto border-l-2 border-muted pl-2"
        >
          {steps.map((step) => (
            <StepCard key={step.step} step={step} />
          ))}
        </div>
      )}
    </div>
  )
}

interface StepCardProps {
  step: AgentStep
}

function StepCard({ step }: StepCardProps) {
  // A step is "in flight" while streaming — no finish yet. We still render
  // whatever fragments have arrived so the user watches reasoning accumulate.
  const hasRetrieved = !!step.retrieved && step.retrieved.length > 0

  return (
    <div className="rounded-md border border-border/60 p-2">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-xs font-medium">第 {step.step} 步</span>
        {step.finish && FINISH_LABEL[step.finish] && (
          <span
            className="rounded px-1.5 py-0.5 text-[10px]"
            style={{ backgroundColor: 'rgba(100, 116, 139, 0.15)' }}
          >
            {FINISH_LABEL[step.finish]}
          </span>
        )}
      </div>

      <div className="space-y-1.5 text-xs text-muted-foreground/80">
        {step.thinking && (
          <div className="whitespace-pre-wrap">{step.thinking}</div>
        )}

        {step.text && <div className="whitespace-pre-wrap">{step.text}</div>}

        {step.action && (
          <div className="whitespace-pre-wrap">
            <span className="font-medium">Action:</span> {step.action.name}({step.action.input})
          </div>
        )}

        {step.observation && !hasRetrieved && (
          <div className="whitespace-pre-wrap">
            <span className="font-medium">Observation:</span> {step.observation.content}
          </div>
        )}

        {/* When retrieved chunks exist they're rendered as structured cards
            below; keep the raw observation text available but collapsed so it
            isn't shown twice. */}
        {step.observation && hasRetrieved && (
          <details className="text-[11px] text-muted-foreground/60">
            <summary className="cursor-pointer">原始观察文本</summary>
            <div className="mt-1 whitespace-pre-wrap">{step.observation.content}</div>
          </details>
        )}

        {hasRetrieved &&
          step.retrieved!.map((chunk, idx) => (
            <details
              key={`${chunk.docId}-${idx}`}
              className="rounded border border-border/50 p-1.5 text-[11px]"
              style={{ backgroundColor: 'rgba(100, 116, 139, 0.08)' }}
            >
              <summary className="cursor-pointer font-medium">
                [来源: {chunk.filename}
                {chunk.heading ? ` # ${chunk.heading}` : ''} | score={chunk.score.toFixed(2)}]
              </summary>
              <div className="mt-1 whitespace-pre-wrap text-muted-foreground/80">
                {chunk.text}
              </div>
            </details>
          ))}
      </div>
    </div>
  )
}
