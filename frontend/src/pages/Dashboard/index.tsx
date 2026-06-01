import React from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Progress } from 'antd';
import {
  ProjectOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
} from '@ant-design/icons';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const trendData = [
  { date: '05-21', sessions: 12, passed: 10, failed: 2 },
  { date: '05-22', sessions: 15, passed: 13, failed: 2 },
  { date: '05-23', sessions: 8, passed: 7, failed: 1 },
  { date: '05-24', sessions: 18, passed: 15, failed: 3 },
  { date: '05-25', sessions: 22, passed: 19, failed: 3 },
  { date: '05-26', sessions: 16, passed: 14, failed: 2 },
  { date: '05-27', sessions: 20, passed: 18, failed: 2 },
];

const recentActivities = [
  {
    key: '1',
    task: 'VR场景渲染性能测试',
    project: '子标的二-渲染质量',
    status: 'completed',
    fps: 72,
    time: '2026-05-27 14:30',
  },
  {
    key: '2',
    task: 'AR博物馆导览场景测试',
    project: '子标的四-云AR协同',
    status: 'running',
    fps: 58,
    time: '2026-05-27 13:15',
  },
  {
    key: '3',
    task: '多人空间协同稳定性测试',
    project: '子标的四-协同测试',
    status: 'failed',
    fps: 0,
    time: '2026-05-27 11:00',
  },
  {
    key: '4',
    task: 'FFR特性收益对比测试',
    project: '子标的三-图形特性',
    status: 'completed',
    fps: 65,
    time: '2026-05-26 16:45',
  },
  {
    key: '5',
    task: '端云渲染时延测试',
    project: '子标的四-端云协同',
    status: 'completed',
    fps: 45,
    time: '2026-05-26 10:20',
  },
];

const statusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
};

const columns = [
  {
    title: '测试任务',
    dataIndex: 'task',
    key: 'task',
  },
  {
    title: '所属项目',
    dataIndex: 'project',
    key: 'project',
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (status: string) => {
      const config = statusMap[status] || statusMap.pending;
      return <Tag color={config.color}>{config.text}</Tag>;
    },
  },
  {
    title: '平均FPS',
    dataIndex: 'fps',
    key: 'fps',
    render: (fps: number) => (
      <span style={{ fontFamily: 'monospace' }}>{fps > 0 ? fps : '-'}</span>
    ),
  },
  {
    title: '执行时间',
    dataIndex: 'time',
    key: 'time',
  },
];

const Dashboard: React.FC = () => {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="项目总数"
              value={24}
              prefix={<ProjectOutlined />}
              valueStyle={{ color: '#3b82f6' }}
            />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ArrowUpOutlined style={{ color: '#10b981' }} /> 较上周 +3
              </Text>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="测试会话"
              value={156}
              prefix={<PlayCircleOutlined />}
              valueStyle={{ color: '#3b82f6' }}
            />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ArrowUpOutlined style={{ color: '#10b981' }} /> 较上周 +12
              </Text>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="通过率"
              value={87.5}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#10b981' }}
            />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ArrowUpOutlined style={{ color: '#10b981' }} /> 较上周 +2.3%
              </Text>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="待处理任务"
              value={5}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#f59e0b' }}
            />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                <ArrowDownOutlined style={{ color: '#10b981' }} /> 较上周 -2
              </Text>
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="近7天测试趋势">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="sessions"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.1}
                  name="总测试数"
                />
                <Area
                  type="monotone"
                  dataKey="passed"
                  stroke="#10b981"
                  fill="#10b981"
                  fillOpacity={0.1}
                  name="通过"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="系统状态">
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>采集插件在线率</span>
                <span>92%</span>
              </div>
              <Progress percent={92} status="active" strokeColor="#3b82f6" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>存储空间使用</span>
                <span>68%</span>
              </div>
              <Progress percent={68} status="active" strokeColor="#10b981" />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>队列任务处理</span>
                <span>45%</span>
              </div>
              <Progress percent={45} status="active" strokeColor="#f59e0b" />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span>数据库连接</span>
                <span>100%</span>
              </div>
              <Progress percent={100} strokeColor="#10b981" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="最近测试活动">
        <Table
          columns={columns}
          dataSource={recentActivities}
          pagination={false}
          size="middle"
        />
      </Card>
    </div>
  );
};

const Text: React.FC<{ type?: string; style?: React.CSSProperties; children: React.ReactNode }> = ({ type, style, children }) => {
  const colorMap: Record<string, string> = {
    secondary: '#8c8c8c',
  };
  return <span style={{ color: type ? colorMap[type] || '#000' : '#000', ...style }}>{children}</span>;
};

export default Dashboard;
