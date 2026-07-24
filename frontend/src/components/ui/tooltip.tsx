import * as React from 'react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  content: string
  children: React.ReactNode
  className?: string
}

// Instant tooltip: shows immediately on hover, unlike the native `title`
// attribute which browsers delay. The wrapper span keeps hover working even
// when the child is a disabled button.
export function Tooltip({ content, children, className }: TooltipProps) {
  return (
    <span className={cn('group relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded-md border bg-[hsl(var(--color-popover))] px-2 py-1 text-xs text-[hsl(var(--color-popover-foreground))] shadow-md group-hover:block"
      >
        {content}
      </span>
    </span>
  )
}
