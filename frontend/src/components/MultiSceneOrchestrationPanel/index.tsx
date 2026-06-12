import React, { useMemo, useState } from 'react';
import { Alert, Button, Select, Space, Table, Tag, Typography } from 'antd';
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CopyOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import SceneRunConfigDrawer from '@/components/SceneRunConfigDrawer';
import { fillScopeKeys, hasAnyEnabledLeaf, type MetricCatalog, type TestScope } from '@/lib/testScope';
import type { UnitySceneResource } from '@/api/unityRunner';
import type { SceneRunDraft } from './types';

const { Option } = Select;

function cloneScope(scope: TestScope): TestScope {
  return fillScopeKeys(structuredClone(scope), 'batch_scene_draft');
}

function createDraftFromScene(
  scene: UnitySceneResource,
  defaultScope: TestScope,
  defaults: { collectInterval: number; frameRateDurationSeconds: number; metricsDurationSeconds: number },
): SceneRunDraft {
  return {
    clientId: `${scene.id}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    sceneResourceId: scene.id,
    sceneName: scene.name,
    scenePath: scene.scene_path,
    projectPath: scene.project_path,
    testScope: cloneScope(defaultScope),
    collectInterval: defaults.collectInterval,
    frameRateDurationSeconds: defaults.frameRateDurationSeconds,
    metricsDurationSeconds: defaults.metricsDurationSeconds,
  };
}

interface MultiSceneOrchestrationPanelProps {
  scenes: UnitySceneResource[];
  defaultScope: TestScope;
  defaultDurations: {
    collectInterval: number;
    frameRateDurationSeconds: number;
    metricsDurationSeconds: number;
  };
  drafts: SceneRunDraft[];
  onChange: (drafts: SceneRunDraft[]) => void;
  metricsCatalog: MetricCatalog | null;
}

const MultiSceneOrchestrationPanel: React.FC<MultiSceneOrchestrationPanelProps> = ({
  scenes,
  defaultScope,
  defaultDurations,
  drafts,
  onChange,
  metricsCatalog,
}) => {
  const [pickerSceneId, setPickerSceneId] = useState<string | undefined>();
  const [editingDraft, setEditingDraft] = useState<SceneRunDraft | null>(null);

  const enabledScenes = useMemo(
    () => scenes.filter((scene) => scene.enabled && scene.exists),
    [scenes],
  );

  const addScene = () => {
    const scene = enabledScenes.find((item) => item.id === pickerSceneId);
    if (!scene) return;
    if (drafts.some((item) => item.sceneResourceId === scene.id)) return;
    onChange([...drafts, createDraftFromScene(scene, defaultScope, defaultDurations)]);
    setPickerSceneId(undefined);
  };

  const moveScene = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= drafts.length) return;
    const next = [...drafts];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const columns = [
    {
      title: '#',
      width: 48,
      render: (_: unknown, __: SceneRunDraft, index: number) => index + 1,
    },
    {
      title: '场景',
      dataIndex: 'sceneName',
      render: (name: string, record: SceneRunDraft) => (
        <div>
          <strong>{name}</strong>
          <div style={{ color: '#8c8c8c', fontSize: 12 }}>{record.scenePath}</div>
        </div>
      ),
    },
    {
      title: '指标',
      render: (_: unknown, record: SceneRunDraft) => (
        <Tag color={hasAnyEnabledLeaf(record.testScope) ? 'blue' : 'default'}>
          {hasAnyEnabledLeaf(record.testScope) ? '已配置' : '未选择'}
        </Tag>
      ),
    },
    {
      title: '时长',
      render: (_: unknown, record: SceneRunDraft) =>
        `${record.frameRateDurationSeconds}s + ${record.metricsDurationSeconds}s`,
    },
    {
      title: '操作',
      width: 220,
      render: (_: unknown, record: SceneRunDraft, index: number) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => setEditingDraft(record)} />
          <Button size="small" icon={<ArrowUpOutlined />} disabled={index === 0} onClick={() => moveScene(index, -1)} />
          <Button
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={index === drafts.length - 1}
            onClick={() => moveScene(index, 1)}
          />
          <Button
            size="small"
            icon={<CopyOutlined />}
            disabled={index === 0}
            onClick={() => {
              const prev = drafts[index - 1];
              onChange(
                drafts.map((item) =>
                  item.clientId === record.clientId
                    ? {
                        ...item,
                        testScope: cloneScope(prev.testScope),
                        collectInterval: prev.collectInterval,
                        frameRateDurationSeconds: prev.frameRateDurationSeconds,
                        metricsDurationSeconds: prev.metricsDurationSeconds,
                      }
                    : item,
                ),
              );
            }}
          />
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            disabled={drafts.length <= 2}
            onClick={() => onChange(drafts.filter((item) => item.clientId !== record.clientId))}
          />
        </Space>
      ),
    },
  ];

  const projectPaths = new Set(drafts.map((item) => item.projectPath));

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="多场景连续测试"
        description="按顺序在同一 Unity 编辑器中连续运行多个场景，每个场景生成独立会话。所有场景必须属于同一工程。"
      />
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          style={{ minWidth: 280 }}
          placeholder="选择要添加的场景"
          value={pickerSceneId}
          onChange={setPickerSceneId}
          showSearch
          optionFilterProp="label"
        >
          {enabledScenes.map((scene) => (
            <Option key={scene.id} value={scene.id} label={scene.name}>
              {scene.name}
            </Option>
          ))}
        </Select>
        <Button type="dashed" icon={<PlusOutlined />} onClick={addScene} disabled={!pickerSceneId}>
          添加场景
        </Button>
        <Button
          onClick={() =>
            onChange(
              drafts.map((item) => ({
                ...item,
                testScope: cloneScope(defaultScope),
                collectInterval: defaultDurations.collectInterval,
                frameRateDurationSeconds: defaultDurations.frameRateDurationSeconds,
                metricsDurationSeconds: defaultDurations.metricsDurationSeconds,
              })),
            )
          }
          disabled={drafts.length === 0}
        >
          全部恢复默认
        </Button>
      </Space>

      {projectPaths.size > 1 && (
        <Alert type="error" showIcon message="所选场景必须属于同一 Unity 工程" style={{ marginBottom: 12 }} />
      )}

      <Table
        rowKey="clientId"
        columns={columns}
        dataSource={drafts}
        pagination={false}
        locale={{ emptyText: '请至少添加 2 个场景' }}
      />

      {drafts.length > 0 && drafts.length < 2 && (
        <Typography.Text type="danger" style={{ display: 'block', marginTop: 8 }}>
          多场景编排至少需要 2 个场景
        </Typography.Text>
      )}

      <SceneRunConfigDrawer
        open={Boolean(editingDraft)}
        draft={editingDraft}
        catalog={metricsCatalog}
        onClose={() => setEditingDraft(null)}
        onSave={(saved) => onChange(drafts.map((item) => (item.clientId === saved.clientId ? saved : item)))}
      />
    </div>
  );
};

export default MultiSceneOrchestrationPanel;
