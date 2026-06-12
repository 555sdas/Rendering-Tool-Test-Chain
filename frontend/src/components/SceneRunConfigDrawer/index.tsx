import React, { useEffect, useState } from 'react';
import { Button, Drawer, InputNumber, Space } from 'antd';
import MetricScopeSelector from '@/components/MetricScopeSelector';
import { fillScopeKeys, hasAnyEnabledLeaf, type MetricCatalog, type TestScope } from '@/lib/testScope';
import type { SceneRunDraft } from '@/components/MultiSceneOrchestrationPanel/types';

interface SceneRunConfigDrawerProps {
  open: boolean;
  draft: SceneRunDraft | null;
  catalog: MetricCatalog | null;
  onClose: () => void;
  onSave: (draft: SceneRunDraft) => void;
}

const SceneRunConfigDrawer: React.FC<SceneRunConfigDrawerProps> = ({
  open,
  draft,
  catalog,
  onClose,
  onSave,
}) => {
  const [localDraft, setLocalDraft] = useState<SceneRunDraft | null>(draft);

  useEffect(() => {
    if (draft) {
      setLocalDraft({
        ...draft,
        testScope: fillScopeKeys(structuredClone(draft.testScope), 'batch_scene_override'),
      });
    }
  }, [draft]);

  if (!localDraft) return null;

  return (
    <Drawer
      title={`编辑场景：${localDraft.sceneName}`}
      width={720}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            onClick={() => {
              if (!hasAnyEnabledLeaf(localDraft.testScope)) return;
              onSave(localDraft);
              onClose();
            }}
            disabled={!hasAnyEnabledLeaf(localDraft.testScope)}
          >
            保存配置
          </Button>
        </Space>
      }
    >
      <Space size="large" wrap style={{ marginBottom: 16 }}>
        <div>
          <div style={{ marginBottom: 4 }}>采集间隔（秒）</div>
          <InputNumber
            min={0.1}
            max={10}
            step={0.1}
            value={localDraft.collectInterval}
            onChange={(value) => setLocalDraft((current) => current ? { ...current, collectInterval: Number(value) || 1 } : current)}
          />
        </div>
        <div>
          <div style={{ marginBottom: 4 }}>帧率采集时长（秒）</div>
          <InputNumber
            min={1}
            max={600}
            value={localDraft.frameRateDurationSeconds}
            onChange={(value) => setLocalDraft((current) => current ? { ...current, frameRateDurationSeconds: Number(value) || 30 } : current)}
          />
        </div>
        <div>
          <div style={{ marginBottom: 4 }}>指标采集时长（秒）</div>
          <InputNumber
            min={1}
            max={600}
            value={localDraft.metricsDurationSeconds}
            onChange={(value) => setLocalDraft((current) => current ? { ...current, metricsDurationSeconds: Number(value) || 30 } : current)}
          />
        </div>
      </Space>
      <MetricScopeSelector
        catalog={catalog}
        value={localDraft.testScope}
        onChange={(scope: TestScope) => setLocalDraft((current) => current ? { ...current, testScope: scope } : current)}
      />
    </Drawer>
  );
};

export default SceneRunConfigDrawer;
