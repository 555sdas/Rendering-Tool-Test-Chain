import React, { useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Form, Input, Select, Space, Tag, message } from 'antd';
import { ReloadOutlined, SaveOutlined } from '@ant-design/icons';
import { systemSettingsApi, type UnitySettings, type UnitySettingsUpdate } from '@/api/systemSettings';


const PathStatus: React.FC<{ exists: boolean; empty?: boolean }> = ({ exists, empty }) => {
  if (empty) return <Tag>未配置</Tag>;
  return exists ? <Tag color="success">路径有效</Tag> : <Tag color="error">路径不存在</Tag>;
};

const Settings: React.FC = () => {
  const [form] = Form.useForm<UnitySettingsUpdate>();
  const [settings, setSettings] = useState<UnitySettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadSettings = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await systemSettingsApi.getUnitySettings();
      setSettings(data);
      form.setFieldsValue({
        unity_executable_path: data.unity_executable_path,
        unity_project_path: data.unity_project_path,
        unity_scene_path: data.unity_scene_path || undefined,
        collector_package_path: data.collector_package_path,
      });
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : '读取系统设置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async (values: UnitySettingsUpdate) => {
    setSaving(true);
    try {
      const data = await systemSettingsApi.updateUnitySettings(values);
      setSettings(data);
      form.setFieldsValue({
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
      setSaving(false);
    }
  };

  const status = settings?.status;
  const discoveredScenes = status?.discovered_scenes || [];

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>系统设置</h2>
        <Button icon={<ReloadOutlined />} loading={loading} onClick={loadSettings}>
          重新检测路径
        </Button>
      </Space>

      {loadError && (
        <Alert
          type="error"
          showIcon
          message="无法读取系统设置"
          description={`${loadError}。只有管理员拥有系统配置权限。`}
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
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="unity_executable_path"
            label="Unity 可执行文件"
            extra="Windows 示例：E:/Unity/2022.3.62f3/Editor/Unity.exe；macOS 示例：/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents/MacOS/Unity"
            rules={[{ required: true, message: '请输入 Unity 可执行文件路径' }]}
          >
            <Input placeholder="请输入后端机器上的 Unity 可执行文件绝对路径" />
          </Form.Item>

          <Form.Item
            name="unity_project_path"
            label="Unity 项目目录"
            extra="目录中应包含 Assets、Packages 和 ProjectSettings。场景将从此目录的 Assets 下自动发现。"
            rules={[{ required: true, message: '请输入 Unity 项目目录' }]}
          >
            <Input placeholder="例如：/Users/me/Projects/MyUnityProject" />
          </Form.Item>

          <Form.Item
            name="collector_package_path"
            label="XR 采集插件目录（可选）"
            extra="留空时默认使用本仓库的 unity-xr-collector 目录。"
          >
            <Input placeholder="例如：D:/Rendering-Tool-Test-Chain/unity-xr-collector" />
          </Form.Item>

          <Form.Item
            name="unity_scene_path"
            label="默认测试场景"
            extra={
              discoveredScenes.length > 0
                ? '测试页场景下拉框将默认选中此项；留空则使用扫描到的第一个场景。'
                : '请先保存有效的 Unity 项目路径以扫描场景列表。'
            }
          >
            <Select
              allowClear
              showSearch
              placeholder={discoveredScenes.length > 0 ? '请选择默认测试场景' : '暂无可用场景'}
              disabled={discoveredScenes.length === 0}
              optionFilterProp="label"
              options={discoveredScenes.map((scenePath) => ({
                value: scenePath,
                label: scenePath,
              }))}
            />
          </Form.Item>

          <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving} disabled={Boolean(loadError)}>
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
            <Descriptions.Item label="自动发现场景">
              {status?.discovered_scene_count ? (
                <Tag color="success">已发现 {status.discovered_scene_count} 个</Tag>
              ) : (
                <Tag color="warning">未发现场景</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="默认测试场景">
              {settings.unity_scene_path ? (
                <Tag color="blue">{settings.unity_scene_path}</Tag>
              ) : (
                <Tag>未指定（使用第一个扫描到的场景）</Tag>
              )}
            </Descriptions.Item>
            <Descriptions.Item label="XR 采集插件目录">
              <PathStatus exists={Boolean(status?.collector_package_exists)} empty={!settings.collector_package_path} />
            </Descriptions.Item>
            <Descriptions.Item label="配置保存位置">{settings.settings_file}</Descriptions.Item>
          </Descriptions>

          {discoveredScenes.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ marginBottom: 8, color: '#64748b' }}>场景预览（测试页下拉框将展示这些选项）</div>
              <Space size={[8, 8]} wrap>
                {discoveredScenes.map((scenePath) => (
                  <Tag key={scenePath} color={scenePath === settings.unity_scene_path ? 'blue' : undefined}>
                    {scenePath}
                    {scenePath === settings.unity_scene_path ? '（默认）' : ''}
                  </Tag>
                ))}
                {(status?.discovered_scene_count || 0) > discoveredScenes.length && (
                  <Tag>... 共 {status?.discovered_scene_count} 个</Tag>
                )}
              </Space>
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default Settings;
