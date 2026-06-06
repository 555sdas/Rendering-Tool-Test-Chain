import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Tag,
  Table,
  Button,
  message,
  Spin,
} from 'antd';
import { ArrowLeftOutlined, EyeOutlined } from '@ant-design/icons';
import { projectsApi, type Project } from '@/api/projects';
import type { TestSession } from '@/types';

const statusMap: Record<string, { color: string; text: string }> = {
  active: { color: 'success', text: '进行中' },
  draft: { color: 'warning', text: '草稿' },
  archived: { color: 'default', text: '已归档' },
};

const sessionStatusMap: Record<string, { color: string; text: string }> = {
  completed: { color: 'success', text: '已完成' },
  running: { color: 'processing', text: '运行中' },
  failed: { color: 'error', text: '失败' },
  pending: { color: 'default', text: '待执行' },
  paused: { color: 'warning', text: '已暂停' },
  cancelled: { color: 'default', text: '已取消' },
};

const ProjectDetail: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return;
      setLoading(true);
      try {
        const [projectData, sessionsData] = await Promise.all([
          projectsApi.get(Number(projectId)),
          projectsApi.listSessions(Number(projectId)),
        ]);
        setProject(projectData);
        setSessions(sessionsData.items || []);
      } catch {
        message.error('获取项目详情失败');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [projectId]);

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 80 }} />;
  }

  if (!project) {
    return <div style={{ textAlign: 'center', marginTop: 80, color: '#999' }}>项目不存在</div>;
  }

  const sessionColumns = [
    {
      title: '会话名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>,
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
      render: (date: string | null) => (date ? new Date(date).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '结束时间',
      dataIndex: 'ended_at',
      key: 'ended_at',
      render: (date: string | null) => (date ? new Date(date).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: TestSession) => (
        <Button type="text" icon={<EyeOutlined />} size="small" onClick={() => navigate(`/analysis?sessionId=${record.id}&projectId=${project.id}`)}>
          分析
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/projects')}
        style={{ padding: 0, marginBottom: 16 }}
      >
        返回项目列表
      </Button>

      <Card title="项目信息" style={{ marginBottom: 24 }}>
        <Descriptions bordered column={2} size="small">
          <Descriptions.Item label="项目名称" span={2}>
            {project.name}
          </Descriptions.Item>
          <Descriptions.Item label="类型">
            <Tag color="blue">{project.project_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusMap[project.status]?.color}>
              {statusMap[project.status]?.text || project.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {project.description || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(project.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {project.updated_at ? new Date(project.updated_at).toLocaleString('zh-CN') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="关联测试会话">
        <Table
          columns={sessionColumns}
          dataSource={sessions}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
};

export default ProjectDetail;
