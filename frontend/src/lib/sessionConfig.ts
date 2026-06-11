export function getConfigString(
  config: Record<string, unknown> | null | undefined,
  keys: string[],
  fallback = '-',
): string {
  for (const key of keys) {
    const value = config?.[key];
    if (value !== undefined && value !== null && value !== '') {
      return String(value);
    }
  }
  return fallback;
}

export function getConfigNumber(
  config: Record<string, unknown> | null | undefined,
  keys: string[],
  fallback?: number,
): number | undefined {
  for (const key of keys) {
    const value = config?.[key];
    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return fallback;
}
