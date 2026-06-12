import React, { useEffect, useMemo, useState } from 'react';
import { Card, Row, Col, Statistic, Tabs, Table, Tag, message, Space, Button, Dropdown } from 'antd';
import type { MenuProps } from 'antd';
import RenderQualityPanel from '@/components/RenderQualityPanel';
import SessionDeviceInfoPanel from '@/components/SessionDeviceInfoPanel';
import MetricSkippedPlaceholder from '@/components/MetricSkippedPlaceholder';
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
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
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
import { analysisApi, type FullReport } from '@/api/analysis';
import { reportsApi, saveReportBlob, type ReportFormat } from '@/api/reports';
import { sessionsApi, type TestSession } from '@/api/sessions';
import { getSessionSceneLabel } from '@/lib/sessionScene';
import {
  buildFrameQualityPieData,
  buildFrameTimeHistogram,
  buildSampleChartData,
  type SampleChartPoint,
} from '@/lib/sampleCharts';

const { TabPane } = Tabs;

const comparisonData = [
  { metric: '平均FPS', quest3: 72, quest2: 65, pico4: 58 },
  { metric: 'P95帧时间(ms)', quest3: 13.9, quest2: 15.4, pico4: 17.2 },
  { metric: '掉帧率(%)', quest3: 2.1, quest2: 3.8, pico4: 5.2 },
  { metric: '长帧次数', quest3: 12, quest2: 28, pico4: 45 },
  { metric: 'CPU平均(%)', quest3: 52, quest2: 58, pico4: 62 },
  { metric: 'GPU平均(%)', quest3: 68, quest2: 75, pico4: 82 },
];

function buildReportFilename(sessionId: number, sessionName: string | null | undefined, format: ReportFormat) {
  const baseName = (sessionName || `session_${sessionId}_render_report`)
    .replace(/[\\/:*?"<>|]+/g, '_')
    .trim();
  return `${baseName || `session_${sessionId}_render_report`}.${format}`;
}

const Analysis: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const sessionIdParam = searchParams.get('sessionId');
  const projectIdParam = searchParams.get('projectId');
  const projectId = projectIdParam ? Number(projectIdParam) : undefined;
  const projectFilterId = projectId && Number.isFinite(projectId) ? projectId : undefined;
  const sessionId = sessionIdParam ? Number(sessionIdParam) : NaN;
  const returnTo =
    (location.state as { returnTo?: string } | null)?.returnTo ??
    (projectFilterId ? `/projects/${projectFilterId}` : '/projects');
  const [fullReport, setFullReport] = useState<FullReport | null>(null);
  const [currentSession, setCurrentSession] = useState<TestSession | null>(null);
  const [sampleChartData, setSampleChartData] = useState<SampleChartPoint[]>([]);
  const [frameTimeData, setFrameTimeData] = useState<Array<{ range: string; count: number }>>([]);
  const [pieData, setPieData] = useState<Array<{ name: string; value: number; color: string }>>([]);
  const [exportingReport, setExportingReport] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(sessionId)) {
      setFullReport(null);
      setCurrentSession(null);
      setSampleChartData([]);
      setFrameTimeData([]);
      setPieData([]);
      return;
    }

    const loadAnalysis = async () => {
      try {
        const [report, sessionDetail, samples] = await Promise.all([
          analysisApi.getFullReport(sessionId),
          sessionsApi.get(sessionId),
          sessionsApi.getSamples(sessionId, { limit: 300 }),
        ]);
        setFullReport(report);
        setCurrentSession(sessionDetail);
        setSampleChartData(buildSampleChartData(samples));
        setFrameTimeData(buildFrameTimeHistogram(samples));
        setPieData(buildFrameQualityPieData(samples));
      } catch {
        message.warning('未能读取后端分析结果，当前显示内置分析样例');
      }
    };
    loadAnalysis();
  }, [sessionId]);

  const canExportReport = Number.isFinite(sessionId);
  const currentSessionName = currentSession?.name || fullReport?.session_info?.name;
  const currentSceneLabel = currentSession ? getSessionSceneLabel(currentSession) : null;

  const handleExportReport = async (format: ReportFormat) => {
    if (!canExportReport) {
      message.warning('请先选择一个后端测试会话');
      return;
    }

    setExportingReport(true);
    try {
      const title = `${currentSessionName || `会话 ${sessionId}`} 详细测试报告`;
      const report = await reportsApi.generateFromSession(sessionId, {
        title,
        description: 'Web 端导出的详细渲染测试报告',
        format,
      });
      const { blob, filename } = await reportsApi.download(report.id);
      saveReportBlob(blob, filename || buildReportFilename(sessionId, currentSessionName, format));
      message.success(`报表已导出（${format.toUpperCase()}）`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '报表导出失败');
    } finally {
      setExportingReport(false);
    }
  };

  const exportMenuItems: MenuProps['items'] = [
    { key: 'html', label: '导出 HTML 详细报告' },
    { key: 'pdf', label: '导出 PDF 详细报告' },
  ];

  const comparisonColumns = [
    {
      title: '指标',
      dataIndex: 'metric',
      key: 'metric',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: 'Quest 3',
      dataIndex: 'quest3',
      key: 'quest3',
      render: (value: number) => (
        <Tag color="blue" style={{ fontFamily: 'monospace' }}>
          {value}
        </Tag>
      ),
    },
    {
      title: 'Quest 2',
      dataIndex: 'quest2',
      key: 'quest2',
      render: (value: number) => (
        <Tag color="cyan" style={{ fontFamily: 'monospace' }}>
          {value}
        </Tag>
      ),
    },
    {
      title: 'PICO 4',
      dataIndex: 'pico4',
      key: 'pico4',
      render: (value: number) => (
        <Tag color="purple" style={{ fontFamily: 'monospace' }}>
          {value}
        </Tag>
      ),
    },
  ];

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
  const hasDrawCallData = useMemo(
    () => sampleChartData.some((item) => item.drawCalls > 0),
    [sampleChartData],
  );

  const renderQuality = fullReport?.render_quality_assessment;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Space wrap>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate(returnTo)}
          >
            返回
          </Button>
          <h2 style={{ margin: 0 }}>性能分析</h2>
          {projectFilterId && <Tag color="blue">项目 {projectFilterId}</Tag>}
          {Number.isFinite(sessionId) ? (
            <>
              {currentSessionName && <Tag color="default">{currentSessionName}</Tag>}
              {currentSceneLabel && currentSceneLabel !== '-' && (
                <Tag color="geekblue">{currentSceneLabel}</Tag>
              )}
            </>
          ) : (
            <Tag color="default">未指定会话</Tag>
          )}
        </Space>
        <Dropdown
          menu={{
            items: exportMenuItems,
            onClick: ({ key }) => handleExportReport(key as ReportFormat),
          }}
          disabled={!canExportReport}
        >
          <Button icon={<DownloadOutlined />} loading={exportingReport} disabled={!canExportReport}>
            导出报表
          </Button>
        </Dropdown>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {fullReport?.section_status?.frame_rate === 'skipped' ? (
              <Statistic title="平均FPS" value="跳过" />
            ) : (
              <Statistic title="平均FPS" value={fullReport?.fps_analysis?.mean ?? '-'} precision={1} suffix="fps" valueStyle={{ color: '#3b82f6' }} />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {fullReport?.section_status?.frame_time === 'skipped' ? (
              <Statistic title="P95帧时间" value="跳过" />
            ) : (
              <Statistic title="P95帧时间" value={fullReport?.frame_time_analysis?.p95_ms ?? '-'} precision={1} suffix="ms" valueStyle={{ color: '#f59e0b' }} />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {fullReport?.section_status?.frame_time === 'skipped' ? (
              <Statistic title="掉帧率" value="跳过" />
            ) : (
              <Statistic title="掉帧率" value={((fullReport?.stability_summary?.dropped_frame_rate ?? 0) * 100)} precision={1} suffix="%" valueStyle={{ color: '#ef4444' }} />
            )}
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            {fullReport?.section_status?.frame_time === 'skipped' ? (
              <Statistic title="长帧次数" value="跳过" />
            ) : (
              <Statistic title="长帧次数" value={fullReport?.stability_summary?.long_frame_count ?? 0} valueStyle={{ color: '#8b5cf6' }} />
            )}
          </Card>
        </Col>
      </Row>

      <Tabs defaultActiveKey="fps">
        <TabPane tab="FPS趋势" key="fps">
          <Card>
            {fullReport?.section_status?.frame_rate === 'skipped' ? (
              <MetricSkippedPlaceholder title="FPS 未纳入本次测试" />
            ) : (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={fpsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis domain={[0, 90]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="fps" stroke="#3b82f6" name="FPS" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            )}
          </Card>
        </TabPane>

        <TabPane tab="帧时间分布" key="frametime">
          {fullReport?.section_status?.frame_time === 'skipped' ? (
            <MetricSkippedPlaceholder title="帧时间未纳入本次测试" />
          ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={16}>
              <Card title="帧时间直方图">
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={frameTimeData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="range" />
                    <YAxis />
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
          )}
        </TabPane>

        <TabPane tab="资源占用" key="resources">
          <Card>
            {(fullReport?.section_status?.cpu === 'skipped' && fullReport?.section_status?.gpu === 'skipped' && fullReport?.section_status?.memory === 'skipped') ? (
              <MetricSkippedPlaceholder title="资源占用指标未纳入本次测试" />
            ) : (
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
            )}
          </Card>
        </TabPane>

        <TabPane tab="Draw Calls" key="drawcalls">
          <Card>
            {!hasDrawCallData ? (
              <MetricSkippedPlaceholder title="Draw Calls 未纳入本次测试或无采样数据" />
            ) : (
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
            )}
          </Card>
        </TabPane>

        <TabPane tab="渲染质量" key="render-quality">
          <RenderQualityPanel assessment={renderQuality} />
        </TabPane>

        <TabPane tab="多设备对比" key="comparison">
          <Card title="设备性能对比">
            <Table
              columns={comparisonColumns}
              dataSource={comparisonData}
              pagination={false}
              size="middle"
            />
          </Card>
        </TabPane>

        <TabPane tab="设备信息" key="device-info">
          {fullReport?.section_status?.device_info === 'skipped' ? (
            <MetricSkippedPlaceholder title="设备信息未纳入本次测试" />
          ) : (
            <SessionDeviceInfoPanel sessionInfo={fullReport?.session_info} />
          )}
        </TabPane>
      </Tabs>
    </div>
  );
};

export default Analysis;
