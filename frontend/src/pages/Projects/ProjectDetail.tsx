import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Tag,
  Button,
  message,
  notification,
  Spin,
  Form,
  Select,
  Checkbox,
  InputNumber,
  Alert,
  Space,
  Progress,
  Steps,
  Typography,
  Tabs,
  Modal,
} from 'antd';
import SessionResultPanel from '@/components/SessionResultPanel';
import MetricScopeSelector from '@/components/MetricScopeSelector';
import TestScopeBanner from '@/components/TestScopeBanner';
import {
  buildBuiltinDefaultScope,
  fillScopeKeys,
  hasAnyEnabledLeaf,
  inferScopeFromSessionConfig,
  isMetricEnabled,
  type MetricCatalog,
  type TestScope,
} from '@/lib/testScope';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EyeOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { projectsApi, type Project } from '@/api/projects';
import {
  createUnityProgressWebSocket,
  unityRunnerApi,
  type UnityEngineResource,
  type UnityRealtimeProgress,
  type UnitySceneResource,
} from '@/api/unityRunner';
import type { TestSession } from '@/api/sessions';
import { formatDateTime, getApiDateTime } from '@/lib/datetime';
import MultiSceneOrchestrationPanel from '@/components/MultiSceneOrchestrationPanel';
import MultiSceneBatchMonitor from '@/components/MultiSceneBatchMonitor';
import MultiSceneBatchResults from '@/components/MultiSceneBatchResults';
import SessionHistoryList from '@/components/SessionHistoryList';
import {
  buildProjectHistoryReturnPath,
  parseHistoryViewParam,
  sessionHistoryView,
  type HistoryViewMode,
} from '@/lib/sessionHistory';
import type { SceneRunDraft } from '@/components/MultiSceneOrchestrationPanel/types';
import { unityBatchesApi, type UnityBatchDetail } from '@/api/unityBatches';
import './ProjectDetail.css';

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
const TERMINAL_BATCH_STATUSES = new Set(['completed', 'partial_completed', 'failed', 'cancelled']);

function isCollectingProgress(progress: UnityRealtimeProgress): boolean {
  return progress.phase !== 'uploading' && progress.phase_label !== '上传结果';
}

function isUploadingProgress(progress: UnityRealtimeProgress): boolean {
  return progress.phase === 'uploading' || progress.phase_label === '上传结果';
}

function findActiveSingleSceneSession(sessions: TestSession[]): TestSession | null {
  return sessions.find((session) => {
    const config = session.config || {};
    return (
      RUNNING_SESSION_STATUSES.has(session.status) &&
      config.run_mode !== 'multi_scene' &&
      (config.source === 'web_unity_runner' || Boolean(config.test_task_id))
    );
  }) ?? null;
}

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

interface MetricTileProps {
  label: string;
  value: string | number;
  accent?: string;
  skipped?: boolean;
  pending?: boolean;
}

const MetricTile: React.FC<MetricTileProps> = ({ label, value, accent = '#111827', skipped = false, pending = false }) => (
  <div className="unity-metric-tile">
    <div className="unity-metric-label">{label}</div>
    {skipped ? (
      <Tag color="default">跳过</Tag>
    ) : pending ? (
      <div className="unity-metric-value" style={{ color: '#8c8c8c' }}>等待采集</div>
    ) : (
      <div className="unity-metric-value" style={{ color: accent }}>{value}</div>
    )}
  </div>
);

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

function getRunProgressDisplay(
  run: ActiveUnityRun,
  now: number,
  realtime: UnityRealtimeProgress | null,
): EstimatedRunProgress {
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

  const elapsedSeconds = Math.max(0, (now - run.startedAtMs) / 1000);
  const elapsedText = formatDuration(elapsedSeconds);

  if (!realtime) {
    return {
      percent: 0,
      phase: '等待 Unity',
      detail: '正在启动编辑器并载入场景，采集开始后进度条将更新',
      elapsedText,
      remainingText: '等待采集开始',
      statusText: sessionStatusMap[run.status]?.text || '运行中',
      progressStatus: 'normal',
      tagColor: 'processing',
      icon: <LoadingOutlined />,
    };
  }

  return {
    percent: Math.min(100, Math.max(0, Math.round(realtime.progress * 100))),
    phase: realtime.phase_label,
    detail: `已采集 ${realtime.sample_count} 个实时样本`,
    elapsedText,
    remainingText: formatDuration(realtime.remaining_seconds),
    statusText: sessionStatusMap[run.status]?.text || '运行中',
    progressStatus: 'active',
    tagColor: 'processing',
    icon: <LoadingOutlined />,
  };
}

function getCollectionStepState(
  run: ActiveUnityRun,
  realtime: UnityRealtimeProgress | null,
): { current: number; status: 'process' | 'finish' | 'error' } {
  if (run.status === 'completed') {
    return { current: 4, status: 'finish' };
  }

  if (run.status === 'failed' || run.status === 'cancelled') {
    let current = 0;
    if (realtime) {
      if (isUploadingProgress(realtime)) current = 3;
      else if (realtime.phase === 'metrics' || realtime.phase_label.includes('指标')) current = 2;
      else if (isCollectingProgress(realtime)) current = 1;
    }
    return { current, status: 'error' };
  }

  if (!realtime) return { current: 0, status: 'process' };
  if (isUploadingProgress(realtime)) return { current: 3, status: 'process' };
  if (realtime.phase === 'metrics' || realtime.phase_label.includes('指标')) {
    return { current: 2, status: 'process' };
  }
  return { current: 1, status: 'process' };
}

const ProjectDetail: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [project, setProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<TestSession[]>([]);
  const [engines, setEngines] = useState<UnityEngineResource[]>([]);
  const [scenes, setScenes] = useState<UnitySceneResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [launching, setLaunching] = useState(false);
  const [activeRun, setActiveRun] = useState<ActiveUnityRun | null>(null);
  const [taskLogs, setTaskLogs] = useState<string[]>([]);
  const liveLogRef = React.useRef<HTMLPreElement>(null);
  const collectionNotifyRef = useRef<{ taskId: number | null; started: boolean; ended: boolean }>({
    taskId: null,
    started: false,
    ended: false,
  });
  const batchNotifyRef = useRef<{
    batchId: number | null;
    sceneIndex: number | null;
    ended: boolean;
  }>({
    batchId: null,
    sceneIndex: null,
    ended: false,
  });
  const [taskError, setTaskError] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const [realtimeProgress, setRealtimeProgress] = useState<UnityRealtimeProgress | null>(null);
  const [realtimeConnection, setRealtimeConnection] = useState<'connecting' | 'live' | 'polling'>('connecting');
  const [now, setNow] = useState(Date.now());
  const [activeTab, setActiveTab] = useState(() => (searchParams.get('tab') === 'history' ? 'history' : 'unity'));
  const historyView = parseHistoryViewParam(searchParams.get('historyView'));

  useEffect(() => {
    const tabFromUrl = searchParams.get('tab') === 'history' ? 'history' : 'unity';
    setActiveTab(tabFromUrl);
  }, [searchParams]);

  const handleTabChange = (key: string) => {
    setActiveTab(key);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (key === 'unity') {
          next.delete('tab');
          next.delete('historyView');
        } else {
          next.set('tab', key);
          if (key !== 'history') {
            next.delete('historyView');
          }
        }
        return next;
      },
      { replace: true },
    );
  };

  const handleHistoryViewChange = (view: HistoryViewMode) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', 'history');
        if (view === 'multi') {
          next.set('historyView', 'multi');
        } else {
          next.delete('historyView');
        }
        return next;
      },
      { replace: true },
    );
  };
  const [showUnityConfig, setShowUnityConfig] = useState(true);
  const [resultSessionId, setResultSessionId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const [metricsCatalog, setMetricsCatalog] = useState<MetricCatalog | null>(null);
  const [testScope, setTestScope] = useState<TestScope>(buildBuiltinDefaultScope('global_default'));
  const [activeRunScope, setActiveRunScope] = useState<TestScope | null>(null);
  const [runMode, setRunMode] = useState<'single' | 'multi'>('single');
  const [sceneDrafts, setSceneDrafts] = useState<SceneRunDraft[]>([]);
  const [activeBatchDetail, setActiveBatchDetail] = useState<UnityBatchDetail | null>(null);
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);

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
        const [projectData, sessionsData, engineData, sceneData, catalog, defaultScope] = await Promise.all([
          projectsApi.get(Number(projectId)),
          projectsApi.listSessions(Number(projectId)),
          unityRunnerApi.listEngines(),
          unityRunnerApi.listScenes({ project_id: Number(projectId) }),
          unityRunnerApi.getTestMetricsCatalog().catch(() => null),
          unityRunnerApi.getDefaultTestScope().catch(() => null),
        ]);
        setMetricsCatalog(catalog);
        if (defaultScope?.default_scope) {
          setTestScope(fillScopeKeys(defaultScope.default_scope, 'global_default'));
        }
        setProject(projectData);
        setSessions(sessionsData.items || []);
        setEngines(engineData);
        setScenes(sceneData);

        const defaultEngine = engineData.find((item) => item.is_default && item.enabled) || engineData[0];
        const defaultScene =
          sceneData.find((item) => item.is_default && item.enabled) ||
          sceneData.find((item) => item.enabled) ||
          sceneData[0];
        form.setFieldsValue({
          unity_engine_id: defaultEngine?.id,
          scene_resource_id: defaultScene?.id,
          collect_interval: 1,
          frame_rate_duration_seconds: 30,
          metrics_duration_seconds: 30,
          batchmode: false,
          ensure_plugin: true,
        });

        try {
          const activeBatch = await unityBatchesApi.getActive(Number(projectId));
          if (activeBatch.data.item) {
            setActiveBatchDetail(activeBatch.data.item);
            setShowUnityConfig(false);
            setRunMode('multi');
          } else {
            const runningSession = findActiveSingleSceneSession(sessionsData.items || []);
            if (runningSession) {
              setActiveRun(createActiveRunFromSession(runningSession));
              setActiveRunScope(inferScopeFromSessionConfig(runningSession.config || {}));
              setShowUnityConfig(false);
              setRunMode('single');
            }
          }
        } catch {
          const runningSession = findActiveSingleSceneSession(sessionsData.items || []);
          if (runningSession) {
            setActiveRun(createActiveRunFromSession(runningSession));
            setActiveRunScope(inferScopeFromSessionConfig(runningSession.config || {}));
            setShowUnityConfig(false);
            setRunMode('single');
          }
        }
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

      const runningSession = findActiveSingleSceneSession(sessions);

      return runningSession ? createActiveRunFromSession(runningSession) : null;
    });
  }, [sessions]);

  useEffect(() => {
    if (!activeRun || TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;
    setShowUnityConfig(false);
    setRunMode('single');
    setActiveRunScope(inferScopeFromSessionConfig(
      sessions.find((session) => session.id === activeRun.sessionId)?.config || {},
    ));
  }, [activeRun, sessions]);

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
      Promise.all([
        loadSessions(),
        activeRun.taskId ? unityRunnerApi.getTaskLogs(activeRun.taskId, { tail_lines: 400 }) : Promise.resolve(null),
      ])
        .then(([, logs]) => {
          if (!logs) return;
          setTaskLogs(logs.lines || []);
          setTaskError(logs.task.error_message || null);
          if (logs.session) {
            setActiveRun((current) => current ? createActiveRunFromSession(logs.session!, current) : current);
          }
        })
        .catch(() => {
          message.warning('刷新 Unity 任务状态失败');
        });
    }, 3000);

    return () => window.clearInterval(refreshTimer);
  }, [activeRun, loadSessions]);

  useEffect(() => {
    const logElement = liveLogRef.current;
    if (!logElement) return;
    logElement.scrollTop = logElement.scrollHeight;
  }, [taskLogs]);

  const activeBatchParentTaskId = activeBatchDetail?.parent_task?.id ?? null;
  const activeBatchTerminal = activeBatchDetail
    ? TERMINAL_BATCH_STATUSES.has(activeBatchDetail.batch.status)
    : true;

  useEffect(() => {
    if (!activeBatchParentTaskId || activeBatchTerminal) return;
    const taskId = activeBatchParentTaskId;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setRealtimeConnection('connecting');
      socket = createUnityProgressWebSocket(taskId);
      socket.onopen = () => setRealtimeConnection('live');
      socket.onmessage = (event) => {
        try {
          const progress = JSON.parse(event.data) as UnityRealtimeProgress;
          if (progress.type === 'unity_progress') {
            setRealtimeProgress(progress);
          }
        } catch {
          // ignore malformed payloads
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        setRealtimeConnection('polling');
        reconnectTimer = window.setTimeout(connect, 2000);
      };
      socket.onerror = () => setRealtimeConnection('polling');
    };
    connect();

    const fetchLatestProgress = () => {
      unityRunnerApi.getLatestProgress(taskId)
        .then((progress) => {
          if (progress) setRealtimeProgress(progress);
        })
        .catch(() => {
          if (socket?.readyState !== WebSocket.OPEN) setRealtimeConnection('polling');
        });
    };
    fetchLatestProgress();
    const pollingTimer = window.setInterval(fetchLatestProgress, 1000);

    return () => {
      disposed = true;
      window.clearInterval(pollingTimer);
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [activeBatchParentTaskId, activeBatchTerminal]);

  useEffect(() => {
    if (!activeBatchParentTaskId || activeBatchTerminal) return;

    const refreshTimer = window.setInterval(() => {
      Promise.all([
        unityBatchesApi.get(activeBatchDetail!.batch.id),
        unityRunnerApi.getTaskLogs(activeBatchParentTaskId, { tail_lines: 400 }),
        loadSessions(),
      ])
        .then(([batchRes, logs]) => {
          setActiveBatchDetail(batchRes.data);
          setTaskLogs(logs.lines || []);
          setTaskError(logs.task.error_message || null);
          if (batchRes.data.batch.status === 'awaiting_user_decision') {
            setDecisionModalOpen(true);
          }
        })
        .catch(() => {
          message.warning('刷新多场景编排状态失败');
        });
    }, 3000);

    return () => window.clearInterval(refreshTimer);
  }, [activeBatchDetail, activeBatchParentTaskId, activeBatchTerminal, loadSessions]);

  useEffect(() => {
    if (!activeRun?.taskId || TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;
    const taskId = activeRun.taskId;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setRealtimeConnection('connecting');
      socket = createUnityProgressWebSocket(taskId);
      socket.onopen = () => setRealtimeConnection('live');
      socket.onmessage = (event) => {
        try {
          const progress = JSON.parse(event.data) as UnityRealtimeProgress;
          if (progress.type === 'unity_progress')
            setRealtimeProgress(progress);
        } catch {
          // HTTP fallback below continues refreshing if a message is malformed.
        }
      };
      socket.onclose = () => {
        if (disposed) return;
        setRealtimeConnection('polling');
        reconnectTimer = window.setTimeout(connect, 2000);
      };
      socket.onerror = () => setRealtimeConnection('polling');
    };
    connect();

    const fetchLatestProgress = () => {
      unityRunnerApi.getLatestProgress(taskId)
        .then((progress) => {
          if (progress) setRealtimeProgress(progress);
        })
        .catch(() => {
          if (socket?.readyState !== WebSocket.OPEN)
            setRealtimeConnection('polling');
        });
    };
    fetchLatestProgress();
    const pollingTimer = window.setInterval(fetchLatestProgress, 1000);

    return () => {
      disposed = true;
      window.clearInterval(pollingTimer);
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [activeRun?.status, activeRun?.taskId]);

  useEffect(() => {
    const taskId = activeRun?.taskId;
    if (!taskId || !activeRun || TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;

    if (collectionNotifyRef.current.taskId !== taskId) {
      collectionNotifyRef.current = { taskId, started: false, ended: false };
    }

    if (!realtimeProgress) return;

    if (isCollectingProgress(realtimeProgress) && !collectionNotifyRef.current.started) {
      collectionNotifyRef.current.started = true;
      notification.success({
        message: '采集已开始',
        description: `${realtimeProgress.phase_label}，Unity 已开始上报实时数据。`,
        placement: 'topRight',
        duration: 5,
      });
    }

    if (
      collectionNotifyRef.current.started &&
      !collectionNotifyRef.current.ended &&
      isUploadingProgress(realtimeProgress)
    ) {
      collectionNotifyRef.current.ended = true;
      notification.info({
        message: '采集已结束',
        description: `共采集 ${realtimeProgress.sample_count} 个样本，正在上传结果…`,
        placement: 'topRight',
        duration: 6,
      });
    }
  }, [activeRun, activeRun?.taskId, activeRun?.status, realtimeProgress]);

  useEffect(() => {
    if (!activeRun?.taskId) return;
    if (!TERMINAL_SESSION_STATUSES.has(activeRun.status)) return;
    if (collectionNotifyRef.current.taskId !== activeRun.taskId) return;
    if (!collectionNotifyRef.current.started || collectionNotifyRef.current.ended) return;

    collectionNotifyRef.current.ended = true;
    if (activeRun.status === 'completed') {
      notification.success({
        message: '采集已结束',
        description: `会话 ${activeRun.sessionName} 已完成，可前往分析页查看结果。`,
        placement: 'topRight',
        duration: 6,
      });
      return;
    }

    if (activeRun.status === 'cancelled') {
      notification.warning({
        message: '采集已取消',
        description: '测试任务已被手动停止。',
        placement: 'topRight',
        duration: 6,
      });
      return;
    }

    notification.error({
      message: '采集失败',
      description: taskError || '请查看 Unity 实时日志了解详情。',
      placement: 'topRight',
      duration: 8,
    });
  }, [activeRun, activeRun?.status, activeRun?.sessionName, activeRun?.taskId, taskError]);

  useEffect(() => {
    if (!activeBatchDetail) return;
    const { batch, items } = activeBatchDetail;
    const currentIndex = realtimeProgress?.scene_index ?? batch.current_scene_index;
    const currentItem = items.find((item) => item.scene_index === currentIndex);
    const tracker = batchNotifyRef.current;

    if (tracker.batchId !== batch.id) {
      batchNotifyRef.current = {
        batchId: batch.id,
        sceneIndex: currentIndex,
        ended: TERMINAL_BATCH_STATUSES.has(batch.status),
      };
      if (!TERMINAL_BATCH_STATUSES.has(batch.status)) {
        notification.success({
          message: '多场景测试已开始',
          description: `编排 #${batch.id}，共 ${batch.scene_total} 个场景，当前执行 ${currentItem?.scene_display_name || `场景 ${currentIndex + 1}`}。`,
          placement: 'topRight',
          duration: 6,
        });
      }
      return;
    }

    if (
      !TERMINAL_BATCH_STATUSES.has(batch.status) &&
      tracker.sceneIndex !== null &&
      currentIndex !== tracker.sceneIndex
    ) {
      batchNotifyRef.current.sceneIndex = currentIndex;
      notification.info({
        message: '正在切换测试场景',
        description: `即将执行场景 ${currentIndex + 1}/${batch.scene_total}：${currentItem?.scene_display_name || '-'}`,
        placement: 'topRight',
        duration: 6,
      });
    }

    if (TERMINAL_BATCH_STATUSES.has(batch.status) && !tracker.ended) {
      batchNotifyRef.current.ended = true;
      const completedCount = items.filter((item) => item.status === 'completed').length;
      const description = `编排 #${batch.id} 已结束，完成 ${completedCount}/${batch.scene_total} 个场景。`;
      if (batch.status === 'completed') {
        notification.success({ message: '多场景测试已完成', description, placement: 'topRight', duration: 7 });
      } else if (batch.status === 'cancelled') {
        notification.warning({ message: '多场景测试已终止', description, placement: 'topRight', duration: 7 });
      } else {
        notification.error({ message: '多场景测试已结束', description, placement: 'topRight', duration: 8 });
      }
    }
  }, [activeBatchDetail, realtimeProgress?.scene_index]);

  useEffect(() => {
    if (activeRun?.status === 'completed') {
      setResultSessionId(activeRun.sessionId);
    }
  }, [activeRun?.sessionId, activeRun?.status]);

  const handleStartUnityTest = async (values: {
    unity_engine_id: string;
    scene_resource_id: string;
    collect_interval: number;
    frame_rate_duration_seconds: number;
    metrics_duration_seconds: number;
    batchmode?: boolean;
    ensure_plugin?: boolean;
  }) => {
    if (!projectId) return;
    if (!hasAnyEnabledLeaf(testScope)) {
      message.error('请至少选择一个测试指标');
      return;
    }
    setLaunching(true);
    try {
      const result = await unityRunnerApi.startTest({
        project_id: Number(projectId),
        unity_engine_id: values.unity_engine_id,
        scene_resource_id: values.scene_resource_id,
        test_scope: { ...testScope, source: 'single_run_override' },
        collect_interval: values.collect_interval,
        frame_rate_duration_seconds: values.frame_rate_duration_seconds,
        metrics_duration_seconds: values.metrics_duration_seconds,
        batchmode: Boolean(values.batchmode),
        ensure_plugin: values.ensure_plugin !== false,
        quality_checks: {
          lighting: Boolean(testScope.quality_categories.lighting),
          materials: Boolean(testScope.quality_categories.materials),
          post_processing: Boolean(testScope.quality_categories.post_processing),
          physics: Boolean(testScope.quality_categories.physics),
        },
      });
      const sessionScope = inferScopeFromSessionConfig(result.session.config || {});
      setActiveRunScope(sessionScope);
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
      collectionNotifyRef.current = { taskId: result.task.id, started: false, ended: false };
      setShowUnityConfig(false);
      setTaskLogs([]);
      setTaskError(null);
      setRealtimeProgress(null);
      setRealtimeConnection('connecting');
      setResultSessionId(null);
      setActiveTab('unity');
      setNow(Date.now());
      message.success(`Unity 已启动，任务 ${result.task.id}，会话 ${result.session.name}`);
      await loadSessions();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '启动 Unity 测试失败');
    } finally {
      setLaunching(false);
    }
  };

  const handleStartMultiSceneBatch = async () => {
    if (!projectId) return;
    setTaskError(null);
    let values;
    try {
      values = await form.validateFields(['unity_engine_id']);
    } catch {
      message.error('请先选择可用的 Unity 引擎');
      return;
    }
    if (sceneDrafts.length < 2) {
      message.error('多场景编排至少需要 2 个场景');
      return;
    }
    if (new Set(sceneDrafts.map((item) => item.projectPath)).size > 1) {
      message.error('所有场景必须属于同一 Unity 工程');
      return;
    }
    if (sceneDrafts.some((item) => !hasAnyEnabledLeaf(item.testScope))) {
      message.error('每个场景至少选择一个测试指标');
      return;
    }
    setLaunching(true);
    try {
      const result = await unityBatchesApi.start({
        project_id: Number(projectId),
        unity_engine_id: values.unity_engine_id,
        batchmode: Boolean(values.batchmode),
        ensure_plugin: values.ensure_plugin !== false,
        scenes: sceneDrafts.map((item) => ({
          scene_resource_id: item.sceneResourceId,
          test_scope: { ...item.testScope, source: 'batch_scene_override' },
          collect_interval: item.collectInterval,
          frame_rate_duration_seconds: item.frameRateDurationSeconds,
          metrics_duration_seconds: item.metricsDurationSeconds,
        })),
      });
      setActiveBatchDetail(result.data);
      batchNotifyRef.current = { batchId: null, sceneIndex: null, ended: false };
      setShowUnityConfig(false);
      setTaskLogs([]);
      setTaskError(null);
      setRealtimeProgress(null);
      setRealtimeConnection('connecting');
      setActiveTab('unity');
      message.success(`多场景编排已启动，批次 ${result.data.batch.id}`);
      await loadSessions();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '启动多场景编排失败';
      setTaskError(errorMessage);
      message.error(errorMessage);
    } finally {
      setLaunching(false);
    }
  };

  const handleStopBatch = async () => {
    if (!activeBatchDetail) return;
    setStopping(true);
    try {
      const result = await unityBatchesApi.stop(activeBatchDetail.batch.id);
      setActiveBatchDetail(result.data);
      message.success('多场景编排已终止');
      await loadSessions();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '终止多场景编排失败');
    } finally {
      setStopping(false);
    }
  };

  const handleBatchDecision = async (action: 'retry' | 'skip' | 'abort') => {
    if (!activeBatchDetail) return;
    const waitingItem = activeBatchDetail.items.find(
      (item) => item.status === 'awaiting_user_decision',
    );
    if (!waitingItem) {
      message.error('未找到待处理的场景项');
      return;
    }
    setDecisionSubmitting(true);
    try {
      const result = await unityBatchesApi.applyDecision(activeBatchDetail.batch.id, {
        action,
        expected_item_id: waitingItem.id,
        expected_scene_index: waitingItem.scene_index,
        decision_version: activeBatchDetail.batch.decision_version,
      });
      setActiveBatchDetail(result.data);
      setDecisionModalOpen(false);
      message.success(action === 'abort' ? '整批已终止' : action === 'skip' ? '已跳过当前场景' : '已重试当前场景');
      await loadSessions();
    } catch (error) {
      try {
        const refreshed = await unityBatchesApi.get(activeBatchDetail.batch.id);
        setActiveBatchDetail(refreshed.data);
      } catch {
        // ignore refresh failure
      }
      message.error(error instanceof Error ? error.message : '提交决策失败');
    } finally {
      setDecisionSubmitting(false);
    }
  };

  const handleRestartUnityTest = async () => {
    setShowUnityConfig(true);
    setActiveRun(null);
    setActiveRunScope(null);
    setActiveBatchDetail(null);
    try {
      const defaultScope = await unityRunnerApi.getDefaultTestScope();
      setTestScope(fillScopeKeys(defaultScope.default_scope, 'global_default'));
    } catch {
      setTestScope(buildBuiltinDefaultScope('global_default'));
    }
    setRealtimeProgress(null);
    setTaskLogs([]);
    setTaskError(null);
    setResultSessionId(null);
    setRealtimeConnection('connecting');
    collectionNotifyRef.current = { taskId: null, started: false, ended: false };
    batchNotifyRef.current = { batchId: null, sceneIndex: null, ended: false };
  };

  const handleStopUnityTest = async () => {
    if (!activeRun?.taskId) return;
    setStopping(true);
    try {
      const result = await unityRunnerApi.stopTest(activeRun.taskId);
      if (result.session) {
        setActiveRun(createActiveRunFromSession(result.session, activeRun));
      }
      message.success('Unity 测试已停止');
      await loadSessions();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '停止 Unity 测试失败');
    } finally {
      setStopping(false);
    }
  };

  const activeEstimate = activeRun ? getRunProgressDisplay(activeRun, now, realtimeProgress) : null;
  const collectionStep = activeRun ? getCollectionStepState(activeRun, realtimeProgress) : null;
  const monitorScope = activeRunScope;
  const showUnitySession = !showUnityConfig && Boolean(
    launching || activeRun || (activeBatchDetail && !activeBatchTerminal),
  );
  const defaultDurations = {
    collectInterval: form.getFieldValue('collect_interval') ?? 1,
    frameRateDurationSeconds: form.getFieldValue('frame_rate_duration_seconds') ?? 30,
    metricsDurationSeconds: form.getFieldValue('metrics_duration_seconds') ?? 30,
  };

  if (loading) {
    return <Spin size="large" style={{ display: 'flex', justifyContent: 'center', marginTop: 80 }} />;
  }

  if (!project) {
    return <div style={{ textAlign: 'center', marginTop: 80, color: '#999' }}>项目不存在</div>;
  }

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

      <Card style={{ marginBottom: 24 }} className="project-test-card">
        <Tabs
          activeKey={activeTab}
          onChange={handleTabChange}
          className="project-test-tabs"
          items={[
            {
              key: 'unity',
              label: 'Unity 本地测试',
              children: (
                <>
        {showUnityConfig && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="从后端已登记的 Unity 引擎和场景资源启动测试，Unity 插件会把采集结果上传并绑定到本项目的新会话。"
          />
        )}

        {showUnitySession && activeBatchDetail && !activeBatchTerminal && (
          <MultiSceneBatchMonitor
            batchDetail={activeBatchDetail}
            realtime={realtimeProgress}
            connection={realtimeConnection}
            taskLogs={taskLogs}
            stopping={stopping}
            onStop={handleStopBatch}
            onOpenDecision={() => setDecisionModalOpen(true)}
          />
        )}

        {showUnitySession && activeRun && activeEstimate && !activeBatchDetail && (
          <div className="unity-monitor">
            <div className="unity-monitor-header">
              <div>
                <div className="unity-monitor-title">
                  <ThunderboltOutlined className="unity-monitor-title-icon" />
                  {TERMINAL_SESSION_STATUSES.has(activeRun.status) ? '最近一次采集' : '采集进行中'}
                  <Tag color="blue">{activeEstimate.phase}</Tag>
                  <Tag color={realtimeConnection === 'live' ? 'success' : realtimeConnection === 'polling' ? 'warning' : 'default'}>
                    {realtimeConnection === 'live' ? 'WebSocket 实时连接' : realtimeConnection === 'polling' ? '实时轮询连接' : '正在连接实时数据'}
                  </Tag>
                </div>
                <div className="unity-monitor-subtitle">
                  会话 {activeRun.sessionName} · 任务 {activeRun.taskId || '-'} · 进程 {activeRun.processId || '-'}
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
                  onClick={() =>
                    navigate(`/analysis?sessionId=${activeRun.sessionId}&projectId=${project.id}`, {
                      state: { returnTo: `/projects/${project.id}?tab=unity` },
                    })
                  }
                >
                  分析
                </Button>
                {!TERMINAL_SESSION_STATUSES.has(activeRun.status) && activeRun.taskId && (
                  <Button danger size="small" icon={<StopOutlined />} loading={stopping} onClick={handleStopUnityTest}>
                    停止
                  </Button>
                )}
                {TERMINAL_SESSION_STATUSES.has(activeRun.status) && (
                  <Button type="primary" size="small" icon={<PlayCircleOutlined />} onClick={handleRestartUnityTest}>
                    再次开始测试
                  </Button>
                )}
              </Space>
            </div>

            <TestScopeBanner scope={activeRunScope} summary={realtimeProgress?.test_scope_summary} />

            <div className="unity-monitor-body">
              <div className="unity-monitor-summary">
                <div className="unity-progress-row">
                  <Progress
                    percent={activeEstimate.percent}
                    status={activeEstimate.progressStatus}
                    strokeWidth={11}
                    showInfo={false}
                    trailColor="#edf1f5"
                    strokeColor={{ '0%': '#1677ff', '100%': '#52c41a' }}
                  />
                  <strong>{activeEstimate.percent}%</strong>
                </div>

                <div className="unity-core-metrics">
                  <MetricTile
                    label="FPS"
                    skipped={monitorScope ? !isMetricEnabled(monitorScope, 'frame_rate') : false}
                    pending={Boolean(monitorScope && isMetricEnabled(monitorScope, 'frame_rate') && !realtimeProgress)}
                    value={`${(realtimeProgress?.fps ?? 0).toFixed(1)} fps`}
                    accent="#3b82f6"
                  />
                  <MetricTile
                    label="CPU"
                    skipped={monitorScope ? !isMetricEnabled(monitorScope, 'cpu') : false}
                    pending={Boolean(monitorScope && isMetricEnabled(monitorScope, 'cpu') && !realtimeProgress)}
                    value={`${(realtimeProgress?.cpu_usage_percent ?? 0).toFixed(1)} %`}
                    accent="#f59e0b"
                  />
                  <MetricTile
                    label="GPU"
                    skipped={monitorScope ? !isMetricEnabled(monitorScope, 'gpu') : false}
                    pending={Boolean(monitorScope && isMetricEnabled(monitorScope, 'gpu') && !realtimeProgress)}
                    value={`${(realtimeProgress?.gpu_usage_percent ?? 0).toFixed(1)} %`}
                    accent="#10b981"
                  />
                  <MetricTile
                    label="内存"
                    skipped={monitorScope ? !isMetricEnabled(monitorScope, 'memory') : false}
                    pending={Boolean(monitorScope && isMetricEnabled(monitorScope, 'memory') && !realtimeProgress)}
                    value={`${(realtimeProgress?.memory_mb ?? 0).toFixed(0)} MB`}
                  />
                  <MetricTile label="样本数" value={realtimeProgress?.sample_count ?? 0} pending={!realtimeProgress} />
                  <MetricTile label="阶段" value={activeEstimate.phase} />
                </div>

                <div className="unity-run-meta">
                  <span>已运行：{activeEstimate.elapsedText}</span>
                  <span>剩余：{activeEstimate.remainingText}</span>
                  <span>实时更新：{realtimeProgress?.received_at ? formatDateTime(realtimeProgress.received_at) : '等待 Unity 上报'}</span>
                  <span>{activeEstimate.detail}</span>
                </div>

                <Steps
                  className="unity-phase-steps"
                  size="small"
                  current={collectionStep?.current ?? 0}
                  status={collectionStep?.status}
                  items={[
                    { title: '启动 Unity', description: '冷启动编辑器' },
                    {
                      title: '帧率采集',
                      description: `${activeRun.frameRateDurationSeconds}s`,
                    },
                    {
                      title: '指标采集',
                      description: `${activeRun.metricsDurationSeconds}s`,
                    },
                    { title: '上传结果', description: '同步到平台' },
                    { title: '完成', description: '可查看分析' },
                  ]}
                />
              </div>

              <div className="unity-monitor-panels">
                <div className="unity-monitor-side">
                  <div className="unity-side-panel">
                    <div className="unity-side-panel-title">运行详情</div>
                    <div className="unity-side-panel-body">
                      {realtimeProgress ? (
                        <Descriptions
                          className="unity-detail-metrics unity-detail-metrics--embedded"
                          bordered
                          size="small"
                          column={2}
                        >
                          <Descriptions.Item label="图形设备">{realtimeProgress.graphics_device_name || '-'}</Descriptions.Item>
                          <Descriptions.Item label="渲染管线">{realtimeProgress.render_pipeline || '-'}</Descriptions.Item>
                          <Descriptions.Item label="设备型号">{realtimeProgress.device_model || '-'}</Descriptions.Item>
                          <Descriptions.Item label="操作系统">{realtimeProgress.operating_system || '-'}</Descriptions.Item>
                          <Descriptions.Item label="Unity 版本">{realtimeProgress.unity_version || '-'}</Descriptions.Item>
                          <Descriptions.Item label="分辨率">{realtimeProgress.screen_resolution || '-'}</Descriptions.Item>
                          <Descriptions.Item label="帧时间">{realtimeProgress.frame_time_ms.toFixed(2)} ms</Descriptions.Item>
                          <Descriptions.Item label="原始帧时间">{realtimeProgress.raw_frame_time_ms.toFixed(2)} ms</Descriptions.Item>
                          <Descriptions.Item label="Draw Calls">{realtimeProgress.draw_calls}</Descriptions.Item>
                          <Descriptions.Item label="三角形">{realtimeProgress.triangles.toLocaleString()}</Descriptions.Item>
                          <Descriptions.Item label="顶点">{realtimeProgress.vertices.toLocaleString()}</Descriptions.Item>
                          <Descriptions.Item label="托管内存">{realtimeProgress.managed_memory_mb.toFixed(1)} MB</Descriptions.Item>
                          <Descriptions.Item label="显存">{realtimeProgress.graphics_memory_mb.toFixed(1)} MB</Descriptions.Item>
                          <Descriptions.Item label="系统内存">{realtimeProgress.system_memory_mb.toFixed(1)} MB</Descriptions.Item>
                          <Descriptions.Item label="材质/唯一">{realtimeProgress.material_count} / {realtimeProgress.unique_material_count}</Descriptions.Item>
                          <Descriptions.Item label="透明材质">{realtimeProgress.transparent_material_count}</Descriptions.Item>
                          <Descriptions.Item label="活动/实时光源">{realtimeProgress.active_light_count} / {realtimeProgress.realtime_light_count}</Descriptions.Item>
                          <Descriptions.Item label="阴影投射器">{realtimeProgress.shadow_caster_count}</Descriptions.Item>
                          <Descriptions.Item label="反射探针">{realtimeProgress.reflection_probe_count}</Descriptions.Item>
                          <Descriptions.Item label="后处理/RT">{realtimeProgress.post_process_volume_count} / {realtimeProgress.render_texture_count}</Descriptions.Item>
                          <Descriptions.Item label="刚体/碰撞体">{realtimeProgress.rigidbody_count} / {realtimeProgress.collider_count}</Descriptions.Item>
                          <Descriptions.Item label="XR" span={2}>
                            {realtimeProgress.is_xr_active ? realtimeProgress.xr_device_name || '活动' : '未活动'}
                          </Descriptions.Item>
                        </Descriptions>
                      ) : (
                        <Alert
                          className="unity-waiting-panel"
                          type="info"
                          showIcon
                          message="等待 Unity 就绪"
                          description="编辑器启动、场景加载与插件初始化完成后，将自动开始采集并显示详细指标。"
                        />
                      )}
                    </div>
                  </div>
                </div>

                <div className="unity-live-log">
                  <div className="unity-live-log-title">
                    <span>实时日志</span>
                    <Tag color={realtimeConnection === 'live' ? 'green' : realtimeConnection === 'polling' ? 'orange' : 'default'}>
                      {realtimeConnection === 'live' ? 'LIVE' : realtimeConnection === 'polling' ? 'POLL' : 'WAIT'}
                    </Tag>
                  </div>
                  <pre ref={liveLogRef}>
                    {taskLogs.length > 0 ? taskLogs.slice(-80).join('\n') : '等待 Unity 日志输出...'}
                  </pre>
                </div>
              </div>
            </div>

            {taskError && (
              <Alert
                type="error"
                showIcon
                message="Unity 自动化执行失败"
                description={taskError}
                style={{ marginTop: 14 }}
              />
            )}

          </div>
        )}

        {showUnitySession && launching && !activeRun && (
          <div className="unity-launching-placeholder">
            <Spin size="large" tip="正在启动 Unity…" />
          </div>
        )}

        {showUnityConfig && (
          <>
            {launching && (
              <Alert
                type="info"
                showIcon
                message="正在启动 Unity"
                description="如果当前 Unity Editor 中的采集插件源码有更新，启动可能需要等待重新编译，最长约 60 秒。"
                style={{ marginBottom: 16 }}
              />
            )}
            {taskError && (
              <Alert
                type="error"
                showIcon
                closable
                message="Unity 启动失败"
                description={taskError}
                onClose={() => setTaskError(null)}
                style={{ marginBottom: 16 }}
              />
            )}
            <div className="unity-config-heading">
              <Typography.Title level={4}>测试配置</Typography.Title>
              <Typography.Text type="secondary">在下方 Tab 中选择单场景或多场景连续测试模式。</Typography.Text>
            </div>
            <Form
              form={form}
              layout="vertical"
              onFinish={runMode === 'single' ? handleStartUnityTest : undefined}
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

              <Tabs
                activeKey={runMode}
                onChange={(key) => setRunMode(key as 'single' | 'multi')}
                className="unity-run-mode-tabs"
                items={[
                  {
                    key: 'single',
                    label: '单场景',
                    children: (
                      <>
                        <Form.Item
                          name="scene_resource_id"
                          label="测试场景"
                          extra="场景列表由系统设置中的 Unity 项目目录自动扫描生成。"
                          rules={[{ required: true, message: '请选择测试场景' }]}
                        >
                          <Select
                            className="unity-scene-select"
                            placeholder={scenes.length > 0 ? '请选择测试场景' : '请先在系统设置中配置 Unity 项目目录'}
                            showSearch
                            optionLabelProp="label"
                            filterOption={(input, option) => {
                              const scene = scenes.find((item) => item.id === option?.value);
                              if (!scene) return false;
                              const keyword = input.trim().toLowerCase();
                              const haystack = `${scene.name} ${scene.scene_path}`.toLowerCase();
                              return haystack.includes(keyword);
                            }}
                          >
                            {scenes.map((scene) => (
                              <Option
                                key={scene.id}
                                value={scene.id}
                                label={scene.name}
                                disabled={!scene.enabled || !scene.exists}
                              >
                                <div className="unity-scene-option">
                                  <div className="unity-scene-option__name">{scene.name}</div>
                                  <div className="unity-scene-option__path">{scene.scene_path}</div>
                                </div>
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

                        <Form.Item label="测试指标" required>
                          <MetricScopeSelector value={testScope} catalog={metricsCatalog} onChange={setTestScope} />
                        </Form.Item>
                      </>
                    ),
                  },
                  {
                    key: 'multi',
                    label: '多场景连续',
                    children: (
                      <MultiSceneOrchestrationPanel
                        scenes={scenes}
                        defaultScope={testScope}
                        defaultDurations={defaultDurations}
                        drafts={sceneDrafts}
                        onChange={setSceneDrafts}
                        metricsCatalog={metricsCatalog}
                      />
                    ),
                  },
                ]}
              />

              <Space size="large" wrap>
                <Form.Item name="ensure_plugin" valuePropName="checked">
                  <Checkbox>缺少插件时自动写入 manifest</Checkbox>
                </Form.Item>
                <Form.Item name="batchmode" valuePropName="checked">
                  <Checkbox>使用 BatchMode</Checkbox>
                </Form.Item>
              </Space>

              {runMode === 'single' ? (
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<PlayCircleOutlined />}
                  loading={launching}
                >
                  启动 Unity 测试
                </Button>
              ) : (
                <Button
                  type="primary"
                  htmlType="button"
                  icon={<PlayCircleOutlined />}
                  loading={launching}
                  onClick={handleStartMultiSceneBatch}
                >
                  启动多场景编排
                </Button>
              )}
            </Form>
          </>
        )}

        {showUnitySession && activeBatchDetail && activeBatchTerminal && (
          <div style={{ marginTop: 16 }}>
            <Space style={{ marginBottom: 12 }}>
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRestartUnityTest}>
                再次开始测试
              </Button>
            </Space>
            <MultiSceneBatchResults items={activeBatchDetail.items} />
          </div>
        )}

        {showUnitySession && resultSessionId && activeRun?.status === 'completed' && !activeBatchDetail && (
          <div className="unity-result-section">
            <div className="unity-result-heading">
              <Typography.Title level={4}>测试结果</Typography.Title>
              <Typography.Text type="secondary">
                会话 {activeRun.sessionName} 已完成，以下为性能分析图表
              </Typography.Text>
            </div>
            <SessionResultPanel sessionId={resultSessionId} />
          </div>
        )}
                </>
              ),
            },
            {
              key: 'history',
              label: '历史测试记录',
              children: (
                <>
                  <div className="history-tab-toolbar">
                    <Typography.Text type="secondary">
                      查看本项目关联的全部测试会话，可跳转完整性能分析页
                    </Typography.Text>
                    <Button icon={<ReloadOutlined />} onClick={loadSessions}>
                      刷新会话
                    </Button>
                  </div>
                  <SessionHistoryList
                    sessions={sessions}
                    historyView={historyView}
                    onHistoryViewChange={handleHistoryViewChange}
                    onAnalyze={(sessionId, context) => {
                      const session = sessions.find((item) => item.id === sessionId);
                      const returnView = context?.historyView ?? (session ? sessionHistoryView(session) : historyView);
                      navigate(`/analysis?sessionId=${sessionId}&projectId=${project.id}`, {
                        state: { returnTo: buildProjectHistoryReturnPath(project.id, returnView) },
                      });
                    }}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="场景执行失败"
        open={decisionModalOpen && Boolean(activeBatchDetail)}
        onCancel={() => setDecisionModalOpen(false)}
        footer={null}
        destroyOnHidden
      >
        {activeBatchDetail && (
          <>
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message={`场景 ${activeBatchDetail.batch.current_scene_index + 1}/${activeBatchDetail.batch.scene_total} 执行失败`}
              description={
                activeBatchDetail.items.find((item) => item.scene_index === activeBatchDetail.batch.current_scene_index)
                  ?.error_message || '请选择后续操作'
              }
            />
            <Space>
              {activeBatchDetail.allowed_actions.includes('retry') && (
                <Button type="primary" loading={decisionSubmitting} onClick={() => handleBatchDecision('retry')}>
                  重试当前场景
                </Button>
              )}
              {activeBatchDetail.allowed_actions.includes('skip') && (
                <Button loading={decisionSubmitting} onClick={() => handleBatchDecision('skip')}>
                  跳过并继续
                </Button>
              )}
              {activeBatchDetail.allowed_actions.includes('abort') && (
                <Button danger loading={decisionSubmitting} onClick={() => handleBatchDecision('abort')}>
                  终止整批
                </Button>
              )}
            </Space>
          </>
        )}
      </Modal>
    </div>
  );
};

export default ProjectDetail;
