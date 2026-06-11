import React, { useCallback, useEffect, useRef, useState } from 'react';
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
  Collapse,
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
  StopOutlined,
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

const METRIC_CHECK_OPTIONS = [
  { value: 'frame_rate', title: 'FPS', detail: '平均帧率、最低帧率、掉帧趋势' },
  { value: 'frame_time', title: '帧时间', detail: 'P95/P99 帧时间、长帧风险' },
  { value: 'cpu', title: 'CPU', detail: 'CPU 占用、主线程压力估算' },
  { value: 'gpu', title: 'GPU / 渲染统计', detail: 'GPU 占用、Draw Call、三角面、SetPass' },
  { value: 'memory', title: '内存', detail: '总内存、托管堆、显存与渲染纹理' },
  { value: 'device_info', title: '设备信息', detail: 'CPU/GPU 型号、系统内存、Unity 与图形 API' },
];
const DEFAULT_METRIC_CHECKS = METRIC_CHECK_OPTIONS.map((item) => item.value);

const QUALITY_CHECK_GROUPS = [
  {
    key: 'lighting',
    title: '光照与阴影',
    options: [
      { value: 'lighting.active_lights', title: '活动光源数量', detail: '统计场景中启用的 Light 数量' },
      { value: 'lighting.realtime_lights', title: '实时光源数量', detail: '识别 Realtime 光源带来的实时光照成本' },
      { value: 'lighting.shadow_casters', title: '阴影投射数量', detail: '统计开启阴影投射的 Renderer 数量' },
      { value: 'lighting.reflection_probes', title: '反射探针数量', detail: '检查 Reflection Probe 规模' },
      { value: 'lighting.exposure_artifacts', title: '曝光/闪烁异常', detail: '评估曝光波动、过曝、欠曝和阴影闪烁标记' },
    ],
  },
  {
    key: 'materials',
    title: '材质与纹理',
    options: [
      { value: 'materials.material_slots', title: '材质槽数量', detail: '统计 Renderer 绑定的材质槽总量' },
      { value: 'materials.unique_materials', title: '唯一材质数量', detail: '评估材质复用和批处理友好度' },
      { value: 'materials.transparent_materials', title: '透明材质数量', detail: '定位透明排序和过绘制风险' },
      { value: 'materials.draw_calls', title: 'Draw Call / SetPass', detail: '结合运行时渲染批次评估材质切换成本' },
      { value: 'materials.texture_memory', title: '纹理内存', detail: '评估贴图尺寸、压缩和纹理流送压力' },
    ],
  },
  {
    key: 'post_processing',
    title: '后处理',
    options: [
      { value: 'post_processing.volumes', title: 'Volume 数量', detail: '统计后处理 Volume 规模' },
      { value: 'post_processing.render_textures', title: 'RenderTexture 数量', detail: '统计运行时 RenderTexture 资源数量' },
      { value: 'post_processing.render_texture_memory', title: '渲染纹理内存', detail: '评估后处理和中间纹理内存压力' },
      { value: 'post_processing.gpu_frame_budget', title: 'GPU 帧预算', detail: '结合 GPU 占用和 P95 帧时间判断后处理成本' },
      { value: 'post_processing.warnings', title: '后处理异常标记', detail: '接收画面偏色、模糊、抗锯齿等异常标记' },
    ],
  },
  {
    key: 'physics',
    title: '物理仿真',
    options: [
      { value: 'physics.rigidbodies', title: '刚体数量', detail: '统计 Rigidbody 规模和动态物理压力' },
      { value: 'physics.colliders', title: '碰撞体数量', detail: '统计 Collider 数量和碰撞层复杂度' },
      { value: 'physics.penetration', title: '穿模/碰撞异常', detail: '接收穿模、碰撞异常、物理告警标记' },
      { value: 'physics.pose_latency', title: '姿态/交互延迟', detail: '评估虚实融合交互响应延迟' },
      { value: 'physics.prediction_error', title: '预测误差', detail: '评估 XR 姿态预测误差风险' },
      { value: 'physics.long_frames', title: '物理相关长帧', detail: '结合长帧数量排查物理/动画/脚本峰值' },
    ],
  },
];

const DEFAULT_QUALITY_DETAIL_CHECKS = QUALITY_CHECK_GROUPS.flatMap((group) => group.options.map((item) => item.value));

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

interface StageLog {
  key: string;
  time: string;
  text: string;
  tone?: 'info' | 'success' | 'warning' | 'error';
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

function formatSelectedLabels(values: string[] | undefined, options: Array<{ value: string; title: string }>): string {
  if (!values?.length) return '未选择';
  const labels = new Map(options.map((item) => [item.value, item.title]));
  return values.map((value) => labels.get(value) || value).join('、');
}

function formatStageTime(): string {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false });
}

function buildQualityCategoryChecks(values: string[] | undefined) {
  const selected = new Set(values || []);
  return {
    lighting: QUALITY_CHECK_GROUPS.find((group) => group.key === 'lighting')?.options.some((item) => selected.has(item.value)) ?? false,
    materials: QUALITY_CHECK_GROUPS.find((group) => group.key === 'materials')?.options.some((item) => selected.has(item.value)) ?? false,
    post_processing: QUALITY_CHECK_GROUPS.find((group) => group.key === 'post_processing')?.options.some((item) => selected.has(item.value)) ?? false,
    physics: QUALITY_CHECK_GROUPS.find((group) => group.key === 'physics')?.options.some((item) => selected.has(item.value)) ?? false,
  };
}

function buildQualityDetailChecks(values: string[] | undefined): Record<string, boolean> {
  const selected = new Set(values || []);
  return Object.fromEntries(DEFAULT_QUALITY_DETAIL_CHECKS.map((key) => [key, selected.has(key)]));
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
  const [stopping, setStopping] = useState(false);
  const [activeRun, setActiveRun] = useState<ActiveUnityRun | null>(null);
  const [stageLogs, setStageLogs] = useState<StageLog[]>([
    { key: 'idle', time: formatStageTime(), text: '等待启动 Unity 测试。', tone: 'info' },
  ]);
  const [now, setNow] = useState(Date.now());
  const loggedStageKeysRef = useRef<Set<string>>(new Set(['idle']));
  const logBodyRef = useRef<HTMLDivElement | null>(null);
  const [form] = Form.useForm();
  const activeEstimate = activeRun ? getEstimatedRunProgress(activeRun, now) : null;

  const loadSessions = useCallback(async () => {
    if (!projectId) return;
    const sessionsData = await projectsApi.listSessions(Number(projectId));
    setSessions(sessionsData.items || []);
  }, [projectId]);

  const appendStageLog = useCallback((key: string, text: string, tone: StageLog['tone'] = 'info') => {
    if (loggedStageKeysRef.current.has(key)) return;
    loggedStageKeysRef.current.add(key);
    setStageLogs((current) => [...current, { key, time: formatStageTime(), text, tone }].slice(-80));
  }, []);

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
          metric_checks: DEFAULT_METRIC_CHECKS,
          quality_detail_checks: DEFAULT_QUALITY_DETAIL_CHECKS,
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

  useEffect(() => {
    if (!logBodyRef.current) return;
    logBodyRef.current.scrollTop = logBodyRef.current.scrollHeight;
  }, [stageLogs]);

  useEffect(() => {
    if (!activeRun || !activeEstimate) return;
    const taskKey = activeRun.taskId || activeRun.sessionId;

    appendStageLog(`task-${taskKey}`, `已创建测试会话 ${activeRun.sessionName}，任务 ${activeRun.taskId || '-'}。`, 'success');

    if (activeRun.status === 'completed') {
      appendStageLog(`done-${taskKey}`, '测试完成，采集数据已上传并绑定到当前会话。', 'success');
      return;
    }
    if (activeRun.status === 'cancelled') {
      appendStageLog(`cancel-${taskKey}`, '测试已停止，Unity 任务和会话已取消。', 'warning');
      return;
    }
    if (activeRun.status === 'failed') {
      appendStageLog(`failed-${taskKey}`, '测试执行失败，请检查 Unity 编辑器和后端日志。', 'error');
      return;
    }

    if (activeEstimate.phase === 'Unity 启动中') {
      appendStageLog(`launch-${taskKey}`, '正在启动 Unity 编辑器并加载场景资源。');
    } else if (activeEstimate.phase === '帧率采集中') {
      appendStageLog(`fps-${taskKey}`, `开始帧率阶段，采集 FPS 和帧时间，预计 ${formatDuration(activeRun.frameRateDurationSeconds)}。`);
    } else if (activeEstimate.phase === '指标采集中') {
      appendStageLog(`metrics-${taskKey}`, `开始指标阶段，采集性能项和已勾选的渲染质量子项，预计 ${formatDuration(activeRun.metricsDurationSeconds)}。`);
    } else if (activeEstimate.phase === '上传确认中') {
      appendStageLog(`upload-${taskKey}`, '采集阶段结束，等待 Unity 插件上传样本并刷新平台会话。');
    }
  }, [activeRun, activeEstimate, appendStageLog]);

  const handleStartUnityTest = async (values: {
    unity_engine_id: string;
    scene_resource_id: string;
    collect_interval: number;
    frame_rate_duration_seconds: number;
    metrics_duration_seconds: number;
    batchmode?: boolean;
    ensure_plugin?: boolean;
    metric_checks?: string[];
    quality_detail_checks?: string[];
  }) => {
    if (!projectId) return;
    const qualityCategoryChecks = buildQualityCategoryChecks(values.quality_detail_checks);
    const qualityDetailChecks = buildQualityDetailChecks(values.quality_detail_checks);
    const selectedMetricChecks = values.metric_checks ?? DEFAULT_METRIC_CHECKS;
    const metricChecks = new Set(selectedMetricChecks);
    setLaunching(true);
    loggedStageKeysRef.current = new Set(['prepare', 'config']);
    setStageLogs([
      { key: 'prepare', time: formatStageTime(), text: `准备创建 Unity 测试任务：项目 ${projectId}` },
      {
        key: 'config',
        time: formatStageTime(),
        text: `采集配置：性能项 ${formatSelectedLabels(selectedMetricChecks, METRIC_CHECK_OPTIONS)}；渲染质量子项 ${values.quality_detail_checks?.length || 0} 个。`,
      },
    ]);
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
        metric_checks: {
          frame_rate: metricChecks.has('frame_rate'),
          frame_time: metricChecks.has('frame_time'),
          cpu: metricChecks.has('cpu'),
          gpu: metricChecks.has('gpu'),
          memory: metricChecks.has('memory'),
          device_info: metricChecks.has('device_info'),
        },
        quality_checks: {
          lighting: qualityCategoryChecks.lighting,
          materials: qualityCategoryChecks.materials,
          post_processing: qualityCategoryChecks.post_processing,
          physics: qualityCategoryChecks.physics,
        },
        quality_metric_checks: qualityDetailChecks,
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
      appendStageLog(`started-${result.task.id}`, `后端已启动 Unity 进程，PID ${result.process_id}。`, 'success');
      await loadSessions();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '启动 Unity 测试失败');
    } finally {
      setLaunching(false);
    }
  };

  const handleStopUnityTest = async () => {
    if (!activeRun?.taskId) {
      message.warning('当前没有可停止的 Unity 任务');
      return;
    }

    setStopping(true);
    appendStageLog(`stop-request-${activeRun.taskId}`, '已发送停止 Unity 请求，正在终止进程。', 'warning');
    try {
      const result = await unityRunnerApi.stopTest(activeRun.taskId);
      if (result.session) {
        setActiveRun(createActiveRunFromSession(result.session, activeRun));
      } else {
        setActiveRun({ ...activeRun, status: 'cancelled', endedAtMs: Date.now() });
      }
      appendStageLog(`stop-done-${activeRun.taskId}`, 'Unity 停止完成，会话已标记为已取消。', 'warning');
      await loadSessions();
      message.success('Unity 停止请求已发送');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '停止 Unity 失败');
    } finally {
      setStopping(false);
    }
  };

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
              marginBottom: 16,
              padding: '12px 14px',
              border: '1px solid #dbeafe',
              borderRadius: 8,
              background: '#f8fbff',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <div style={{ minWidth: 260 }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 3 }}>
                  当前测试会话 {activeRun.sessionName}
                </div>
                <div style={{ color: '#64748b', fontSize: 13 }}>
                  任务 {activeRun.taskId || '-'} · 进程 {activeRun.processId || '-'}
                  {activeRun.engineName ? ` · ${activeRun.engineName}` : ''}
                  {activeRun.sceneName ? ` · ${activeRun.sceneName}` : ''}
                </div>
              </div>
              <div style={{ width: 260 }}>
                <Progress
                  percent={activeEstimate.percent}
                  status={activeEstimate.progressStatus}
                  strokeWidth={6}
                  trailColor="#dbeafe"
                  strokeColor="#1677ff"
                  size="small"
                />
              </div>
              <div style={{ color: '#475569', fontSize: 13, minWidth: 160 }}>
                <ClockCircleOutlined style={{ marginRight: 6, color: '#1677ff' }} />
                已运行 {activeEstimate.elapsedText} / 剩余 {activeEstimate.remainingText}
              </div>
              <Space>
                <Tag color={activeEstimate.tagColor} icon={activeEstimate.icon}>
                  {activeEstimate.statusText}
                </Tag>
                <Button
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => navigate(`/analysis?sessionId=${activeRun.sessionId}&projectId=${project.id}`)}
                >
                  分析
                </Button>
                <Button
                  size="small"
                  danger
                  icon={<StopOutlined />}
                  loading={stopping}
                  disabled={!activeRun.taskId || TERMINAL_SESSION_STATUSES.has(activeRun.status)}
                  onClick={handleStopUnityTest}
                >
                  停止 Unity
                </Button>
              </Space>
            </div>
          </div>
        )}

        <div
          style={{
            marginBottom: 18,
            border: '1px solid #1e293b',
            borderRadius: 8,
            overflow: 'hidden',
            background: '#020617',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '8px 12px',
              background: '#0f172a',
              color: '#e2e8f0',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <span>运行日志</span>
            <span style={{ color: '#94a3b8', fontWeight: 400 }}>
              {activeRun?.taskId ? `task ${activeRun.taskId}` : '未启动'}
            </span>
          </div>
          <div
            ref={logBodyRef}
            style={{
              height: 160,
              overflowY: 'auto',
              padding: '10px 12px',
              color: '#cbd5e1',
              fontFamily: 'Consolas, "Courier New", monospace',
              fontSize: 12,
              lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
            }}
          >
            {stageLogs.map((item) => (
              <div key={item.key}>
                <span style={{ color: '#64748b' }}>[{item.time}]</span>{' '}
                <span
                  style={{
                    color:
                      item.tone === 'success'
                        ? '#86efac'
                        : item.tone === 'warning'
                          ? '#fde68a'
                          : item.tone === 'error'
                            ? '#fca5a5'
                            : '#cbd5e1',
                  }}
                >
                  {item.text}
                </span>
              </div>
            ))}
          </div>
        </div>

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

          <Collapse
            size="small"
            style={{ marginBottom: 16, background: '#fff' }}
            items={[
              {
                key: 'metrics',
                forceRender: true,
                label: '性能采集项（默认全选，可展开调整）',
                children: (
                  <Form.Item name="metric_checks" style={{ marginBottom: 0 }}>
                    <Checkbox.Group style={{ width: '100%' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10 }}>
                        {METRIC_CHECK_OPTIONS.map((item) => (
                          <label
                            key={item.value}
                            style={{
                              display: 'flex',
                              gap: 8,
                              minHeight: 72,
                              padding: '10px 12px',
                              border: '1px solid #e2e8f0',
                              borderRadius: 8,
                              background: '#ffffff',
                              cursor: 'pointer',
                            }}
                          >
                            <Checkbox value={item.value} />
                            <span>
                              <span style={{ display: 'block', fontWeight: 600, color: '#0f172a' }}>{item.title}</span>
                              <span style={{ display: 'block', marginTop: 4, color: '#64748b', fontSize: 12, lineHeight: 1.45 }}>
                                {item.detail}
                              </span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </Checkbox.Group>
                  </Form.Item>
                ),
              },
            ]}
          />

          <Form.Item name="quality_detail_checks" label="渲染质量评估项">
            <Checkbox.Group style={{ width: '100%' }}>
              <Collapse
                size="small"
                defaultActiveKey={['lighting']}
                items={QUALITY_CHECK_GROUPS.map((group) => ({
                  key: group.key,
                  label: `${group.title}（${group.options.length} 个具体测试部分）`,
                  children: (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
                      {group.options.map((item) => (
                        <label
                          key={item.value}
                          style={{
                            display: 'flex',
                            gap: 8,
                            minHeight: 76,
                            padding: '10px 12px',
                            border: '1px solid #dbeafe',
                            borderRadius: 8,
                            background: '#f8fbff',
                            cursor: 'pointer',
                          }}
                        >
                          <Checkbox value={item.value} />
                          <span>
                            <span style={{ display: 'block', fontWeight: 600, color: '#0f172a' }}>{item.title}</span>
                            <span style={{ display: 'block', marginTop: 4, color: '#64748b', fontSize: 12, lineHeight: 1.45 }}>
                              {item.detail}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                  ),
                }))}
              />
            </Checkbox.Group>
          </Form.Item>

          <Space size="large" wrap>
            <Form.Item name="ensure_plugin" valuePropName="checked">
              <Checkbox>缺少插件时自动写入 manifest</Checkbox>
            </Form.Item>
            <Form.Item name="batchmode" valuePropName="checked">
              <Checkbox>使用 BatchMode</Checkbox>
            </Form.Item>
          </Space>

          <Space wrap>
            <Button
              type="primary"
              htmlType="submit"
              icon={<PlayCircleOutlined />}
              loading={launching}
            >
              启动 Unity 测试
            </Button>
            {activeRun && !TERMINAL_SESSION_STATUSES.has(activeRun.status) && (
              <Button
                danger
                icon={<StopOutlined />}
                loading={stopping}
                disabled={!activeRun.taskId}
                onClick={handleStopUnityTest}
              >
                停止 Unity
              </Button>
            )}
          </Space>
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
