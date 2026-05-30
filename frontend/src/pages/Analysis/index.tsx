import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Select, Statistic, Tabs, Table, Tag, message, Progress } from 'antd';
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
import { analysisApi, type FullReport, type RenderQualityCategory } from '@/api/analysis';
import { sessionsApi, type PerformanceSample } from '@/api/sessions';

const { Option } = Select;
const { TabPane } = Tabs;

const fpsData = [
  { time: '0s', session1: 72, session2: 65, session3: 58 },
  { time: '30s', session1: 70, session2: 63, session3: 55 },
  { time: '1m', session1: 71, session2: 64, session3: 57 },
  { time: '1m30s', session1: 68, session2: 62, session3: 54 },
  { time: '2m', session1: 72, session2: 66, session3: 59 },
  { time: '2m30s', session1: 69, session2: 64, session3: 56 },
  { time: '3m', session1: 71, session2: 65, session3: 58 },
  { time: '3m30s', session1: 70, session2: 63, session3: 55 },
  { time: '4m', session1: 72, session2: 67, session3: 60 },
  { time: '4m30s', session1: 68, session2: 62, session3: 54 },
  { time: '5m', session1: 71, session2: 65, session3: 57 },
];

const frameTimeData = [
  { range: '< 11ms', count: 450 },
  { range: '11-13ms', count: 280 },
  { range: '13-16ms', count: 120 },
  { range: '16-20ms', count: 80 },
  { range: '> 20ms', count: 45 },
];

const resourceData = [
  { time: '0s', cpu: 45, gpu: 62, memory: 3.2, vram: 2.1 },
  { time: '30s', cpu: 48, gpu: 68, memory: 3.4, vram: 2.3 },
  { time: '1m', cpu: 52, gpu: 72, memory: 3.6, vram: 2.5 },
  { time: '1m30s', cpu: 50, gpu: 70, memory: 3.5, vram: 2.4 },
  { time: '2m', cpu: 55, gpu: 75, memory: 3.8, vram: 2.7 },
  { time: '2m30s', cpu: 53, gpu: 73, memory: 3.7, vram: 2.6 },
  { time: '3m', cpu: 58, gpu: 78, memory: 4.0, vram: 2.9 },
  { time: '3m30s', cpu: 56, gpu: 76, memory: 3.9, vram: 2.8 },
  { time: '4m', cpu: 60, gpu: 80, memory: 4.2, vram: 3.1 },
  { time: '4m30s', cpu: 57, gpu: 77, memory: 4.0, vram: 2.9 },
  { time: '5m', cpu: 59, gpu: 79, memory: 4.1, vram: 3.0 },
];

const comparisonData = [
  { metric: '平均FPS', quest3: 72, quest2: 65, pico4: 58 },
  { metric: 'P95帧时间(ms)', quest3: 13.9, quest2: 15.4, pico4: 17.2 },
  { metric: '掉帧率(%)', quest3: 2.1, quest2: 3.8, pico4: 5.2 },
  { metric: '长帧次数', quest3: 12, quest2: 28, pico4: 45 },
  { metric: 'CPU平均(%)', quest3: 52, quest2: 58, pico4: 62 },
  { metric: 'GPU平均(%)', quest3: 68, quest2: 75, pico4: 82 },
];

const pieData = [
  { name: '正常帧', value: 850, color: '#10b981' },
  { name: '轻微掉帧', value: 80, color: '#f59e0b' },
  { name: '严重掉帧', value: 45, color: '#ef4444' },
  { name: '长帧', value: 25, color: '#8b5cf6' },
];

const fallbackSessionOptions = [
  { value: 'session1', label: 'Quest 3 - VR大空间' },
  { value: 'session2', label: 'Quest 2 - 标准场景' },
  { value: 'session3', label: 'PICO 4 - 协同场景' },
];

const Analysis: React.FC = () => {
  const [selectedSessions, setSelectedSessions] = useState<string[]>(['session1', 'session2']);
  const [sessionOptions, setSessionOptions] = useState(fallbackSessionOptions);
  const [fullReport, setFullReport] = useState<FullReport | null>(null);
  const [sampleChartData, setSampleChartData] = useState<Array<{ time: string; fps: number; cpu: number; gpu: number; memory: number }>>([]);

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const response = await sessionsApi.list({ limit: 50 });
        if (response.items.length > 0) {
          const options = response.items.map((session) => ({
            value: String(session.id),
            label: session.name,
          }));
          setSessionOptions(options);
          setSelectedSessions([options[0].value]);
        }
      } catch {
        message.warning('未能读取后端会话，当前显示内置分析样例');
      }
    };
    loadSessions();
  }, []);

  useEffect(() => {
    const sessionId = Number(selectedSessions[0]);
    if (!Number.isFinite(sessionId)) {
      setFullReport(null);
      setSampleChartData([]);
      return;
    }

    const loadAnalysis = async () => {
      try {
        const [report, samples] = await Promise.all([
          analysisApi.getFullReport(sessionId),
          sessionsApi.getSamples(sessionId, { limit: 300 }),
        ]);
        setFullReport(report);
        setSampleChartData(samples.slice(0, 120).map((sample: PerformanceSample, index) => ({
          time: `${index}s`,
          fps: Number(sample.fps || 0),
          cpu: Number(sample.cpu_usage_percent || 0),
          gpu: Number(sample.gpu_usage_percent || 0),
          memory: Number(((sample.memory_mb || 0) / 1024).toFixed(2)),
        })));
      } catch {
        message.warning('未能读取后端分析结果，当前显示内置分析样例');
      }
    };
    loadAnalysis();
  }, [selectedSessions]);

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

  const renderQuality = fullReport?.render_quality_assessment;
  const qualityColumns = [
    {
      title: '维度',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: '得分',
      dataIndex: 'score',
      key: 'score',
      width: 180,
      render: (value: number) => <Progress percent={Math.round(value)} size="small" />,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: string) => {
        const color = value === '通过' ? 'green' : value === '需关注' ? 'orange' : 'red';
        return <Tag color={color}>{value}</Tag>;
      },
    },
    {
      title: '主要依据',
      key: 'metrics',
      render: (_: unknown, record: RenderQualityCategory) => (
        <span>
          {Object.entries(record.metrics)
            .filter(([, value]) => value !== null && value !== undefined)
            .slice(0, 4)
            .map(([key, value]) => `${key}: ${value}`)
            .join('；') || '暂无专项采集指标'}
        </span>
      ),
    },
    {
      title: '扣分项',
      key: 'deductions',
      render: (_: unknown, record: RenderQualityCategory) => (
        <span>
          {record.deductions.length
            ? record.deductions.map((item) => `${item.reason}(-${item.points})`).join('；')
            : '无明显扣分项'}
        </span>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>性能分析</h2>
        <Select
          mode="multiple"
          placeholder="选择对比会话"
          value={selectedSessions}
          onChange={setSelectedSessions}
          style={{ width: 400 }}
        >
          {sessionOptions.map((opt) => (
            <Option key={opt.value} value={opt.value}>
              {opt.label}
            </Option>
          ))}
        </Select>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="平均FPS" value={fullReport?.fps_analysis?.mean ?? 70.3} precision={1} suffix="fps" valueStyle={{ color: '#3b82f6' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="P95帧时间" value={fullReport?.frame_time_analysis?.p95_ms ?? 14.2} precision={1} suffix="ms" valueStyle={{ color: '#f59e0b' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="掉帧率" value={((fullReport?.stability_summary?.dropped_frame_rate ?? 0.032) * 100)} precision={1} suffix="%" valueStyle={{ color: '#ef4444' }} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic title="长帧次数" value={fullReport?.stability_summary?.long_frame_count ?? 28} valueStyle={{ color: '#8b5cf6' }} />
          </Card>
        </Col>
      </Row>

      <Tabs defaultActiveKey="fps">
        <TabPane tab="FPS趋势" key="fps">
          <Card>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={sampleChartData.length ? sampleChartData : fpsData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis domain={[0, 90]} />
                <Tooltip />
                <Legend />
                {sampleChartData.length ? (
                  <Line type="monotone" dataKey="fps" stroke="#3b82f6" name="FPS" strokeWidth={2} dot={false} />
                ) : (
                  <>
                    {selectedSessions.includes('session1') && (
                      <Line type="monotone" dataKey="session1" stroke="#3b82f6" name="Quest 3" strokeWidth={2} dot={false} />
                    )}
                    {selectedSessions.includes('session2') && (
                      <Line type="monotone" dataKey="session2" stroke="#10b981" name="Quest 2" strokeWidth={2} dot={false} />
                    )}
                    {selectedSessions.includes('session3') && (
                      <Line type="monotone" dataKey="session3" stroke="#f59e0b" name="PICO 4" strokeWidth={2} dot={false} />
                    )}
                  </>
                )}
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </TabPane>

        <TabPane tab="帧时间分布" key="frametime">
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
        </TabPane>

        <TabPane tab="资源占用" key="resources">
          <Card>
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={sampleChartData.length ? sampleChartData : resourceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis yAxisId="left" domain={[0, 100]} />
                <YAxis yAxisId="right" orientation="right" domain={[0, 5]} />
                <Tooltip />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="cpu" stroke="#3b82f6" name="CPU (%)" strokeWidth={2} dot={false} />
                <Line yAxisId="left" type="monotone" dataKey="gpu" stroke="#ef4444" name="GPU (%)" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="memory" stroke="#10b981" name="内存 (GB)" strokeWidth={2} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="vram" stroke="#f59e0b" name="显存 (GB)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </TabPane>

        <TabPane tab="渲染质量" key="render-quality">
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic title="总体质量分" value={renderQuality?.overall_score ?? 0} precision={1} suffix="/ 100" />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic title="质量等级" value={renderQuality?.grade ?? '-'} />
              </Card>
            </Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic title="证据样本数" value={renderQuality?.evidence.sample_count ?? 0} />
              </Card>
            </Col>
          </Row>
          <Card
            title="光照、材质、后处理与物理仿真评分"
            extra={<Tag color={renderQuality?.evidence.has_runtime_quality_metrics ? 'blue' : 'orange'}>
              {renderQuality?.evaluation_mode.type ?? '未评估'}
            </Tag>}
          >
            <Table
              columns={qualityColumns}
              dataSource={renderQuality?.categories || []}
              rowKey="key"
              pagination={false}
              size="middle"
            />
            <div style={{ color: '#64748b', marginTop: 12 }}>
              {renderQuality?.evaluation_mode.description}
            </div>
          </Card>
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
      </Tabs>
    </div>
  );
};

export default Analysis;
