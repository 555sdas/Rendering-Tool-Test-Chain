import React, { useEffect, useMemo, useState } from 'react';
import { Button, Progress, Tag } from 'antd';
import { ExperimentOutlined, RightOutlined } from '@ant-design/icons';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  createUnityProgressWebSocket,
  unityRunnerApi,
  type ActiveUnityRunSummary,
  type UnityRealtimeProgress,
} from '@/api/unityRunner';
import './GlobalUnityProgress.css';

function formatRemaining(seconds: number): string {
  const safe = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return minutes > 0 ? `${minutes}分${rest}秒` : `${rest}秒`;
}

const GlobalUnityProgress: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<ActiveUnityRunSummary[]>([]);
  const [realtime, setRealtime] = useState<UnityRealtimeProgress | null>(null);
  const activeRun = runs[0] ?? null;
  const hiddenOnTestWorkspace = /^\/projects\/\d+\/?$/.test(location.pathname);

  useEffect(() => {
    let disposed = false;
    const refresh = () => {
      unityRunnerApi.listActiveRuns()
        .then((items) => {
          if (!disposed) setRuns(items);
        })
        .catch(() => {
          // Keep the previous summary during short backend interruptions.
        });
    };
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!activeRun?.task_id) {
      setRealtime(null);
      return;
    }
    const taskId = activeRun.task_id;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let disposed = false;
    const connect = () => {
      if (disposed) return;
      socket = createUnityProgressWebSocket(taskId);
      socket.onmessage = (event) => {
        try {
          const progress = JSON.parse(event.data) as UnityRealtimeProgress;
          if (progress.type === 'unity_progress') setRealtime(progress);
        } catch {
          // The active-run polling remains the fallback.
        }
      };
      socket.onclose = () => {
        if (!disposed) reconnectTimer = window.setTimeout(connect, 2000);
      };
    };
    setRealtime(null);
    connect();
    unityRunnerApi.getLatestProgress(taskId).then(setRealtime).catch(() => undefined);
    return () => {
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [activeRun?.task_id]);

  const display = useMemo(() => {
    if (!activeRun) return null;
    const progress = activeRun.run_mode === 'multi_scene'
      ? realtime?.overall_progress ?? activeRun.progress
      : realtime?.progress ?? activeRun.progress;
    return {
      percent: Math.min(100, Math.max(0, Math.round(progress * 100))),
      phase: realtime?.phase_label || activeRun.phase_label,
      remaining: realtime?.remaining_seconds ?? activeRun.remaining_seconds,
    };
  }, [activeRun, realtime]);

  if (!activeRun || !display || hiddenOnTestWorkspace) return null;

  return (
    <div className="global-unity-progress">
      <div className="global-unity-progress__summary">
        <ExperimentOutlined className="global-unity-progress__icon" />
        <div className="global-unity-progress__text">
          <strong>{activeRun.project_name || `项目 #${activeRun.project_id}`}</strong>
          <span>
            {activeRun.scene_name || 'Unity 测试'}
            {activeRun.run_mode === 'multi_scene'
              ? ` · 场景 ${activeRun.scene_index + 1}/${activeRun.scene_total}`
              : ''}
          </span>
        </div>
        <Tag color={activeRun.status === 'awaiting_user_decision' ? 'warning' : 'processing'}>
          {display.phase}
        </Tag>
      </div>
      <div className="global-unity-progress__bar">
        <Progress percent={display.percent} showInfo={false} strokeWidth={8} />
        <strong>{display.percent}%</strong>
        <span>剩余 {formatRemaining(display.remaining)}</span>
      </div>
      <Button
        type="link"
        size="small"
        icon={<RightOutlined />}
        iconPosition="end"
        onClick={() => navigate(`/projects/${activeRun.project_id}`)}
      >
        查看测试
      </Button>
    </div>
  );
};

export default GlobalUnityProgress;
