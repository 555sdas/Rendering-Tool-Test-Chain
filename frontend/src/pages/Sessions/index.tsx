import React, { useCallback, useEffect, useState } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Input,
  Select,
  Space,
  Timeline,
  Descriptions,
  Modal,
  Tabs,
  message,
} from 'antd';
import {
  SearchOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  DesktopOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { TestSession } from '@/types';
import { sessionsApi } from '@/api/sessions';
import { formatDateTime, getApiDateTime } from '@/lib/datetime';

const { Option } = Select;
const { TabPane } = Tabs;

const getConfigString = (config: Record<string, unknown> | null | undefined, keys: string[], fallback = '-') => {
  for (const key of keys) {
    const value = config?.[key];
    if (value !== undefined && value !== null && value !== '') {
      return String(value);
    }
  }
  return fallback;
};

const getConfigNumber = (config: Record<string, unknown> | null | undefined, keys: string[], fallback = 0) => {
  for (const key of keys) {
    const value = config?.[key];
    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return fallback;
};

const mockSessions: TestSession[] = [
  {
    id: 1,
    name: 'VR场景渲染性能测试 - 高复杂度',
    description: 'LBE大空间场景渲染性能基准测试',
    status: 'completed',
    device_model: 'Meta Quest 3',
    os_version: 'Android 12',
    xr_runtime: 'OpenXR',
    app_version: '1.0.0',
    scene_id: 1,
    user_id: 1,
    project_id: 1,
    config: null,
    started_at: '2026-05-27T14:00:00Z',
    ended_at: '2026-05-27T14:30:00Z',
    duration_seconds: 1800,
    created_at: '2026-05-27T13:00:00Z',
    updated_at: '2026-05-27T14:30:00Z',
    task_id: 101,
    task_name: 'VR场景渲染性能测试 - 高复杂度',
    device_info: {
      device_name: 'Meta Quest 3',
      os_version: 'Android 12',
      gpu_model: 'Adreno 740',
      cpu_model: 'Snapdragon XR2 Gen 2',
      ram_gb: 8,
    },
    scene_info: {
      scene_name: 'LBE大空间场景',
      complexity: 'high',
      render_pipeline: 'URP',
    },
    start_time: '2026-05-27T14:00:00Z',
    end_time: '2026-05-27T14:30:00Z',
  },
  {
    id: 2,
    name: 'AR博物馆导览 - 端云协同',
    description: '博物馆文物展示端云协同测试',
    status: 'running',
    device_model: 'HoloLens 2',
    os_version: 'Windows Holographic',
    xr_runtime: 'Windows Mixed Reality',
    app_version: '1.0.0',
    scene_id: 2,
    user_id: 1,
    project_id: 2,
    config: null,
    started_at: '2026-05-27T13:15:00Z',
    ended_at: null,
    duration_seconds: null,
    created_at: '2026-05-27T13:00:00Z',
    updated_at: '2026-05-27T13:15:00Z',
    task_id: 102,
    task_name: 'AR博物馆导览 - 端云协同',
    device_info: {
      device_name: 'HoloLens 2',
      os_version: 'Windows Holographic',
      gpu_model: 'Adreno 630',
      cpu_model: 'Snapdragon 850',
      ram_gb: 4,
    },
    scene_info: {
      scene_name: '博物馆文物展示',
      complexity: 'medium',
      render_pipeline: 'MRTK',
    },
    start_time: '2026-05-27T13:15:00Z',
    end_time: null,
  },
  {
    id: 3,
    name: '多人空间协同 - 3用户场景',
    description: '协同会议室多人交互测试',
    status: 'failed',
    device_model: 'PICO 4',
    os_version: 'Android 10',
    xr_runtime: 'OpenXR',
    app_version: '1.0.0',
    scene_id: 3,
    user_id: 1,
    project_id: 3,
    config: null,
    started_at: '2026-05-27T11:00:00Z',
    ended_at: '2026-05-27T11:05:00Z',
    duration_seconds: 300,
    created_at: '2026-05-27T10:00:00Z',
    updated_at: '2026-05-27T11:05:00Z',
    task_id: 103,
    task_name: '多人空间协同 - 3用户场景',
    device_info: {
      device_name: 'PICO 4',
      os_version: 'Android 10',
      gpu_model: 'Adreno 650',
      cpu_model: 'Snapdragon XR2',
      ram_gb: 8,
    },
    scene_info: {
      scene_name: '协同会议室',
      complexity: 'medium',
      render_pipeline: 'URP',
    },
    start_time: '2026-05-27T11:00:00Z',
    end_time: '2026-05-27T11:05:00Z',
  },
  {
    id: 4,
    name: 'FFR特性开关对比测试',
    description: '固定注视点渲染特性开关对比',
    status: 'completed',
    device_model: 'Meta Quest 2',
    os_version: 'Android 10',
    xr_runtime: 'OpenXR',
    app_version: '1.0.0',
    scene_id: 4,
    user_id: 1,
    project_id: 4,
    config: null,
    started_at: '2026-05-26T16:30:00Z',
    ended_at: '2026-05-26T17:00:00Z',
    duration_seconds: 1800,
    created_at: '2026-05-26T16:00:00Z',
    updated_at: '2026-05-26T17:00:00Z',
    task_id: 104,
    task_name: 'FFR特性开关对比测试',
    device_info: {
      device_name: 'Meta Quest 2',
      os_version: 'Android 10',
      gpu_model: 'Adreno 650',
      cpu_model: 'Snapdragon XR2',
      ram_gb: 6,
    },
    scene_info: {
      scene_name: '标准测试场景',
      complexity: 'low',
      render_pipeline: 'URP',
    },
    start_time: '2026-05-26T16:30:00Z',
    end_time: '2026-05-26T17:00:00Z',
  },
  {
    id: 5,
    name: '端云渲染时延基准测试',
    description: 'CloudXR端云渲染时延基准测试',
    status: 'pending',
    device_model: 'Nreal Air',
    os_version: 'Android 11',
    xr_runtime: 'OpenXR',
    app_version: '1.0.0',
    scene_id: 5,
    user_id: 1,
    project_id: 5,
    config: null,
    started_at: '2026-05-27T15:00:00Z',
    ended_at: null,
    duration_seconds: null,
    created_at: '2026-05-27T14:00:00Z',
    updated_at: '2026-05-27T15:00:00Z',
    task_id: 105,
    task_name: '端云渲染时延基准测试',
    device_info: {
      device_name: 'Nreal Air',
      os_version: 'Android 11',
      gpu_model: 'Mali-G78',
      cpu_model: 'Dimensity 1200',
      ram_gb: 8,
    },
    scene_info: {
      scene_name: 'CloudXR测试场景',
      complexity: 'high',
      render_pipeline: 'CloudXR',
    },
    start_time: '2026-05-27T15:00:00Z',
    end_time: null,
  },
];

const statusConfig: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
  completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined /> },
  running: { color: 'processing', text: '运行中', icon: <PlayCircleOutlined /> },
  failed: { color: 'error', text: '失败', icon: <CloseCircleOutlined /> },
  pending: { color: 'default', text: '待执行', icon: <ClockCircleOutlined /> },
};

const Sessions: React.FC = () => {
  const [sessions, setSessions] = useState<TestSession[]>(mockSessions);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedSession, setSelectedSession] = useState<TestSession | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  const mapSession = useCallback((session: TestSession): TestSession => {
    const systemMemoryMb = getConfigNumber(session.config, ['system_memory_mb', 'systemMemorySize']);
    return {
      ...session,
      status: session.status as TestSession['status'],
      task_name: session.name,
      start_time: session.started_at || undefined,
      end_time: session.ended_at,
      device_info: {
        device_name: session.device_model || getConfigString(session.config, ['device_name', 'device_model'], '未知设备'),
        os_version: session.os_version || getConfigString(session.config, ['os_version'], '-'),
        gpu_model: getConfigString(session.config, ['gpu_model', 'graphicsDeviceName'], '-'),
        gpu_version: getConfigString(session.config, ['gpu_version', 'graphicsDeviceVersion'], '-'),
        gpu_memory_mb: getConfigNumber(session.config, ['gpu_memory_mb', 'graphicsMemorySize']),
        cpu_model: getConfigString(session.config, ['cpu_model', 'processorType'], '-'),
        ram_gb: getConfigNumber(session.config, ['ram_gb'], systemMemoryMb ? Number((systemMemoryMb / 1024).toFixed(2)) : 0),
        system_memory_mb: systemMemoryMb,
      },
      scene_info: {
        scene_name: getConfigString(session.config, ['scene_name'], `场景 ${session.scene_id || '-'}`),
        complexity: (session.config?.['complexity'] as NonNullable<TestSession['scene_info']>['complexity']) || 'medium',
        render_pipeline: getConfigString(session.config, ['render_pipeline'], 'URP'),
      },
    };
  }, []);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await sessionsApi.list({ limit: 100 });
      const apiSessions = response.items.map(mapSession);
      if (apiSessions.length > 0) {
        setSessions(apiSessions);
      }
    } catch {
      message.warning('未能读取后端测试会话，当前显示内置演示数据');
    } finally {
      setLoading(false);
    }
  }, [mapSession]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const filteredSessions = sessions.filter((s) => {
    const matchSearch = (s.task_name || s.name || '').toLowerCase().includes(searchText.toLowerCase());
    const matchStatus = statusFilter ? s.status === statusFilter : true;
    return matchSearch && matchStatus;
  });

  const handleViewDetail = (session: TestSession) => {
    setSelectedSession(session);
    setIsDetailOpen(true);
  };

  const getDuration = (start: string | undefined, end: string | null | undefined, durationSeconds?: number | null) => {
    if (durationSeconds !== undefined && durationSeconds !== null) {
      const mins = Math.floor(durationSeconds / 60);
      const secs = Math.floor(durationSeconds % 60);
      return `${mins}分${secs}秒`;
    }
    if (!start) return '-';
    const startTime = getApiDateTime(start);
    const endTime = end ? getApiDateTime(end) : Date.now();
    if (startTime === null || endTime === null) return '-';
    const diff = Math.floor((endTime - startTime) / 1000);
    const mins = Math.floor(diff / 60);
    const secs = diff % 60;
    return `${mins}分${secs}秒`;
  };

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      render: (_text: string, record: TestSession) => <strong>{record.task_name || record.name}</strong>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const config = statusConfig[status] || statusConfig.pending;
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.text}
          </Tag>
        );
      },
    },
    {
      title: '设备',
      dataIndex: 'device_info',
      key: 'device',
      render: (info: TestSession['device_info']) => (
        <Space>
          <DesktopOutlined />
          <span>{info?.device_name || '-'}</span>
        </Space>
      ),
    },
    {
      title: 'CPU',
      dataIndex: 'device_info',
      key: 'cpu',
      render: (info: TestSession['device_info']) => info?.cpu_model || '-',
    },
    {
      title: '场景复杂度',
      dataIndex: 'scene_info',
      key: 'complexity',
      render: (info: TestSession['scene_info']) => (
        <Tag color={info?.complexity === 'high' ? 'red' : info?.complexity === 'medium' ? 'orange' : 'green'}>
          {info?.complexity === 'high' ? '高' : info?.complexity === 'medium' ? '中' : '低'}
        </Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'start_time',
      key: 'start_time',
      render: (time: string | undefined) => formatDateTime(time),
    },
    {
      title: '结束时间',
      dataIndex: 'end_time',
      key: 'end_time',
      render: (time: string | null | undefined) => formatDateTime(time),
    },
    {
      title: '耗时',
      key: 'duration',
      render: (_: unknown, record: TestSession) =>
        getDuration(record.start_time, record.end_time, record.duration_seconds),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: TestSession) => (
        <Button type="text" icon={<EyeOutlined />} size="small" onClick={() => handleViewDetail(record)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>测试会话</h2>
        <Space>
          <Button onClick={loadSessions}>
            刷新
          </Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ color: '#475569', lineHeight: 1.8 }}>
          测试会话由 Unity 插件上传后自动生成或同步。项目用于归类测试结果；Unity 配置中的
          <strong> Project ID </strong>
          决定数据归到哪个项目。
          <br />
          自动上传模式填写平台地址：
          <code style={{ marginLeft: 8 }}>http://localhost:8002/api/v1</code>
        </div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder="搜索任务名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 280 }}
            allowClear
          />
          <Select
            placeholder="筛选状态"
            value={statusFilter || undefined}
            onChange={setStatusFilter}
            style={{ width: 140 }}
            allowClear
          >
            <Option value="pending">待执行</Option>
            <Option value="running">运行中</Option>
            <Option value="completed">已完成</Option>
            <Option value="failed">失败</Option>
          </Select>
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={filteredSessions}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        loading={loading}
      />

      <Modal
        title="测试会话详情"
        open={isDetailOpen}
        onCancel={() => setIsDetailOpen(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setIsDetailOpen(false)}>
            关闭
          </Button>,
        ]}
      >
        {selectedSession && (
          <Tabs defaultActiveKey="info">
            <TabPane tab="基本信息" key="info">
              <Descriptions bordered column={2} size="small">
                <Descriptions.Item label="任务名称" span={2}>
                  {selectedSession.task_name || selectedSession.name}
                </Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={statusConfig[selectedSession.status]?.color}>
                    {statusConfig[selectedSession.status]?.text}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="渲染管线">
                  {selectedSession.scene_info?.render_pipeline || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="开始时间">
                  {selectedSession.start_time
                    ? formatDateTime(selectedSession.start_time)
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="结束时间">
                  {selectedSession.end_time
                    ? formatDateTime(selectedSession.end_time)
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="耗时">
                  {getDuration(selectedSession.start_time, selectedSession.end_time, selectedSession.duration_seconds)}
                </Descriptions.Item>
                <Descriptions.Item label="上传模式">
                  {String(selectedSession.config?.['sync_mode'] || '-')}
                </Descriptions.Item>
              </Descriptions>

              <Descriptions bordered column={2} size="small" title="设备信息" style={{ marginTop: 16 }}>
                <Descriptions.Item label="设备名称">
                  {selectedSession.device_info?.device_name || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="操作系统">
                  {selectedSession.device_info?.os_version || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="GPU">
                  {selectedSession.device_info?.gpu_model || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="GPU版本">
                  {selectedSession.device_info?.gpu_version || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="显存">
                  {selectedSession.device_info?.gpu_memory_mb
                    ? `${selectedSession.device_info.gpu_memory_mb} MB`
                    : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="CPU">
                  {selectedSession.device_info?.cpu_model || '-'}
                </Descriptions.Item>
                <Descriptions.Item label="系统内存">
                  {selectedSession.device_info?.ram_gb ? `${selectedSession.device_info.ram_gb} GB` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="系统内存原始值">
                  {selectedSession.device_info?.system_memory_mb
                    ? `${selectedSession.device_info.system_memory_mb} MB`
                    : '-'}
                </Descriptions.Item>
              </Descriptions>
            </TabPane>
            <TabPane tab="执行日志" key="logs">
              <Timeline
                items={[
                  {
                    dot: <PlayCircleOutlined style={{ color: '#10b981' }} />,
                    children: `测试开始 - ${formatDateTime(selectedSession.start_time)}`,
                  },
                  {
                    dot: <ClockCircleOutlined style={{ color: '#3b82f6' }} />,
                    children: '场景加载完成，开始数据采集',
                  },
                  {
                    dot: <PauseCircleOutlined style={{ color: '#f59e0b' }} />,
                    children: '执行视角路线切换',
                  },
                  {
                    dot:
                      selectedSession.status === 'completed' ? (
                        <CheckCircleOutlined style={{ color: '#10b981' }} />
                      ) : selectedSession.status === 'failed' ? (
                        <CloseCircleOutlined style={{ color: '#ef4444' }} />
                      ) : (
                        <ClockCircleOutlined style={{ color: '#bfbfbf' }} />
                      ),
                    children:
                      selectedSession.status === 'completed'
                        ? `测试完成 - ${formatDateTime(selectedSession.end_time)}`
                        : selectedSession.status === 'failed'
                        ? `测试失败 - ${formatDateTime(selectedSession.end_time)}`
                        : '测试中...',
                  },
                ]}
              />
            </TabPane>
          </Tabs>
        )}
      </Modal>
    </div>
  );
};

export default Sessions;
