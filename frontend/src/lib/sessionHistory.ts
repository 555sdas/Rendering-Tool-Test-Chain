import type { TestSession } from '@/api/sessions';
import { getApiDateTime } from '@/lib/datetime';

export interface MultiSceneBatchGroup {
  batchId: number;
  sessions: TestSession[];
  sceneTotal: number;
  startedAtMs: number;
  endedAtMs: number | null;
}

function configNumber(config: Record<string, unknown> | null | undefined, key: string, fallback = 0): number {
  const value = config?.[key];
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function isMultiSceneSession(session: TestSession): boolean {
  const config = session.config || {};
  return config.run_mode === 'multi_scene' && configNumber(config, 'batch_id', 0) > 0;
}

function sortBatchSessions(sessions: TestSession[]): TestSession[] {
  return [...sessions].sort((left, right) => {
    const leftIndex = configNumber(left.config, 'scene_index', 0);
    const rightIndex = configNumber(right.config, 'scene_index', 0);
    if (leftIndex !== rightIndex) return leftIndex - rightIndex;
    const leftStarted = getApiDateTime(left.started_at) ?? 0;
    const rightStarted = getApiDateTime(right.started_at) ?? 0;
    if (leftStarted !== rightStarted) return leftStarted - rightStarted;
    return left.id - right.id;
  });
}

export function groupSessionsForHistory(sessions: TestSession[]): {
  batches: MultiSceneBatchGroup[];
  singles: TestSession[];
} {
  const singles: TestSession[] = [];
  const batchMap = new Map<number, TestSession[]>();

  for (const session of sessions) {
    if (isMultiSceneSession(session)) {
      const batchId = configNumber(session.config, 'batch_id', 0);
      const existing = batchMap.get(batchId) || [];
      existing.push(session);
      batchMap.set(batchId, existing);
      continue;
    }
    singles.push(session);
  }

  const batches = Array.from(batchMap.entries()).map(([batchId, batchSessions]) => {
    const sorted = sortBatchSessions(batchSessions);
    const sceneTotal = Math.max(
      configNumber(sorted[0]?.config, 'scene_total', 0),
      ...sorted.map((item) => configNumber(item.config, 'scene_index', 0) + 1),
    );
    const startedAtMs = Math.min(
      ...sorted.map((item) => getApiDateTime(item.started_at) ?? Number.MAX_SAFE_INTEGER),
    );
    const endedAtMs = Math.max(
      ...sorted.map((item) => getApiDateTime(item.ended_at) ?? 0),
    );
    return {
      batchId,
      sessions: sorted,
      sceneTotal: sceneTotal || sorted.length,
      startedAtMs: Number.isFinite(startedAtMs) ? startedAtMs : 0,
      endedAtMs: endedAtMs > 0 ? endedAtMs : null,
    };
  });

  batches.sort((left, right) => right.startedAtMs - left.startedAtMs);
  singles.sort((left, right) => (getApiDateTime(right.started_at) ?? 0) - (getApiDateTime(left.started_at) ?? 0));

  return { batches, singles };
}

export function summarizeBatchStatus(sessions: TestSession[]): {
  color: string;
  text: string;
} {
  if (sessions.length === 0) {
    return { color: 'default', text: '未知' };
  }

  const statuses = new Set(sessions.map((item) => String(item.status)));
  if (statuses.has('running') || statuses.has('pending')) {
    return { color: 'processing', text: '进行中' };
  }
  if (statuses.has('failed')) {
    return { color: 'error', text: '含失败场景' };
  }
  if ([...statuses].every((status) => status === 'completed')) {
    return { color: 'success', text: '全部完成' };
  }
  if ([...statuses].every((status) => status === 'cancelled')) {
    return { color: 'default', text: '已取消' };
  }
  if (statuses.has('completed') && (statuses.has('cancelled') || statuses.has('skipped'))) {
    return { color: 'gold', text: '部分完成' };
  }
  return { color: 'warning', text: '混合状态' };
}

export function getBatchSceneLabels(sessions: TestSession[]): string {
  const seen = new Set<number>();
  const labels: string[] = [];
  for (const session of sessions) {
    const index = configNumber(session.config, 'scene_index', -1);
    if (index < 0 || seen.has(index)) continue;
    seen.add(index);
    const label =
      (session.config?.scene_display_name as string | undefined) ||
      session.scene_display_name ||
      `场景 ${index + 1}`;
    labels.push(label);
  }
  return labels.join(' → ') || '多场景编排';
}
