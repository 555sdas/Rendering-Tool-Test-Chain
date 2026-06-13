import React, { useMemo, useState } from 'react';
import { Button, Empty, Table, Tabs, Tag } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { TestSession } from '@/api/sessions';
import { formatDateTime, getApiDateTime } from '@/lib/datetime';
import { getSessionSceneLabel } from '@/lib/sessionScene';
import { groupSessionsForHistory, type HistoryViewMode } from '@/lib/sessionHistory';
import MultiSceneBatchHistory from './MultiSceneBatchHistory';

const sessionStatusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
  paused: { color: 'warning', text: '已暂停' },
  skipped: { color: 'default', text: '已跳过' },
  cancelled: { color: 'default', text: '已取消' },
};

interface SessionHistoryListProps {
  sessions: TestSession[];
  historyView?: HistoryViewMode;
  onHistoryViewChange?: (view: HistoryViewMode) => void;
  onAnalyze: (sessionId: number, context?: { historyView: HistoryViewMode }) => void;
}

function formatDurationSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} 秒`;
  return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
}

function durationText(session: TestSession): string {
  const seconds = session.duration_seconds ??
    ((getApiDateTime(session.ended_at) ?? Date.now()) - (getApiDateTime(session.started_at) ?? Date.now())) / 1000;
  return formatDurationSeconds(seconds);
}

const StatusTag: React.FC<{ status: string }> = ({ status }) => {
  const config = sessionStatusMap[status] || { color: 'default', text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

const SessionHistoryList: React.FC<SessionHistoryListProps> = ({
  sessions,
  historyView: controlledHistoryView,
  onHistoryViewChange,
  onAnalyze,
}) => {
  const { batches, singles } = useMemo(() => groupSessionsForHistory(sessions), [sessions]);
  const [internalHistoryView, setInternalHistoryView] = useState<HistoryViewMode>(() =>
    singles.length === 0 && batches.length > 0 ? 'multi' : 'single',
  );
  const activeHistoryView = controlledHistoryView ?? internalHistoryView;

  const handleHistoryViewChange = (view: HistoryViewMode) => {
    if (onHistoryViewChange) {
      onHistoryViewChange(view);
      return;
    }
    setInternalHistoryView(view);
  };

  const singleSceneColumns = useMemo(
    () => [
      { title: '会话', dataIndex: 'name', key: 'name', render: (text: string) => <strong>{text}</strong> },
      {
        title: '测试场景',
        key: 'scene_display_name',
        render: (_: unknown, record: TestSession) => <Tag color="geekblue">{getSessionSceneLabel(record)}</Tag>,
      },
      { title: '状态', dataIndex: 'status', key: 'status', render: (status: string) => <StatusTag status={status} /> },
      { title: '设备', dataIndex: 'device_model', key: 'device_model', render: (val: string | null) => val || '-' },
      { title: '开始时间', dataIndex: 'started_at', key: 'started_at', render: (date: string | null) => formatDateTime(date) },
      { title: '耗时', key: 'duration', render: (_: unknown, record: TestSession) => durationText(record) },
      {
        title: '操作',
        key: 'action',
        render: (_: unknown, record: TestSession) => (
          <Button
            type="text"
            icon={<EyeOutlined />}
            size="small"
            onClick={() => onAnalyze(record.id, { historyView: 'single' })}
          >
            分析
          </Button>
        ),
      },
    ],
    [onAnalyze],
  );

  if (batches.length === 0 && singles.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无测试记录" />;
  }

  return (
    <div className="session-history-list">
      <Tabs
        activeKey={activeHistoryView}
        onChange={(key) => handleHistoryViewChange(key as HistoryViewMode)}
        className="session-history-tabs"
        items={[
          {
            key: 'single',
            label: `单场景${singles.length > 0 ? ` (${singles.length})` : ''}`,
            children: singles.length > 0 ? (
              <Table columns={singleSceneColumns} dataSource={singles} rowKey="id" pagination={{ pageSize: 10 }} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无单场景测试记录" />
            ),
          },
          {
            key: 'multi',
            label: `多场景批次${batches.length > 0 ? ` (${batches.length})` : ''}`,
            children: batches.length > 0 ? (
              <MultiSceneBatchHistory
                batches={batches}
                onAnalyze={(sessionId) => onAnalyze(sessionId, { historyView: 'multi' })}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无多场景编排记录" />
            ),
          },
        ]}
      />
    </div>
  );
};

export default SessionHistoryList;
