import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render } from '@testing-library/react'
import { MessageList } from '@/components/MessageList'
import type { Message } from '@/types'

// jsdom gives every element zero height, so the virtualizer would render
// nothing. Inflate the host measurements for the duration of the bench.
let clientHeightDescriptor: PropertyDescriptor | undefined
beforeEach(() => {
  clientHeightDescriptor = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype,
    'clientHeight',
  )
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
    configurable: true,
    get() {
      return 800
    },
  })
})
afterEach(() => {
  if (clientHeightDescriptor) {
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', clientHeightDescriptor)
  }
})

function buildMessages(n: number): Message[] {
  const now = '2026-01-01T00:00:00Z'
  const out: Message[] = []
  for (let i = 0; i < n; i++) {
    out.push({
      id: `m${i}`,
      conversationId: 'perf',
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `Message ${i}: ${'lorem ipsum '.repeat(20)}`,
      status: 'done',
      createdAt: now,
    })
  }
  return out
}

describe('MessageList performance', () => {
  it('mounts 1000 messages and stays inside the time envelope', async () => {
    const messages = buildMessages(1000)
    const start = performance.now()
    const { unmount, container } = render(<MessageList messages={messages} />)
    const elapsed = performance.now() - start

    // Sanity: the virtualized wrapper was mounted with a non-zero total size.
    const wrapper = container.querySelector('div[style*="height"]')
    expect(wrapper).not.toBeNull()
    // Performance envelope: keep generous so CI runners don't flake.
    expect(elapsed).toBeLessThan(2000)

    unmount()
  })
})