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
    narration: null,
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
    expect(screen.getByText(/第 1 步/)).toBeInTheDocument()
    expect(screen.getByText(/第 2 步/)).toBeInTheDocument()
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

  it('toggles step content visibility on header click when collapsed', () => {
    const steps = [step({ step: 1, finish: 'final', text: 'Final Answer: ok' })]
    // bodyStarted && !isStreaming -> auto-collapsed (content hidden, header visible).
    render(<AgentTrace steps={steps} isStreaming={false} bodyStarted />)
    // Header is always visible.
    const header = screen.getByText(/第 1 步/).closest('button')!
    // Content hidden when collapsed.
    expect(screen.queryByText('Final Answer: ok')).not.toBeInTheDocument()
    fireEvent.click(header)
    // Content visible after expanding.
    expect(screen.getByText('Final Answer: ok')).toBeInTheDocument()
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
    expect(screen.getByText('chunk body text')).toBeInTheDocument()
  })

  it('renders the narration as body text below the step card', () => {
    const steps = [
      step({ step: 1, finish: 'tool', text: 'Thought A', narration: '我先搜索一下' }),
    ]
    render(<AgentTrace steps={steps} {...OPEN} />)
    expect(screen.getByText('我先搜索一下')).toBeInTheDocument()
  })
})
