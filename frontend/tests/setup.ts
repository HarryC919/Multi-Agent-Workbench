import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom doesn't implement scrollIntoView; the messages list uses it for
// auto-scroll-to-bottom behavior on new messages.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}

// polyfill ResizeObserver used by @tanstack/react-virtual measureElement.
class ResizeObserverMock {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

// Tear down React DOM between every test to avoid state leakage.
afterEach(() => {
  cleanup()
})