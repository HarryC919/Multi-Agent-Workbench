export function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export function snakeToCamel<T>(obj: unknown): T {
  if (obj === null || typeof obj !== 'object') {
    return obj as T
  }

  if (Array.isArray(obj)) {
    return obj.map((item) => snakeToCamel(item)) as T
  }

  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[toCamelCase(key)] = snakeToCamel(value)
  }
  return result as T
}
