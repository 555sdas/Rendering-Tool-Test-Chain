const TIMEZONE_SUFFIX_RE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

function normalizeApiDate(value: string): string {
  const trimmed = value.trim().replace(/(\.\d{3})\d+/, '$1');
  if (TIMEZONE_SUFFIX_RE.test(trimmed)) {
    return trimmed;
  }
  return `${trimmed}Z`;
}

export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(normalizeApiDate(value));
  return Number.isNaN(date.getTime()) ? null : date;
}

export function getApiDateTime(value: string | null | undefined): number | null {
  return parseApiDate(value)?.getTime() ?? null;
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseApiDate(value);
  return date ? date.toLocaleString('zh-CN') : '-';
}

export function formatDate(value: string | null | undefined): string {
  const date = parseApiDate(value);
  return date ? date.toLocaleDateString('zh-CN') : '-';
}
