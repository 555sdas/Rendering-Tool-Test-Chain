import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Tag,
  Table,
  Button,
  message,
  Spin,
  Form,
  Select,
  Checkbox,
  InputNumber,
  Alert,
  Space,
  Progress,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  EyeOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { projectsApi, type Project } from '@/api/projects';
import { unityRunnerApi, type UnityEngineResource, type UnitySceneResource } from '@/api/unityRunner';
import type { TestSession } from '@/api/sessions';
import { formatDateTime, getApiDateTime } from '@/lib/datetime';

const { Option } = Select;

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

const RUNNING_SESSION_STATUSES = new Set(['pending', 'running']);
const TERMINAL_SESSION_STATUSES = new Set(['completed', 'failed', 'cancelled']);
const DEFAULT_LAUNCH_SECONDS = 6;
const DEFAULT_UPLOAD_SECONDS = 8;

interface ActiveUnityRun {
  taskId: number | null;
  sessionId: number;
  sessionName: string;
  status: string;
  startedAtMs: number;
  endedAtMs: number | null;
  frameRateDurationSeconds: number;
  metricsDurationSeconds: number;
  processId: number | null;
  engineName: string | null;
  sceneName: string | null;
}

interface EstimatedRunProgress {
  percent: number;
  phase: string;
  detail: string;
  elapsedText: string;
  remainingText: string;
  statusText: string;
  progressStatus: 'normal' | 'active' | 'exception' | 'success';
  tagColor: string;
  icon: React.ReactNode;
}

function getConfigNumber(config: Record<string, unknown> | null | undefined, key: string, fallback: number): number {
  const value = config?.[key];
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

function getConfigString(config: Record<string, unknown> | null | undefined, key: string): string | null {
  const value = config?.[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const rest = safeSeconds % 60;
  return minutes > 0 ? `${minutes}分${rest}秒` : `${rest}秒`;
}

function createActiveRunFromSession(
  session: TestSession,
  overrides: Partial<ActiveUnityRun> = {},
): ActiveUnityRun {
  const config = session.config || {};
  return {
    taskId: (overrides.taskId ?? getConfigNumber(config, 'test_task_id', 0)) || null,
    sessionId: session.id,
    sessionName: session.name,
    status: session.status,
    startedAtMs: getApiDateTime(session.started_at) ?? overrides.startedAtMs ?? Date.now(),
    endedAtMs: getApiDateTime(session.ended_at) ?? overrides.endedAtMs ?? null,
    frameRateDurationSeconds:
      overrides.frameRateDurationSeconds ??
      getConfigNumber(config, 'frame_rate_duration_seconds', 30),
    metricsDurationSeconds:
      overrides.metricsDurationSeconds ??
      getConfigNumber(config, 'metrics_duration_seconds', 30),
    processId: (overrides.processId ?? getConfigNumber(config, 'process_id', 0)) || null,
    engineName:
      overrides.engineName ??
      getConfigString(config, 'unity_engine_name') ??
      getConfigString(config, 'engine'),
    sceneName:
      overrides.sceneName ??
      getConfigString(config, 'scene_resource_name') ??
      getConfigString(config, 'unity_scene_path'),
  };
}

function getEstimatedRunProgress(run: ActiveUnityRun, now: number): EstimatedRunProgress {
  if (run.status === 'completed') {
    return {
      percent: 100,
      phase: '已完成',
      detail: '采集结果已同步到平台',
      elapsedText: formatDuration(((run.endedAtMs ?? now) - run.startedAtMs) / 1000),
      remainingText: '0秒',
      statusText: '会话已完成',
      progressStatus: 'success',
      tagColor: 'success',
      icon: <CheckCircleOutlined />,
    };
  }

  if (run.status === 'failed' || run.status === 'cancelled') {
    return {
      percent: 100,
      phase: run.status === 'failed' ? '执行失败' : '已取消',
      detail: '请查看 Unity 日志或会话详情',
      elapsedText: formatDuration(((run.endedAtMs ?? now) - run.startedAtMs) / 1000),
      remainingText: '-',
      statusText: sessionStatusMap[run.status]?.text || run.status,
      progressStatus: 'exception',
      tagColor: 'error',
      icon: <CloseCircleOutlined />,
    };
  }

  const frameSeconds = Math.max(1, run.frameRateDurationSeconds);
  const metricsSeconds = Math.max(1, run.metricsDurationSeconds);
  const totalSeconds = DEFAULT_LAUNCH_SECONDS + frameSeconds + metricsSeconds + DEFAULT_UPLOAD_SECONDS;
  const elapsedSeconds = Math.max(0, (now - run.startedAtMs) / 1000);
  const remainingSeconds = Math.max(0, totalSeconds - elapsedSeconds);
  const percent = Math.min(96, Math.max(2, Math.round((elapsedSeconds / totalSeconds) * 100)));

  let phase = 'Unity 启动中';
  let detail = '正在打开编辑器并载入场景';

  if (elapsedSeconds >= DEFAULT_LAUNCH_SECONDS + frameSeconds + metricsSeconds) {
    phase = '上传确认中';
    detail = '等待 Unity 上传样本并刷新会话状态';
  } else if (elapsedSeconds >= DEFAULT_LAUNCH_SECONDS + frameSeconds) {
    phase = '指标采集中';
    detail = 'CPU、GPU、内存和渲染质量指标';
  } else if (elapsedSeconds >= DEFAULT_LAUNCH_SECONDS) {
    phase = '帧率采集中';
    detail = 'FPS 和帧时间采样';
  }

  return {
    percent,
    phase,
    detail,
    elapsedText: formatDuration(elapsedSeconds),
    remainingText: remainingSeconds > 0 ? formatDuration(remainingSeconds) : '等待确认',
    statusText: sessionStatusMap[run.status]?.text || '运行中',
    progressStatus: 'active',
    tagColor: 'processing',
    icon: <LoadingOutlined />,
  };
}

const ProjectDetail: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [engines, setEngines] = useState<UnityEngineResource[]>([]);
  const [scenes, setScenes] = useState<UnitySceneResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [activeRun, setActiveRun] = useState<ActiveUnityRun | null>(null);
  const [now, setNow] = useState(Date.now());
  const [form] = Form.useForm();

  const loadSessions = useCallback(async () => {
    if (!projectId) return;
    const sessionsData = await projectsApi.listSessions(Number(projectId));
    setSessions(sessionsData.items || []);
  }, [projectId]);

  useEffect(() => {
    const loadData = async () => {
      if (!projectId) return;
      setLoading(true);
      try {
        const [projectData, sessionsData, engineData, sceneData] = await Promise.all([
          projectsApi.get(Number(projectId)),
          projectsApi.listSessions(Number(projectId)),
          unityRunnerApi.listEngines(),
          unityRunnerApi.listScenes({ project_id: Number(projectId) }),
        ]);
        setProject(projectData);
        setSessions(sessionsData.items || []);
        setEngines(engineData);
        setScenes(sceneData);

        const defaultEngine = engineData.find((item) => item.is_default && item.enabled) || engineData[0];
        const defaultScene = sceneData.find((item) => item.enabled) || sceneData[0];
        form.setFieldsValue({
          unity_engine_id: defaultEngine?.id,
          scene_resource_id: defaultScene?.id,
          collect_interval: 1,
          frame_rate_duration_seconds: 30,
          metrics_duration_seconds: 30,
          batchmode: false,
          ensure_plugin: true,
          quality_checks: ['lighting', 'materials', 'post_processing', 'physics'],
        });
      } catch {
        message.error('获取项目详情失败');
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [form, projectId]);

  useEffect(() => {
    setActiveRun((currentRun) => {
      if (currentRun) {
        const updatedSession = sessions.find((session) => session.id === currentRun.sessionId);
        if (!updatedSession) return currentRun;

        const updatedRun = createActiveRunFromSession(updatedSession, currentRun);
        if (
          updatedRun.status === currentRun.status &&
          updatedRun.endedAtMs === currentRun.endedAtMs &&
          updatedRun.frameRateDurationSeconds === currentRun.frameRateDurationSeconds &&
          updatedRun.metricsDurationSeconds === currentRun.metricsDurationSeconds
        ) {
          return currentRun;
        }
        return updatedRun;
      }

      const runningSession = sessions.find((session) => {
        const config = session.config || {};
        return (
          RUNNING_SESSION_STATUSES.has(session.status) &&
          (config.source === 'web_unity_runner' || Boolean(config.test_task_id))
        );
      });

      return runningSession ? createActiveRunFromSession(runningSession) : null;
    });
  }, [sessions]);

  useEffect(() => {
    if (!activeRun || TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;

    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [activeRun]);

  useEffect(() => {
    if (!activeRun || TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;

    const refreshTimer = window.setInterval(() => {
      loadSessions().catch(() => {
        message.warning('刷新会话状态失败');
      });
    }, 3000);

    return () => window.clearInterval(refreshTimer);
  }, [activeRun, loadSessions]);

  const handleStartUnityTest = async (values: {
    unity_engine_id: string;
    scene_resource_id: string;
    collect_interval: number;
    frame_rate_duration_seconds: number;
    metrics_duration_seconds: number;
    batchmode?: boolean;
    ensure_plugin?: boolean;
    quality_checks?: string[];
  }) => {
    if (!projectId) return;
    const checks = new Set(values.quality_checks || []);
    setLaunching(true);
    try {
      const result = await unityRunnerApi.startTest({
        project_id: Number(projectId),
        unity_engine_id: values.unity_engine_id,
        scene_resource_id: values.scene_resource_id,
        collect_interval: values.collect_interval,
        frame_rate_duration_seconds: values.frame_rate_duration_seconds,
        metrics_duration_seconds: values.metrics_duration_seconds,
        batchmode: Boolean(values.batchmode),
        ensure_plugin: values.ensure_plugin !== false,
        quality_checks: {
          lighting: checks.has('lighting'),
          materials: checks.has('materials'),
          post_processing: checks.has('post_processing'),
          physics: checks.has('physics'),
        },
      });
      setActiveRun(
        createActiveRunFromSession(result.session, {
          taskId: result.task.id,
          processId: result.process_id,
          engineName: result.engine.name,
          sceneName: result.scene.name,
          frameRateDurationSeconds: values.frame_rate_duration_seconds,
          metricsDurationSeconds: values.metrics_duration_seconds,
          startedAtMs: Date.now(),
        }),
      );
      setNow(Date.now());
      message.success(`Unity 已启动，任务 ${result.task.id}，会话 ${result.session.name}`);
      await loadSessions();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '启动 Unity 测试失败');
    } finally {
      setLaunching(false);
    }
  };

  const activeEstimate = activeRun ? getEstimatedRunProgress(activeRun, now) : null;

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
            {formatDateTime(project.created_at)}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {formatDateTime(project.updated_at)}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title="Unity 本地测试"
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadSessions}>
            刷新会话
          </Button>
        }
        style={{ marginBottom: 24 }}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="从后端已登记的 Unity 引擎和场景资源启动测试，Unity 插件会把采集结果上传并绑定到本项目的新会话。"
        />

        {activeRun && activeEstimate && (
          <div
            style={{
              marginBottom: 20,
              padding: 18,
              border: '1px solid #d6e4ff',
              borderRadius: 8,
              background: 'linear-gradient(180deg, #f8fbff 0%, #ffffff 100%)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 16,
                marginBottom: 12,
              }}
            >
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                  当前测试会话 {activeRun.sessionName}
                </div>
                <div style={{ color: '#64748b', fontSize: 13 }}>
                  任务 {activeRun.taskId || '-'} · 进程 {activeRun.processId || '-'}
                  {activeRun.engineName ? ` · ${activeRun.engineName}` : ''}
                  {activeRun.sceneName ? ` · ${activeRun.sceneName}` : ''}
                </div>
              </div>
              <Space>
                <Tag color={activeEstimate.tagColor} icon={activeEstimate.icon}>
                  {activeEstimate.phase}
                </Tag>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/analysis?sessionId=${activeRun.sessionId}&projectId=${project.id}`)}
                >
                  分析
                </Button>
              </Space>
            </div>

            <Progress
              percent={activeEstimate.percent}
              status={activeEstimate.progressStatus}
              strokeWidth={12}
              trailColor="#e8eef7"
              strokeColor={{
                '0%': '#1677ff',
                '55%': '#13c2c2',
                '100%': '#52c41a',
              }}
            />

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: 12,
                marginTop: 14,
              }}
            >
              <div style={{ padding: '10px 12px', background: '#ffffff', border: '1px solid #edf2f7', borderRadius: 6 }}>
                <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>当前阶段</div>
                <div style={{ fontWeight: 600 }}>{activeEstimate.detail}</div>
              </div>
              <div style={{ padding: '10px 12px', background: '#ffffff', border: '1px solid #edf2f7', borderRadius: 6 }}>
                <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>会话状态</div>
                <div style={{ fontWeight: 600 }}>{activeEstimate.statusText}</div>
              </div>
              <div style={{ padding: '10px 12px', background: '#ffffff', border: '1px solid #edf2f7', borderRadius: 6 }}>
                <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>已运行</div>
                <div style={{ fontWeight: 600 }}>
                  <ClockCircleOutlined style={{ marginRight: 6, color: '#1677ff' }} />
                  {activeEstimate.elapsedText}
                </div>
              </div>
              <div style={{ padding: '10px 12px', background: '#ffffff', border: '1px solid #edf2f7', borderRadius: 6 }}>
                <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>预计剩余</div>
                <div style={{ fontWeight: 600 }}>{activeEstimate.remainingText}</div>
              </div>
            </div>
          </div>
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleStartUnityTest}
        >
          <Form.Item
            name="unity_engine_id"
            label="Unity 引擎"
            rules={[{ required: true, message: '请选择 Unity 引擎' }]}
          >
            <Select placeholder="请选择 Unity 引擎">
              {engines.map((engine) => (
                <Option key={engine.id} value={engine.id} disabled={!engine.enabled || !engine.exists}>
                  {engine.name} {engine.exists ? '' : '（路径不存在）'}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="scene_resource_id"
            label="场景资源"
            rules={[{ required: true, message: '请选择场景资源' }]}
          >
            <Select placeholder="请选择场景资源">
              {scenes.map((scene) => (
                <Option key={scene.id} value={scene.id} disabled={!scene.enabled || !scene.exists}>
                  {scene.name} {scene.manifest_has_plugin ? '' : '（将自动写入插件包）'}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Space size="large" wrap>
            <Form.Item name="collect_interval" label="采集间隔（秒）" rules={[{ required: true }]}>
              <InputNumber min={0.1} max={10} step={0.1} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="frame_rate_duration_seconds" label="帧率采集时长（秒）" rules={[{ required: true }]}>
              <InputNumber min={1} max={600} step={1} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="metrics_duration_seconds" label="指标采集时长（秒）" rules={[{ required: true }]}>
              <InputNumber min={1} max={600} step={1} style={{ width: 180 }} />
            </Form.Item>
          </Space>

          <Form.Item
            name="quality_checks"
            label="渲染质量测试项"
            rules={[{ required: true, message: '请至少选择一个测试项' }]}
          >
            <Checkbox.Group
              options={[
                { label: '光照与阴影', value: 'lighting' },
                { label: '材质与纹理', value: 'materials' },
                { label: '后处理', value: 'post_processing' },
                { label: '物理仿真', value: 'physics' },
              ]}
            />
          </Form.Item>

          <Space size="large" wrap>
            <Form.Item name="ensure_plugin" valuePropName="checked">
              <Checkbox>缺少插件时自动写入 manifest</Checkbox>
            </Form.Item>
            <Form.Item name="batchmode" valuePropName="checked">
              <Checkbox>使用 BatchMode</Checkbox>
            </Form.Item>
          </Space>

          <Button
            type="primary"
            htmlType="submit"
            icon={<PlayCircleOutlined />}
            loading={launching}
          >
            启动 Unity 测试
          </Button>
        </Form>
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
