import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AgentTrace } from '@/components/AgentTrace'
import type { AgentStep } from '@/types'

function step(overrides: Partial<AgentStep> = {}): AgentStep {
  return {
    step: 1,
    thinking: '',
    text: '',
    action: null,
    observation: null,
    retrieved: null,
    finish: null,
    ...overrides,
  }
}

// `isStreaming && !bodyStarted` keeps the trace auto-expanded (matches the
// live in-flight state), so the step cards are in the DOM for assertions.
const OPEN = { isStreaming: true, bodyStarted: false }

describe('AgentTrace', () => {
  it('renders one card per step', () => {
    const steps = [
      step({ step: 1, finish: 'tool', text: 'Thought A' }),
      step({ step: 2, finish: 'final', text: 'Final Answer: done' }),
    ]
    render(<AgentTrace steps={steps} {...OPEN} />)
    expect(screen.getByText('第 1 步')).toBeInTheDocument()
    expect(screen.getByText('第 2 步')).toBeInTheDocument()
  })

  it('renders the finish badge from the finish value', () => {
    const steps = [step({ step: 1, finish: 'final' })]
    render(<AgentTrace steps={steps} {...OPEN} />)
    expect(screen.getByText('完成')).toBeInTheDocument()
  })

  it('collapses the raw observation text into a details summary when retrieved chunks are present', () => {
    const steps = [
      step({
        step: 1,
        finish: 'tool',
        action: { name: 'retrieve_notes', input: 'q' },
        observation: { name: 'retrieve_notes', content: 'Observation: raw snippet' },
        retrieved: [
          {
            docId: 'd1',
            filename: 'notes.md',
            heading: '安装',
            score: 0.87,
            text: '用 uv 安装。',
          },
        ],
      }),
    ]
    render(<AgentTrace steps={steps} {...OPEN} />)
    // The raw observation text is tucked inside a collapsed <details> whose
    // summary is "原始观察文本" — the visible surface is the retrieved card.
    expect(screen.getByText('原始观察文本')).toBeInTheDocument()
    expect(screen.getByText(/来源: notes.md/)).toBeInTheDocument()
    expect(screen.getByText(/score=0.87/)).toBeInTheDocument()
  })

  it('shows the observation text when retrieved is null', () => {
    const steps = [
      step({
        step: 1,
        finish: 'tool',
        observation: { name: 'echo', content: 'Observation: hello' },
      }),
    ]
    render(<AgentTrace steps={steps} {...OPEN} />)
    expect(screen.getByText('Observation: hello')).toBeInTheDocument()
  })

  it('expands on header click when collapsed', () => {
    const steps = [step({ step: 1, finish: 'final', text: 'Final Answer: ok' })]
    // bodyStarted && !isStreaming → auto-collapsed.
    render(<AgentTrace steps={steps} isStreaming={false} bodyStarted />)
    const header = screen.getByText('Agent 推理过程').closest('button')!
    // Collapsed initially: card not visible.
    expect(screen.queryByText('第 1 步')).not.toBeInTheDocument()
    fireEvent.click(header)
    expect(screen.getByText('第 1 步')).toBeInTheDocument()
  })

  it('renders nothing for an empty steps array', () => {
    const { container } = render(<AgentTrace steps={[]} {...OPEN} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders chunk text inside the retrieved card details', () => {
    const steps = [
      step({
        step: 1,
        finish: 'tool',
        retrieved: [
          {
            docId: 'd1',
            filename: 'notes.md',
            heading: null,
            score: 0.5,
            text: 'chunk body text',
          },
        ],
      }),
    ]
    render(<AgentTrace steps={steps} {...OPEN} />)
    // Chunk text is always rendered (inside <details>, not summary), so it
    // should be in the document regardless of open/closed summary state.
    expect(screen.getByText('chunk body text')).toBeInTheDocument()
  })
})
