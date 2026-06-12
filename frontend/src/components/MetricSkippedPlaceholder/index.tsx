import React from 'react';
import { Typography } from 'antd';

interface MetricSkippedPlaceholderProps {
  title?: string;
  description?: string;
}

const MetricSkippedPlaceholder: React.FC<MetricSkippedPlaceholderProps> = ({
  title = '未纳入本次测试',
  description = '该指标未在本次测试范围内，因此跳过采集与展示。',
}) => (
  <div
    style={{
      minHeight: 120,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#8c8c8c',
      background: '#fafafa',
      border: '1px dashed #d9d9d9',
      borderRadius: 8,
      padding: 24,
    }}
  >
    <Typography.Text type="secondary" strong>
      {title}
    </Typography.Text>
    <Typography.Text type="secondary" style={{ marginTop: 8, textAlign: 'center' }}>
      {description}
    </Typography.Text>
  </div>
);

export default MetricSkippedPlaceholder;
