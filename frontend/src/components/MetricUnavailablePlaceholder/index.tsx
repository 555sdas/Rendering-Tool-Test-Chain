import React from 'react';
import { Typography } from 'antd';

interface MetricUnavailablePlaceholderProps {
  title?: string;
  description?: string;
}

const MetricUnavailablePlaceholder: React.FC<MetricUnavailablePlaceholderProps> = ({
  title = '采集不可用',
  description = '该指标已纳入本次测试，但当前运行环境未提供有效数据。',
}) => (
  <div
    style={{
      minHeight: 120,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#ad6800',
      background: '#fffbe6',
      border: '1px dashed #ffe58f',
      borderRadius: 8,
      padding: 24,
    }}
  >
    <Typography.Text style={{ color: '#ad6800' }} strong>
      {title}
    </Typography.Text>
    <Typography.Text style={{ marginTop: 8, textAlign: 'center', color: '#ad6800' }}>
      {description}
    </Typography.Text>
  </div>
);

export default MetricUnavailablePlaceholder;
