import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Spin, Empty } from 'antd';
import {
  ProjectOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { projectsApi } from '@/api/projects';
import { sessionsApi, type TestSession } from '@/api/sessions';
import { formatDateTime, parseApiDate } from '@/lib/datetime';

const PIE_COLORS = ['#10b981', '#ef4444', '#3b82f6', '#f59e0b'];

const statusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
  paused: { color: 'warning', text: '已暂停' },
  cancelled: { color: 'default', text: '已取消' },
};

const columns = [
  {
    title: '测试会话',
    dataIndex: 'name',
    key: 'name',
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
    title: '设备',
    dataIndex: 'device_model',
    key: 'device_model',
    render: (v: string | null) => v || '-',
  },
  {
    title: '耗时',
    dataIndex: 'duration_seconds',
    key: 'duration',
    render: (v: number | null) => (v != null ? `${Math.round(v)}s` : '-'),
  },
  {
    title: '开始时间',
    dataIndex: 'started_at',
    key: 'started_at',
    render: (v: string | null) => formatDateTime(v),
  },
];

function buildTrendData(sessions: TestSession[]): { date: string; count: number }[] {
  const days: Record<string, number> = {};
  const today = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = `${d.getMonth() + 1}-${d.getDate()}`;
    days[key] = 0;
  }
  sessions.forEach((s) => {
    if (s.created_at) {
      const d = parseApiDate(s.created_at);
      if (!d) return;
      const key = `${d.getMonth() + 1}-${d.getDate()}`;
      if (days[key] !== undefined) days[key]++;
    }
  });
  return Object.entries(days).map(([date, count]) => ({ date, count }));
}

interface StatusPieItem {
  name: string;
  value: number;
}

const Dashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [projectCount, setProjectCount] = useState(0);
  const [sessionCount, setSessionCount] = useState(0);
  const [passRate, setPassRate] = useState<number | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [recentSessions, setRecentSessions] = useState<TestSession[]>([]);
  const [trendData, setTrendData] = useState<{ date: string; count: number }[]>([]);
  const [statusPieData, setStatusPieData] = useState<StatusPieItem[]>([]);

  useEffect(() => {
    const loadDashboard = async () => {
      setLoading(true);
      try {
        const [projects, sessionResult] = await Promise.all([
          projectsApi.list({ limit: 100 }),
          sessionsApi.list({ limit: 10 }),
        ]);

        const projectList = Array.isArray(projects) ? projects : [];
        setProjectCount(projectList.length);

        const { total, items } = sessionResult;
        setSessionCount(total);
        setRecentSessions(items);

        if (total > 0) {
          const [completedRes, failedRes, runningRes, pendingRes, trendRes] = await Promise.all([
            sessionsApi.list({ limit: 1, status: 'completed' }),
            sessionsApi.list({ limit: 1, status: 'failed' }),
            sessionsApi.list({ limit: 1, status: 'running' }),
            sessionsApi.list({ limit: 1, status: 'pending' }),
            sessionsApi.list({ limit: 500 }),
          ]);

          const finished = completedRes.total + failedRes.total;
          setPassRate(finished > 0 ? Math.round((completedRes.total / finished) * 1000) / 10 : null);
          setPendingCount(runningRes.total + pendingRes.total);

          // 按日期分组生成趋势图数据
          setTrendData(buildTrendData(trendRes.items));

          // 状态分布饼图
          const pieItems: StatusPieItem[] = [
            { name: '已完成', value: completedRes.total },
            { name: '失败', value: failedRes.total },
            { name: '运行中', value: runningRes.total },
            { name: '待执行', value: pendingRes.total },
          ].filter((item) => item.value > 0);
          setStatusPieData(pieItems);
        }
      } catch {
        // API 调用失败时保持默认值，不显示假数据
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const hasStats = projectCount > 0 || sessionCount > 0;
  const hasCharts = trendData.some((d) => d.count > 0) || statusPieData.length > 0;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" tip="加载仪表盘数据..." />
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>仪表盘</h2>

      {hasStats ? (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="项目总数"
                  value={projectCount}
                  prefix={<ProjectOutlined />}
                  valueStyle={{ color: '#3b82f6' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="测试会话"
                  value={sessionCount}
                  prefix={<PlayCircleOutlined />}
                  valueStyle={{ color: '#3b82f6' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="通过率"
                  value={passRate != null ? passRate : '-'}
                  suffix={passRate != null ? '%' : ''}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#10b981' }}
                />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card>
                <Statistic
                  title="待处理"
                  value={pendingCount}
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ color: '#f59e0b' }}
                />
              </Card>
            </Col>
          </Row>

          {hasCharts && (
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col xs={24} lg={14}>
                <Card title="近7天会话趋势">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={trendData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} name="会话数" />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
              </Col>
              <Col xs={24} lg={10}>
                <Card title="会话状态分布">
                  <ResponsiveContainer width="100%" height={260}>
                    <PieChart>
                      <Pie
                        data={statusPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={90}
                        paddingAngle={3}
                        dataKey="value"
                        label={({ name, value }) => `${name} ${value}`}
                      >
                        {statusPieData.map((_, index) => (
                          <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </Card>
              </Col>
            </Row>
          )}
        </>
      ) : (
        <Empty description="暂无统计数据，请先创建项目并运行测试" style={{ margin: '40px 0' }} />
      )}

      {recentSessions.length > 0 ? (
        <Card title="最近测试会话">
          <Table
            columns={columns}
            dataSource={recentSessions}
            rowKey="id"
            pagination={false}
            size="middle"
          />
        </Card>
      ) : hasStats ? (
        <Empty description="暂无测试会话记录" style={{ margin: '20px 0' }} />
      ) : null}
    </div>
  );
};

export default Dashboard;
