import React, { useEffect, useMemo, useState } from 'react';
import { Button, Collapse, Pagination, Tag } from 'antd';
import type { CollapseProps } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { TestSession } from '@/api/sessions';
import { formatDateTime, getApiDateTime } from '@/lib/datetime';
import { getSessionSceneLabel } from '@/lib/sessionScene';
import {
  getBatchSceneLabels,
  summarizeBatchStatus,
  type MultiSceneBatchGroup,
} from '@/lib/sessionHistory';
import './MultiSceneBatchHistory.css';

const TABLE_HEADERS = ['会话', '测试场景', '状态', '设备', '开始时间', '耗时', '操作'] as const;
const DEFAULT_PAGE_SIZE = 10;
const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

const sessionStatusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
  paused: { color: 'warning', text: '已暂停' },
  skipped: { color: 'default', text: '已跳过' },
  cancelled: { color: 'default', text: '已取消' },
};

interface MultiSceneBatchHistoryProps {
  batches: MultiSceneBatchGroup[];
  onAnalyze: (sessionId: number) => void;
}

function configNumber(session: TestSession, key: string, fallback = 0): number {
  const value = session.config?.[key];
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatDurationSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} 秒`;
  return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
}

function sessionDurationText(session: TestSession): string {
  const seconds = session.duration_seconds ??
    ((getApiDateTime(session.ended_at) ?? Date.now()) - (getApiDateTime(session.started_at) ?? Date.now())) / 1000;
  return formatDurationSeconds(seconds);
}

function batchDurationText(batch: MultiSceneBatchGroup): string {
  if (batch.endedAtMs && batch.startedAtMs) {
    return formatDurationSeconds((batch.endedAtMs - batch.startedAtMs) / 1000);
  }
  const totalSeconds = batch.sessions.reduce((sum, session) => {
    const seconds = session.duration_seconds ??
      ((getApiDateTime(session.ended_at) ?? Date.now()) - (getApiDateTime(session.started_at) ?? Date.now())) / 1000;
    return sum + Math.max(0, seconds);
  }, 0);
  return formatDurationSeconds(totalSeconds);
}

function batchDeviceLabel(batch: MultiSceneBatchGroup): string {
  return batch.sessions.find((session) => session.device_model)?.device_model || '-';
}

const StatusTag: React.FC<{ status: string }> = ({ status }) => {
  const config = sessionStatusMap[status] || { color: 'default', text: status };
  return <Tag color={config.color} className="batch-status-tag">{config.text}</Tag>;
};

function buildSceneGroups(batch: MultiSceneBatchGroup): Map<number, TestSession[]> {
  const sceneGroups = new Map<number, TestSession[]>();
  batch.sessions.forEach((session) => {
    const index = configNumber(session, 'scene_index');
    sceneGroups.set(index, [...(sceneGroups.get(index) || []), session]);
  });
  return sceneGroups;
}

function BatchHistoryTableHeader() {
  return (
    <div className="batch-history-shell__thead">
      <div className="batch-history-row batch-history-row--header">
        {TABLE_HEADERS.map((title) => (
          <div key={title} className="batch-history-row__cell batch-history-row__cell--header">
            {title}
          </div>
        ))}
        <div className="batch-history-row__expand-slot" aria-hidden />
      </div>
    </div>
  );
}

function BatchPanelLabel({ batch }: { batch: MultiSceneBatchGroup }) {
  const summary = summarizeBatchStatus(batch.sessions);

  return (
    <div className="batch-collapse-label">
      <div className="batch-history-row">
        <div className="batch-history-row__cell">
          <strong>编排 #{batch.batchId}</strong>
        </div>
        <div className="batch-history-row__cell">
          <Tag color="geekblue">{getBatchSceneLabels(batch.sessions)}</Tag>
        </div>
        <div className="batch-history-row__cell">
          <Tag color={summary.color}>{summary.text}</Tag>
        </div>
        <div className="batch-history-row__cell">{batchDeviceLabel(batch)}</div>
        <div className="batch-history-row__cell">
          {formatDateTime(batch.sessions[0]?.started_at ?? null)}
        </div>
        <div className="batch-history-row__cell">{batchDurationText(batch)}</div>
        <div className="batch-history-row__cell">
          <span className="batch-history-row__placeholder">-</span>
        </div>
      </div>
    </div>
  );
}

function SceneSessionRow({
  session,
  sceneLabel,
  sessionLabel,
  retryTag,
  onAnalyze,
}: {
  session: TestSession | undefined;
  sceneLabel: string;
  sessionLabel?: string;
  retryTag?: string;
  onAnalyze: (sessionId: number) => void;
}) {
  if (!session) {
    return (
      <div className="batch-history-row batch-history-row--child">
        <div className="batch-history-row__cell batch-history-row__placeholder">-</div>
        <div className="batch-history-row__cell">
          <Tag color="geekblue">{sceneLabel}</Tag>
        </div>
        <div className="batch-history-row__cell batch-history-row__placeholder">未执行</div>
        <div className="batch-history-row__cell batch-history-row__placeholder">-</div>
        <div className="batch-history-row__cell batch-history-row__placeholder">-</div>
        <div className="batch-history-row__cell batch-history-row__placeholder">-</div>
        <div className="batch-history-row__cell batch-history-row__placeholder">-</div>
        <div className="batch-history-row__expand-slot" aria-hidden />
      </div>
    );
  }

  return (
    <div className="batch-history-row batch-history-row--child">
      <div className="batch-history-row__cell">
        <strong>{sessionLabel ?? session.name}</strong>
      </div>
      <div className="batch-history-row__cell batch-history-row__cell--tags">
        <Tag color="geekblue">{sceneLabel}</Tag>
        {retryTag && <Tag color="orange">{retryTag}</Tag>}
      </div>
      <div className="batch-history-row__cell">
        <StatusTag status={session.status} />
      </div>
      <div className="batch-history-row__cell">{session.device_model || '-'}</div>
      <div className="batch-history-row__cell">{formatDateTime(session.started_at)}</div>
      <div className="batch-history-row__cell">{sessionDurationText(session)}</div>
      <div className="batch-history-row__cell">
        <Button
          type="text"
          icon={<EyeOutlined />}
          size="small"
          onClick={(event) => {
            event.stopPropagation();
            onAnalyze(session.id);
          }}
        >
          分析
        </Button>
      </div>
      <div className="batch-history-row__expand-slot" aria-hidden />
    </div>
  );
}

function BatchPanelContent({
  batch,
  onAnalyze,
}: {
  batch: MultiSceneBatchGroup;
  onAnalyze: (sessionId: number) => void;
}) {
  const sceneGroups = buildSceneGroups(batch);

  return (
    <div className="batch-history-item__scenes">
      {Array.from({ length: batch.sceneTotal }, (_, index) => {
        const attempts = sceneGroups.get(index) || [];
        const latest = attempts.at(-1);
        const sceneLabel = latest ? getSessionSceneLabel(latest) : `场景 ${index + 1}`;

        return (
          <React.Fragment key={index}>
            <SceneSessionRow
              session={latest}
              sceneLabel={sceneLabel}
              retryTag={attempts.length > 1 ? `${attempts.length} 次尝试` : undefined}
              onAnalyze={onAnalyze}
            />
            {attempts.slice(0, -1).map((attempt, attemptIndex) => (
              <div key={attempt.id} className="batch-history-row-wrap batch-history-row-wrap--retry">
                <SceneSessionRow
                  session={attempt}
                  sceneLabel={getSessionSceneLabel(attempt)}
                  sessionLabel={`尝试 ${attemptIndex + 1} · ${attempt.name}`}
                  onAnalyze={onAnalyze}
                />
              </div>
            ))}
          </React.Fragment>
        );
      })}
    </div>
  );
}

const MultiSceneBatchHistory: React.FC<MultiSceneBatchHistoryProps> = ({ batches, onAnalyze }) => {
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const totalPages = Math.max(1, Math.ceil(batches.length / pageSize));

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
      setActiveKeys([]);
    }
  }, [batches.length, currentPage, totalPages]);

  const pagedBatches = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return batches.slice(start, start + pageSize);
  }, [batches, currentPage, pageSize]);

  const items: CollapseProps['items'] = useMemo(
    () => pagedBatches.map((batch) => ({
      key: String(batch.batchId),
      label: <BatchPanelLabel batch={batch} />,
      children: <BatchPanelContent batch={batch} onAnalyze={onAnalyze} />,
    })),
    [pagedBatches, onAnalyze],
  );

  return (
    <div className="batch-history-shell">
      <div className="batch-history-shell__table">
        <BatchHistoryTableHeader />
        <Collapse
          className="batch-history-collapse"
          activeKey={activeKeys}
          onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys : [keys])}
          expandIconPosition="end"
          items={items}
        />
        <div className="batch-history-shell__pagination ant-table-pagination ant-table-pagination-right">
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={batches.length}
            showSizeChanger
            pageSizeOptions={PAGE_SIZE_OPTIONS}
            onChange={(page, size) => {
              setCurrentPage(page);
              setPageSize(size);
              setActiveKeys([]);
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default MultiSceneBatchHistory;
