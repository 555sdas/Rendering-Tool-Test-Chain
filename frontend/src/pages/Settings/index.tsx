import React, { useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Form, Input, Select, Space, Tabs, Tag, message } from 'antd';
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import MetricScopeSelector from '@/components/MetricScopeSelector';
import ScoringDefinitionEditor from '@/components/ScoringDefinitionEditor';
import {
  DEFAULT_SCORING_DEFINITION,
  systemSettingsApi,
  type ScoringCategoryCatalogEntry,
  type ScoringDefinition,
  type UnitySettings,
  type UnitySettingsUpdate,
} from '@/api/systemSettings';
import { buildBuiltinDefaultScope, fillScopeKeys, hasAnyEnabledLeaf, type MetricCatalog, type TestScope } from '@/lib/testScope';

const PathStatus: React.FC<{ exists: boolean; empty?: boolean }> = ({ exists, empty }) => {
  if (empty) return <Tag>未配置</Tag>;
  return exists ? <Tag color="success">路径有效</Tag> : <Tag color="error">路径不存在</Tag>;
};

const Settings: React.FC = () => {
  const [pathForm] = Form.useForm<UnitySettingsUpdate>();
  const [settings, setSettings] = useState<UnitySettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingPaths, setSavingPaths] = useState(false);
  const [savingMetrics, setSavingMetrics] = useState(false);
  const [pathLoadError, setPathLoadError] = useState<string | null>(null);
  const [metricsLoadError, setMetricsLoadError] = useState<string | null>(null);
  const [metricsCatalog, setMetricsCatalog] = useState<MetricCatalog | null>(null);
  const [testScope, setTestScope] = useState<TestScope>(buildBuiltinDefaultScope('global_default'));
  const [scoringDefinition, setScoringDefinition] = useState<ScoringDefinition>(DEFAULT_SCORING_DEFINITION);
  const [scoringCatalog, setScoringCatalog] = useState<ScoringCategoryCatalogEntry[]>([]);
  const [scoringLoading, setScoringLoading] = useState(false);
  const [scoringSaving, setScoringSaving] = useState(false);
  const [scoringError, setScoringError] = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    setPathLoadError(null);
    setMetricsLoadError(null);
    setScoringError(null);
    setScoringLoading(true);

    const [unityResult, catalogResult, metricsResult, scoringResult] = await Promise.allSettled([
      systemSettingsApi.getUnitySettings(),
      systemSettingsApi.getTestMetricsCatalog(),
      systemSettingsApi.getDefaultTestScope(),
      systemSettingsApi.getScoringDefinition(),
    ]);

    if (unityResult.status === 'fulfilled') {
      const data = unityResult.value;
      setSettings(data);
      pathForm.setFieldsValue({
        unity_executable_path: data.unity_executable_path,
        unity_project_path: data.unity_project_path,
        unity_scene_path: data.unity_scene_path || undefined,
        collector_package_path: data.collector_package_path,
      });
    } else {
      setPathLoadError(
        unityResult.reason instanceof Error ? unityResult.reason.message : '读取 Unity 路径设置失败',
      );
    }

    if (catalogResult.status === 'fulfilled') {
      setMetricsCatalog(catalogResult.value);
    } else {
      setMetricsLoadError(
        catalogResult.reason instanceof Error ? catalogResult.reason.message : '读取测试指标目录失败',
      );
    }

    if (metricsResult.status === 'fulfilled') {
      setTestScope(fillScopeKeys(metricsResult.value.default_scope, 'global_default'));
    } else {
      setMetricsLoadError(
        metricsResult.reason instanceof Error ? metricsResult.reason.message : '读取默认测试指标失败',
      );
    }

    if (scoringResult.status === 'fulfilled') {
      setScoringDefinition(scoringResult.value.definition);
      setScoringCatalog(scoringResult.value.catalog.categories);
    } else {
      setScoringError(
        scoringResult.reason instanceof Error ? scoringResult.reason.message : '读取评分定义失败',
      );
    }

    setScoringLoading(false);
    setLoading(false);
  };

  useEffect(() => {
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSavePaths = async (values: UnitySettingsUpdate) => {
    setSavingPaths(true);
    try {
      const data = await systemSettingsApi.updateUnitySettings(values);
      setSettings(data);
      pathForm.setFieldsValue({
        unity_executable_path: data.unity_executable_path,
        unity_project_path: data.unity_project_path,
        unity_scene_path: data.unity_scene_path || undefined,
        collector_package_path: data.collector_package_path,
      });
      const sceneCount = data.status.discovered_scene_count ?? 0;
      message.success(
        sceneCount > 0
          ? `Unity 路径配置已保存，已自动发现 ${sceneCount} 个场景`
          : 'Unity 路径配置已保存，未在 Assets 下发现 .unity 场景文件',
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存系统设置失败');
    } finally {
      setSavingPaths(false);
    }
  };

  const handleSaveMetrics = async () => {
    if (!hasAnyEnabledLeaf(testScope)) {
      message.error('请至少选择一个测试指标');
      return;
    }
    setSavingMetrics(true);
    try {
      const result = await systemSettingsApi.updateDefaultTestScope({
        ...testScope,
        source: 'global_default',
      });
      setTestScope(fillScopeKeys(result.default_scope, 'global_default'));
      message.success('全局默认测试指标已保存');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存测试指标失败');
    } finally {
      setSavingMetrics(false);
    }
  };

  const handleResetMetrics = async () => {
    setSavingMetrics(true);
    try {
      const result = await systemSettingsApi.resetDefaultTestScope();
      setTestScope(fillScopeKeys(result.default_scope, 'built_in_default'));
      message.success('已恢复系统内置默认测试指标');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '重置测试指标失败');
    } finally {
      setSavingMetrics(false);
    }
  };

  const handleSaveScoring = async () => {
    setScoringSaving(true);
    try {
      const result = await systemSettingsApi.updateScoringDefinition(scoringDefinition);
      setScoringDefinition(result.definition);
      setScoringCatalog(result.catalog.categories);
    } finally {
      setScoringSaving(false);
    }
  };

  const handleResetScoring = async () => {
    setScoringSaving(true);
    try {
      const result = await systemSettingsApi.resetScoringDefinition();
      setScoringDefinition(result.definition);
      setScoringCatalog(result.catalog.categories);
    } finally {
      setScoringSaving(false);
    }
  };

  const status = settings?.status;
  const discoveredScenes = status?.discovered_scenes || [];

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>系统设置</h2>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={loadSettings}>
          重新加载
        </Button>
      </Space>

      <Tabs
        items={[
          {
            key: 'unity-paths',
            label: 'Unity 本地测试路径',
            children: (
              <>
                {pathLoadError && (
                  <Alert
                    type="error"
                    showIcon
                    message="无法读取 Unity 路径设置"
                    description={`${pathLoadError}。只有管理员拥有系统配置权限。`}
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Alert
                  type="info"
                  showIcon
                  message="路径属于后端运行机器"
                  description="请填写后端所在电脑上的绝对路径。保存后，系统会自动扫描 Unity 项目 Assets 目录下的 .unity 场景；可在下方指定默认测试场景，项目详情页将自动选中该场景。"
                  style={{ marginBottom: 16 }}
                />
                <Card title="Unity 本地测试路径" loading={loading}>
                  <Form form={pathForm} layout="vertical" onFinish={handleSavePaths}>
                    <Form.Item
                      name="unity_executable_path"
                      label="Unity 可执行文件"
                      rules={[{ required: true, message: '请输入 Unity 可执行文件路径' }]}
                    >
                      <Input placeholder="请输入后端机器上的 Unity 可执行文件绝对路径" />
                    </Form.Item>
                    <Form.Item
                      name="unity_project_path"
                      label="Unity 项目目录"
                      rules={[{ required: true, message: '请输入 Unity 项目目录' }]}
                    >
                      <Input placeholder="例如：/Users/me/Projects/MyUnityProject" />
                    </Form.Item>
                    <Form.Item name="collector_package_path" label="XR 采集插件目录（可选）">
                      <Input placeholder="例如：D:/Rendering-Tool-Test-Chain/unity-xr-collector" />
                    </Form.Item>
                    <Form.Item name="unity_scene_path" label="默认测试场景">
                      <Select
                        allowClear
                        showSearch
                        placeholder={discoveredScenes.length > 0 ? '请选择默认测试场景' : '暂无可用场景'}
                        disabled={discoveredScenes.length === 0}
                        options={discoveredScenes.map((scenePath) => ({ value: scenePath, label: scenePath }))}
                      />
                    </Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      icon={<SaveOutlined />}
                      loading={savingPaths}
                      disabled={Boolean(pathLoadError)}
                    >
                      保存并检测
                    </Button>
                  </Form>
                </Card>
                {settings && (
                  <Card title="当前检测结果" style={{ marginTop: 16 }}>
                    <Descriptions column={1} bordered size="small">
                      <Descriptions.Item label="Unity 可执行文件">
                        <PathStatus exists={Boolean(status?.unity_executable_exists)} empty={!settings.unity_executable_path} />
                      </Descriptions.Item>
                      <Descriptions.Item label="Unity 项目目录">
                        <PathStatus exists={Boolean(status?.unity_project_exists)} empty={!settings.unity_project_path} />
                      </Descriptions.Item>
                      <Descriptions.Item label="默认测试场景">
                        {settings.unity_scene_path ? <Tag color="blue">{settings.unity_scene_path}</Tag> : <Tag>未指定</Tag>}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>
                )}
              </>
            ),
          },
          {
            key: 'test-metrics',
            label: '测试指标',
            children: (
              <>
                {metricsLoadError && (
                  <Alert
                    type="warning"
                    showIcon
                    message="测试指标设置加载失败"
                    description={metricsLoadError}
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Card
                  title="全局默认测试指标"
                  loading={loading}
                  extra={
                    <Space>
                      <Button onClick={handleResetMetrics} loading={savingMetrics}>
                        恢复系统默认
                      </Button>
                      <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveMetrics} loading={savingMetrics}>
                        保存测试指标
                      </Button>
                    </Space>
                  }
                >
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="全局默认测试范围"
                    description="此处配置的是新建测试时的默认勾选范围。项目详情页启动测试前仍可单次覆盖，不会影响历史会话快照。"
                  />
                  <MetricScopeSelector value={testScope} catalog={metricsCatalog} onChange={setTestScope} />
                </Card>
              </>
            ),
          },
          {
            key: 'scoring-definition',
            label: '评分定义',
            children: (
              <>
                {scoringError && (
                  <Alert
                    type="warning"
                    showIcon
                    message="评分定义加载失败"
                    description={scoringError}
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Card loading={scoringLoading || loading}>
                  <ScoringDefinitionEditor
                    definition={scoringDefinition}
                    catalog={scoringCatalog}
                    saving={scoringSaving}
                    onChange={setScoringDefinition}
                    onSave={handleSaveScoring}
                    onReset={handleResetScoring}
                  />
                </Card>
              </>
            ),
          },
        ]}
      />
    </div>
  );
};

export default Settings;
