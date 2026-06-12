import React, { useMemo, useState } from 'react';
import { Button, Collapse, Empty, Table, Tabs, Tag } from 'antd';
import { EyeOutlined } from '@ant-design/icons';
import type { TestSession } from '@/api/sessions';
import { formatDateTime } from '@/lib/datetime';
import { getSessionSceneLabel } from '@/lib/sessionScene';
import {
  getBatchSceneLabels,
  groupSessionsForHistory,
  summarizeBatchStatus,
} from '@/lib/sessionHistory';

const sessionStatusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
  paused: { color: 'warning', text: '已暂停' },
  cancelled: { color: 'default', text: '已取消' },
};

interface SessionHistoryListProps {
  sessions: TestSession[];
  onAnalyze: (sessionId: number) => void;
}

const SessionHistoryList: React.FC<SessionHistoryListProps> = ({
  sessions,
  onAnalyze,
}) => {
  const { batches, singles } = useMemo(() => groupSessionsForHistory(sessions), [sessions]);
  const [activeTab, setActiveTab] = useState<'single' | 'multi'>(() =>
    singles.length === 0 && batches.length > 0 ? 'multi' : 'single',
  );

  const childColumns = [
    {
      title: '顺序',
      key: 'scene_index',
      width: 72,
      render: (_: unknown, record: TestSession) => {
        const index = Number((record.config as Record<string, unknown> | undefined)?.scene_index ?? 0);
        return <Tag>{index + 1}</Tag>;
      },
    },
    {
      title: '会话',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: '测试场景',
      key: 'scene_display_name',
      render: (_: unknown, record: TestSession) => (
        <Tag color="geekblue">{getSessionSceneLabel(record)}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const config = sessionStatusMap[status] || sessionStatusMap.pending;
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '设备',
      dataIndex: 'device_model',
      key: 'device_model',
      render: (val: string | null) => val || '-',
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (date: string | null) => formatDateTime(date),
    },
    {
      title: '结束时间',
      dataIndex: 'ended_at',
      key: 'ended_at',
      render: (date: string | null) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: TestSession) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          size="small"
          onClick={() => onAnalyze(record.id)}
        >
          分析
        </Button>
      ),
    },
  ];

  const singleSceneColumns = [
    {
      title: '会话',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: '测试场景',
      key: 'scene_display_name',
      render: (_: unknown, record: TestSession) => (
        <Tag color="geekblue">{getSessionSceneLabel(record)}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const config = sessionStatusMap[status] || sessionStatusMap.pending;
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '设备',
      dataIndex: 'device_model',
      key: 'device_model',
      render: (val: string | null) => val || '-',
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (date: string | null) => formatDateTime(date),
    },
    {
      title: '结束时间',
      dataIndex: 'ended_at',
      key: 'ended_at',
      render: (date: string | null) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: TestSession) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          size="small"
          onClick={() => onAnalyze(record.id)}
        >
          分析
        </Button>
      ),
    },
  ];

  const batchCollapseItems = batches.map((batch) => {
    const summary = summarizeBatchStatus(batch.sessions);
    const sceneLabels = getBatchSceneLabels(batch.sessions);
    const uniqueSceneCount = new Set(
      batch.sessions.map((item) => Number((item.config as Record<string, unknown> | undefined)?.scene_index ?? -1)),
    ).size;
    const batchStartedAt = batch.sessions[0]?.started_at ?? null;
    const batchEndedAt = [...batch.sessions]
      .map((item) => item.ended_at)
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;

    return {
      key: String(batch.batchId),
      label: (
        <div className="session-history-batch-header">
          <div className="session-history-batch-header__main">
            <Tag color="purple">多场景</Tag>
            <strong>编排 #{batch.batchId}</strong>
            <span className="session-history-batch-header__scenes">{sceneLabels}</span>
          </div>
          <div className="session-history-batch-header__meta">
            <Tag color={summary.color}>{summary.text}</Tag>
            <span>
              {uniqueSceneCount}/{batch.sceneTotal} 场景 · {batch.sessions.length} 个会话
            </span>
            <span>
              {formatDateTime(batchStartedAt)}
              {batchEndedAt ? ` — ${formatDateTime(batchEndedAt)}` : ''}
            </span>
          </div>
        </div>
      ),
      children: (
        <Table
          columns={childColumns}
          dataSource={batch.sessions}
          rowKey="id"
          pagination={false}
          size="small"
        />
      ),
    };
  });

  if (batches.length === 0 && singles.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无测试记录" />;
  }

  return (
    <div className="session-history-list">
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'single' | 'multi')}
        className="session-history-tabs"
        items={[
          {
            key: 'single',
            label: `单场景${singles.length > 0 ? ` (${singles.length})` : ''}`,
            children: singles.length > 0 ? (
              <Table
                columns={singleSceneColumns}
                dataSource={singles}
                rowKey="id"
                pagination={{ pageSize: 10 }}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无单场景测试记录" />
            ),
          },
          {
            key: 'multi',
            label: `多场景${batches.length > 0 ? ` (${batches.length})` : ''}`,
            children: batches.length > 0 ? (
              <Collapse
                accordion={false}
                defaultActiveKey={[String(batches[0].batchId)]}
                items={batchCollapseItems}
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
