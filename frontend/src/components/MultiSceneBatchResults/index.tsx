import React, { useState } from 'react';
import { Tabs, Tag, Typography } from 'antd';
import SessionResultPanel from '@/components/SessionResultPanel';
import type { BatchItem } from '@/api/unityBatches';

const itemStatusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  skipped: { color: 'default', text: '已跳过' },
  failed: { color: 'error', text: '失败' },
  cancelled: { color: 'default', text: '已取消' },
};

interface MultiSceneBatchResultsProps {
  items: BatchItem[];
}

const MultiSceneBatchResults: React.FC<MultiSceneBatchResultsProps> = ({ items }) => {
  const completedItems = items.filter((item) => item.current_session_id && item.status === 'completed');
  const [activeKey, setActiveKey] = useState(
    completedItems[0] ? String(completedItems[0].current_session_id) : undefined,
  );

  if (completedItems.length === 0) {
    return <Typography.Text type="secondary">暂无已完成场景结果</Typography.Text>;
  }

  return (
    <div className="unity-result-section">
      <div className="unity-result-heading">
        <Typography.Title level={4}>多场景测试结果</Typography.Title>
        <Typography.Text type="secondary">按场景查看独立会话的分析结果</Typography.Text>
      </div>
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        destroyInactiveTabPane
        items={completedItems.map((item) => {
          const status = itemStatusMap[item.status] || { color: 'default', text: item.status };
          return {
            key: String(item.current_session_id),
            label: (
              <span>
                {item.scene_display_name}{' '}
                <Tag color={status.color}>{status.text}</Tag>
              </span>
            ),
            children: <SessionResultPanel sessionId={item.current_session_id!} />,
          };
        })}
      />
    </div>
  );
};

export default MultiSceneBatchResults;
