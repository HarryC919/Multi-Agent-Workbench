import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { AgentStep } from '@/types'
import { MarkdownContent } from './MarkdownContent'

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
 * Phase 3: renders the agent's ReAct transcript as an **interleaved** sequence
 * of per-step units. Each step renders:
 *   1. A collapsible reasoning card (Thought / Action / Observation) - the
 *      `说明:` line is stripped from the trace text so it isn't duplicated.
 *   2. The step's narration output (说明:) as **body text** rendered directly
 *      in the message flow - same styling as the final answer - NOT inside the
 *      collapsible box. This keeps every step's output always visible even when
 *      the reasoning card is collapsed.
 *
 * The final answer is rendered separately by MessageItem (lives in
 * `message.content`), so it naturally follows the last step's narration.
 *
 * Tailwind v4 pitfall: `@theme` defines bare HSL colors, which makes `bg-*`
 * utilities render transparent (see ui/modal.tsx). Badge backgrounds use inline
 * `rgba()` styles instead.
 */
export function AgentTrace({ steps, isStreaming, bodyStarted }: AgentTraceProps) {
  const streamingTrace = isStreaming && !bodyStarted

  if (!steps || steps.length === 0) return null

  return (
    <div className="mb-2 space-y-2">
      {steps.map((step) => (
        <StepUnit
          key={step.step}
          step={step}
          streamingTrace={streamingTrace}
        />
      ))}
    </div>
  )
}

interface StepUnitProps {
  step: AgentStep
  streamingTrace: boolean
}

/** Remove `说明:` lines from the trace text so they only appear as the
 *  narration body output below the card, never duplicated inside it. */
function stripNarration(text: string): string {
  return text
    .split('\n')
    .filter((line) => !/^\s*说明\s*[:：]/.test(line))
    .join('\n')
    .trim()
}

function StepUnit({ step, streamingTrace }: StepUnitProps) {
  // The in-flight step (no finish yet) stays expanded while streaming;
  // completed steps collapse once the final answer starts.
  const inFlight = streamingTrace && !step.finish
  const [open, setOpen] = useState(true)

  useEffect(() => {
    if (step.finish && !streamingTrace) {
      setOpen(false)
    } else if (inFlight) {
      setOpen(true)
    }
  }, [step.finish, streamingTrace, inFlight])

  const hasRetrieved = !!step.retrieved && step.retrieved.length > 0
  const traceText = step.text ? stripNarration(step.text) : ''
  // Render the collapsible card when there's any reasoning content (including
  // retrieved chunks). The header always shows so the step number + finish
  // badge are visible even if the details are collapsed.
  const hasDetails = !!(step.thinking || traceText || step.action || step.observation || step.retrieved)

  return (
    <div className="space-y-1.5">
      <div className="rounded-md border border-border/60 p-2">
        <div className="mb-1 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-1 text-xs text-muted-foreground/80 hover:text-muted-foreground"
          >
            {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <span>第 {step.step} 步 推理</span>
          </button>
          {step.finish && FINISH_LABEL[step.finish] && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px]"
              style={{ backgroundColor: 'rgba(100, 116, 139, 0.15)' }}
            >
              {FINISH_LABEL[step.finish]}
            </span>
          )}
          </div>

          {open && hasDetails && (
            <div className="space-y-1.5 text-xs text-muted-foreground/80">
              {step.thinking && (
                <div className="whitespace-pre-wrap">{step.thinking}</div>
              )}

              {traceText && <div className="whitespace-pre-wrap">{traceText}</div>}

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
          )}
      </div>

      {/* Phase 3: the per-step narration output (说明:), rendered as body text
          in the message flow - same styling as the final answer - NOT inside
          the collapsible card. Always visible even when the trace is collapsed. */}
      {step.narration && <MarkdownContent>{step.narration}</MarkdownContent>}
    </div>
  )
}
