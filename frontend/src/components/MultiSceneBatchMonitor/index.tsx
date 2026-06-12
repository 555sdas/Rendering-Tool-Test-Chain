import React from 'react';
import { Alert, Button, Descriptions, Progress, Space, Steps, Tag } from 'antd';
import { StopOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { BatchItem, UnityBatchDetail } from '@/api/unityBatches';
import type { UnityRealtimeProgress } from '@/api/unityRunner';

const batchStatusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '待启动' },
  running: { color: 'processing', text: '运行中' },
  awaiting_user_decision: { color: 'warning', text: '等待处理' },
  completed: { color: 'success', text: '已完成' },
  partial_completed: { color: 'gold', text: '部分完成' },
  failed: { color: 'error', text: '失败' },
  cancelled: { color: 'default', text: '已取消' },
};

const itemStatusMap: Record<string, string> = {
  pending: '待执行',
  running: '运行中',
  uploading: '上传中',
  completed: '已完成',
  failed: '失败',
  awaiting_user_decision: '等待处理',
  skipped: '已跳过',
  cancelled: '已取消',
};

interface MultiSceneBatchMonitorProps {
  batchDetail: UnityBatchDetail;
  realtime: UnityRealtimeProgress | null;
  connection: 'connecting' | 'live' | 'polling';
  taskLogs: string[];
  stopping: boolean;
  onStop: () => void;
  onOpenDecision: () => void;
}

const MultiSceneBatchMonitor: React.FC<MultiSceneBatchMonitorProps> = ({
  batchDetail,
  realtime,
  connection,
  taskLogs,
  stopping,
  onStop,
  onOpenDecision,
}) => {
  const { batch, items, allowed_actions: allowedActions } = batchDetail;
  const status = batchStatusMap[batch.status] || { color: 'default', text: batch.status };
  const overallPercent = Math.round((realtime?.overall_progress ?? batch.result_summary?.overall_progress ?? 0) as number * 100);
  const currentIndex = realtime?.scene_index ?? batch.current_scene_index;
  const currentItem = items.find((item: BatchItem) => item.scene_index === currentIndex);
  const sceneLabel = realtime?.scene_display_name || currentItem?.scene_display_name || '-';

  return (
    <div className="unity-monitor">
      <div className="unity-monitor-header">
        <div>
          <div className="unity-monitor-title">
            <ThunderboltOutlined className="unity-monitor-title-icon" />
            多场景编排 #{batch.id}
            <Tag color={status.color}>{status.text}</Tag>
            <Tag color={connection === 'live' ? 'success' : connection === 'polling' ? 'warning' : 'default'}>
              {connection === 'live' ? 'WebSocket 实时连接' : connection === 'polling' ? '实时轮询连接' : '正在连接实时数据'}
            </Tag>
          </div>
          <div className="unity-monitor-subtitle">
            场景 {currentIndex + 1}/{batch.scene_total} · {sceneLabel}
            {realtime?.attempt ? ` · 尝试 ${realtime.attempt}` : ''}
            {batchDetail.parent_task ? ` · 父任务 ${batchDetail.parent_task.id}` : ''}
          </div>
        </div>
        <Space>
          {batch.status === 'awaiting_user_decision' && (
            <Button type="primary" onClick={onOpenDecision}>
              处理失败场景
            </Button>
          )}
          {allowedActions.includes('abort') && (
            <Button danger icon={<StopOutlined />} loading={stopping} onClick={onStop}>
              终止整批
            </Button>
          )}
        </Space>
      </div>

      <div className="unity-monitor-body">
        <div className="unity-monitor-summary">
          <div className="unity-progress-row">
            <Progress
              percent={overallPercent}
              status={batch.status === 'awaiting_user_decision' ? 'exception' : 'active'}
              strokeWidth={11}
              showInfo={false}
            />
            <strong>{overallPercent}%</strong>
          </div>
          <div className="unity-run-meta">
            <span>当前阶段：{realtime?.phase_label || '等待 Unity 上报'}</span>
            <span>当前场景进度：{Math.round((realtime?.scene_progress ?? realtime?.progress ?? 0) * 100)}%</span>
            <span>样本数：{realtime?.sample_count ?? 0}</span>
          </div>
          <Steps
            size="small"
            current={currentIndex}
            items={items.map((item: BatchItem) => ({
              title: item.scene_display_name,
              description: itemStatusMap[item.status] || item.status,
            }))}
          />
        </div>

        {batch.status === 'awaiting_user_decision' && (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 12 }}
            message="场景执行失败，编排已暂停"
            description={currentItem?.error_message || realtime?.error_message || realtime?.message || '请选择重试、跳过或终止整批。'}
            action={<Button size="small" type="primary" onClick={onOpenDecision}>立即处理</Button>}
          />
        )}

        <Descriptions bordered size="small" column={2} style={{ marginTop: 12 }}>
          {items.map((item: BatchItem) => (
            <Descriptions.Item key={item.id} label={`${item.scene_index + 1}. ${item.scene_display_name}`}>
              {itemStatusMap[item.status] || item.status}
              {item.current_session_id ? ` · 会话 ${item.current_session_id}` : ''}
            </Descriptions.Item>
          ))}
        </Descriptions>

        <div className="unity-live-log" style={{ marginTop: 12 }}>
          <div className="unity-live-log-title">
            <span>编排日志</span>
          </div>
          <pre>{taskLogs.length > 0 ? taskLogs.slice(-80).join('\n') : '等待 Unity 日志输出...'}</pre>
        </div>
      </div>
    </div>
  );
};

export default MultiSceneBatchMonitor;
