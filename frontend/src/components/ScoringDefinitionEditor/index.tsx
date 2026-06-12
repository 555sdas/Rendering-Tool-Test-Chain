import React, { useMemo } from 'react';
import { Alert, Button, Card, InputNumber, Slider, Space, Statistic, Typography, message, Modal } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import type {
  ScoringCategoryCatalogEntry,
  ScoringCategoryId,
  ScoringDefinition,
} from '@/api/systemSettings';

const CATEGORY_ORDER: ScoringCategoryId[] = ['lighting', 'material', 'post_processing', 'physics'];

interface ScoringDefinitionEditorProps {
  definition: ScoringDefinition;
  catalog: ScoringCategoryCatalogEntry[];
  saving?: boolean;
  onChange: (definition: ScoringDefinition) => void;
  onSave: () => Promise<void>;
  onReset: () => Promise<void>;
}

function buildFormulaPreview(
  weights: Record<ScoringCategoryId, number>,
  catalog: ScoringCategoryCatalogEntry[],
): string {
  const labelMap = Object.fromEntries(catalog.map((item) => [item.id, item.label]));
  return CATEGORY_ORDER.map((id) => `${labelMap[id] || id} × ${weights[id]}%`).join(' + ');
}

const ScoringDefinitionEditor: React.FC<ScoringDefinitionEditorProps> = ({
  definition,
  catalog,
  saving = false,
  onChange,
  onSave,
  onReset,
}) => {
  const weights = definition.category_weights;
  const totalWeight = useMemo(
    () => CATEGORY_ORDER.reduce((sum, id) => sum + (weights[id] || 0), 0),
    [weights],
  );
  const weightDelta = Math.round((totalWeight - 100) * 100) / 100;
  const canSave = Math.abs(weightDelta) < 0.01;

  const updateWeight = (categoryId: ScoringCategoryId, value: number | null) => {
    if (value == null || Number.isNaN(value)) return;
    onChange({
      ...definition,
      category_weights: {
        ...definition.category_weights,
        [categoryId]: Math.max(0, Math.min(100, value)),
      },
    });
  };

  const handleAverage = () => {
    onChange({
      ...definition,
      category_weights: {
        lighting: 25,
        material: 25,
        post_processing: 25,
        physics: 25,
      },
    });
  };

  const handleReset = () => {
    Modal.confirm({
      title: '恢复系统默认评分定义？',
      content: '将恢复为 25% / 25% / 25% / 25%，仅影响之后创建的新测试。',
      okText: '确认恢复',
      cancelText: '取消',
      onOk: async () => {
        try {
          await onReset();
          message.success('已恢复系统默认评分定义');
        } catch (error) {
          message.error(error instanceof Error ? error.message : '恢复失败');
        }
      },
    });
  };

  const handleSave = async () => {
    if (!canSave) {
      message.error(`权重总和必须为 100%，当前差额 ${weightDelta > 0 ? '+' : ''}${weightDelta.toFixed(2)}%`);
      return;
    }
    try {
      await onSave();
      message.success('评分定义已保存');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存评分定义失败');
    }
  };

  const labelMap = Object.fromEntries(catalog.map((item) => [item.id, item]));

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="评分定义说明"
        description={
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>修改仅影响之后创建的新测试；历史测试继续使用创建时的评分定义快照。</li>
            <li>权重为 0 的分类仍会展示评分，但不计入总分。</li>
            <li>当前评分属于预测试风险评估模型，不代表最终画质认证结论。</li>
          </ul>
        }
      />

      <Card
        title="分类权重"
        extra={
          <Space>
            <Button onClick={handleAverage}>平均分配</Button>
            <Button onClick={handleReset} loading={saving}>
              恢复系统默认
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving} disabled={!canSave}>
              保存评分定义
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {CATEGORY_ORDER.map((categoryId) => {
            const entry = labelMap[categoryId];
            const value = weights[categoryId];
            return (
              <Card key={categoryId} size="small" type="inner">
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                    <div>
                      <Typography.Text strong>{entry?.label || categoryId}</Typography.Text>
                      {entry?.description ? (
                        <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>
                          {entry.description}
                        </Typography.Paragraph>
                      ) : null}
                    </div>
                    <InputNumber
                      min={0}
                      max={100}
                      step={1}
                      value={value}
                      addonAfter="%"
                      onChange={(next) => updateWeight(categoryId, next)}
                    />
                  </div>
                  <Slider
                    min={0}
                    max={100}
                    value={value}
                    onChange={(next) => updateWeight(categoryId, next)}
                  />
                </Space>
              </Card>
            );
          })}
        </Space>

        <div style={{ marginTop: 20, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <Statistic
            title="权重总和"
            value={totalWeight}
            precision={2}
            suffix="%"
            valueStyle={{ color: canSave ? '#3f8600' : '#cf1322' }}
          />
          {!canSave ? (
            <Statistic
              title="与 100% 的差额"
              value={weightDelta}
              precision={2}
              suffix="%"
              valueStyle={{ color: '#cf1322' }}
            />
          ) : (
            <Statistic title="校验状态" value="可保存" valueStyle={{ color: '#3f8600' }} />
          )}
        </div>

        <Alert
          type="success"
          showIcon
          style={{ marginTop: 16 }}
          message="总分公式预览"
          description={`总分 = ${buildFormulaPreview(weights, catalog)}`}
        />
      </Card>
    </div>
  );
};

export default ScoringDefinitionEditor;
