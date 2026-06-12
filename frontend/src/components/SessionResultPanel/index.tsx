import React, { useEffect, useMemo, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Tabs,
  Spin,
  message,
} from 'antd';
import RenderQualityPanel from '@/components/RenderQualityPanel';
import SessionDeviceInfoPanel from '@/components/SessionDeviceInfoPanel';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { analysisApi, type FullReport } from '@/api/analysis';
import { sessionsApi } from '@/api/sessions';
import {
  buildFrameQualityPieData,
  buildFrameTimeHistogram,
  buildSampleChartData,
  type SampleChartPoint,
} from '@/lib/sampleCharts';
import './SessionResultPanel.css';

interface SessionResultPanelProps {
  sessionId: number;
}

const SessionResultPanel: React.FC<SessionResultPanelProps> = ({ sessionId }) => {
  const [loading, setLoading] = useState(true);
  const [fullReport, setFullReport] = useState<FullReport | null>(null);
  const [sampleChartData, setSampleChartData] = useState<SampleChartPoint[]>([]);
  const [frameTimeData, setFrameTimeData] = useState<Array<{ range: string; count: number }>>([]);
  const [pieData, setPieData] = useState<Array<{ name: string; value: number; color: string }>>([]);

  useEffect(() => {
    let disposed = false;

    const loadResult = async () => {
      setLoading(true);
      try {
        const [report, samples] = await Promise.all([
          analysisApi.getFullReport(sessionId),
          sessionsApi.getSamples(sessionId, { limit: 300 }),
        ]);
        if (disposed) return;
        setFullReport(report);
        setSampleChartData(buildSampleChartData(samples));
        setFrameTimeData(buildFrameTimeHistogram(samples));
        setPieData(buildFrameQualityPieData(samples));
      } catch {
        if (!disposed) {
          message.warning('未能加载测试结果，请稍后从历史记录查看');
          setFullReport(null);
          setSampleChartData([]);
          setFrameTimeData([]);
          setPieData([]);
        }
      } finally {
        if (!disposed) setLoading(false);
      }
    };

    loadResult();
    return () => {
      disposed = true;
    };
  }, [sessionId]);

  const fpsChartData = useMemo(
    () => sampleChartData.filter((item) => item.fps > 0).slice(0, 60),
    [sampleChartData],
  );
  const resourceChartData = useMemo(
    () => sampleChartData.slice(-60),
    [sampleChartData],
  );
  const drawCallChartData = useMemo(
    () => sampleChartData.slice(-60),
    [sampleChartData],
  );

  const renderQuality = fullReport?.render_quality_assessment;

  if (loading) {
    return (
      <div className="session-result-panel__loading">
        <Spin tip="正在加载测试结果..." />
      </div>
    );
  }

  if (!fullReport && sampleChartData.length === 0) {
    return (
      <Card>
        <div className="session-result-panel__empty">暂无测试结果数据</div>
      </Card>
    );
  }

  const sectionStatus = fullReport?.section_status;

  return (
    <div className="session-result-panel">
      <Row gutter={[16, 16]} className="session-result-panel__summary">
        <Col xs={24} sm={12} lg={6}>
          <Card className="session-result-panel__stat-card">
            <Statistic
              title="平均FPS"
              value={sectionStatus?.frame_rate === 'skipped' ? '跳过' : (fullReport?.fps_analysis?.mean ?? 0)}
              precision={sectionStatus?.frame_rate === 'skipped' ? undefined : 1}
              suffix={sectionStatus?.frame_rate === 'skipped' ? undefined : 'fps'}
              valueStyle={{ color: '#3b82f6' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="session-result-panel__stat-card">
            <Statistic
              title="P95帧时间"
              value={fullReport?.frame_time_analysis?.p95_ms ?? 0}
              precision={1}
              suffix="ms"
              valueStyle={{ color: '#f59e0b' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="session-result-panel__stat-card">
            <Statistic
              title="掉帧率"
              value={((fullReport?.stability_summary?.dropped_frame_rate ?? 0) * 100)}
              precision={1}
              suffix="%"
              valueStyle={{ color: '#ef4444' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="session-result-panel__stat-card">
            <Statistic
              title="长帧次数"
              value={fullReport?.stability_summary?.long_frame_count ?? 0}
              valueStyle={{ color: '#8b5cf6' }}
            />
          </Card>
        </Col>
      </Row>

      <Tabs
        defaultActiveKey="fps"
        className="session-result-panel__tabs"
        items={[
          {
            key: 'fps',
            label: 'FPS趋势',
            children: (
              <Card>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={fpsChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis domain={[0, 'auto']} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="fps" stroke="#3b82f6" name="FPS" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            ),
          },
          {
            key: 'frametime',
            label: '帧时间分布',
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} lg={16}>
                  <Card title="帧时间直方图">
                    <ResponsiveContainer width="100%" height={350}>
                      <BarChart data={frameTimeData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="range" />
                        <YAxis allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="count" fill="#3b82f6" name="帧数" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>
                </Col>
                <Col xs={24} lg={8}>
                  <Card title="帧质量分布">
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={100}
                          paddingAngle={4}
                          dataKey="value"
                        >
                          {pieData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'resources',
            label: '资源占用',
            children: (
              <Card>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={resourceChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis yAxisId="left" domain={[0, 100]} />
                    <YAxis yAxisId="right" orientation="right" domain={[0, 'auto']} />
                    <Tooltip />
                    <Legend />
                    <Line yAxisId="left" type="monotone" dataKey="cpu" stroke="#3b82f6" name="CPU (%)" strokeWidth={2} dot={false} />
                    <Line yAxisId="left" type="monotone" dataKey="gpu" stroke="#ef4444" name="GPU (%)" strokeWidth={2} dot={false} />
                    <Line yAxisId="right" type="monotone" dataKey="memory" stroke="#10b981" name="内存 (GB)" strokeWidth={2} dot={false} />
                    <Line yAxisId="right" type="monotone" dataKey="vram" stroke="#f59e0b" name="显存 (GB)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            ),
          },
          {
            key: 'drawcalls',
            label: 'Draw Calls',
            children: (
              <Card>
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={drawCallChartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis allowDecimals={false} domain={[0, 'auto']} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="drawCalls" stroke="#8b5cf6" name="Draw Calls" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Card>
            ),
          },
          {
            key: 'render-quality',
            label: '渲染质量',
            children: <RenderQualityPanel assessment={renderQuality} />,
          },
          {
            key: 'device-info',
            label: '设备信息',
            children: <SessionDeviceInfoPanel sessionInfo={fullReport?.session_info} />,
          },
        ]}
      />
    </div>
  );
};

export default SessionResultPanel;
