import React, { useMemo } from 'react';
import { Alert, Card, Col, Progress, Row, Statistic, Tag, Tooltip, Typography } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import type { RenderQualityAssessment, RenderQualityCategory } from '@/api/analysis';
import {
  buildCategoryMetricDisplayItems,
  getStatusColor,
  type MetricDisplayItem,
} from '@/lib/renderQualityLabels';
import './RenderQualityPanel.css';

function MetricListLabel({ item }: { item: MetricDisplayItem }) {
  if (!item.description) {
    return <span className="rq-metric-list__label">{item.label}</span>;
  }

  return (
    <span className="rq-metric-list__label">
      {item.label}
      <Tooltip title={item.description} placement="topLeft">
        <QuestionCircleOutlined className="rq-metric-list__help" />
      </Tooltip>
    </span>
  );
}

interface RenderQualityPanelProps {
  assessment: RenderQualityAssessment | null | undefined;
}

function CategoryScoreRing({ category }: { category: RenderQualityCategory }) {
  if (category.tested === false || category.score === null || category.score === undefined) {
    return (
      <div className="rq-score-ring rq-score-ring--empty">
        <span>未测试</span>
      </div>
    );
  }

  const percent = Math.round(category.score);
  const color = getStatusColor(category.status);

  return (
    <Progress
      type="circle"
      percent={percent}
      size={96}
      strokeColor={color}
      trailColor="#f0f2f5"
      format={() => (
        <div className="rq-score-ring__inner">
          <strong style={{ color }}>{percent}</strong>
          <span>分</span>
        </div>
      )}
    />
  );
}

function MetricValue({ item }: { item: MetricDisplayItem }) {
  const valueClass = [
    'rq-metric-list__value',
    item.missing ? 'rq-metric-list__value--missing' : '',
    item.status === 'unavailable' ? 'rq-metric-list__value--unavailable' : '',
    item.status === 'failed' ? 'rq-metric-list__value--failed' : '',
    item.status === 'skipped' ? 'rq-metric-list__value--skipped' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <span className="rq-metric-list__result">
      <span className={valueClass}>{item.value}</span>
      {item.statusReason ? <span className="rq-metric-list__reason">{item.statusReason}</span> : null}
    </span>
  );

  if (item.statusTooltip) {
    return <Tooltip title={item.statusTooltip}>{content}</Tooltip>;
  }

  return content;
}

function CategoryCard({ category }: { category: RenderQualityCategory }) {
  const metricItems = buildCategoryMetricDisplayItems(category.metrics, category.metric_status);
  const statusColor = getStatusColor(category.status);

  return (
    <Card className="rq-category-card" bordered={false}>
      <div className="rq-category-card__header">
        <div>
          <Typography.Title level={5} className="rq-category-card__title">
            {category.name}
          </Typography.Title>
          <Typography.Text type="secondary" className="rq-category-card__weight">
            权重 {category.weight}%
            {category.included_in_overall_score === false && category.tested ? '（不计入总分）' : ''}
          </Typography.Text>
        </div>
        <Tag color={statusColor === '#52c41a' ? 'success' : statusColor === '#faad14' ? 'warning' : category.status === '未测试' ? 'default' : 'error'}>
          {category.status}
        </Tag>
      </div>

      <div className="rq-category-card__body">
        <CategoryScoreRing category={category} />

        <div className="rq-category-card__content">
          <div className="rq-category-card__section">
            <div className="rq-category-card__section-title">主要依据</div>
            {metricItems.length > 0 ? (
              <ul className="rq-metric-list">
                {metricItems.map((item) => (
                  <li key={item.key}>
                    <MetricListLabel item={item} />
                    <MetricValue item={item} />
                  </li>
                ))}
              </ul>
            ) : (
              <Typography.Text type="secondary">暂无专项采集指标</Typography.Text>
            )}
          </div>

          <div className="rq-category-card__section">
            <div className="rq-category-card__section-title">扣分项</div>
            {category.deductions.length > 0 ? (
              <ul className="rq-deduction-list">
                {category.deductions.map((item, index) => (
                  <li key={`${item.reason}-${index}`}>
                    <span>{item.reason}</span>
                    <Tag color="error" className="rq-deduction-tag">-{item.points}</Tag>
                  </li>
                ))}
              </ul>
            ) : (
              <Typography.Text type="secondary">
                {category.tested === false ? '本次未勾选，不参与评分' : '无明显扣分项'}
              </Typography.Text>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  lighting: '光照与阴影',
  material: '材质与纹理',
  post_processing: '后处理与画面一致性',
  physics: '物理仿真与虚实融合',
};

const RenderQualityPanel: React.FC<RenderQualityPanelProps> = ({ assessment }) => {
  const scoringSummary = useMemo(() => {
    if (!assessment?.scoring_definition) return null;
    const weights = assessment.scoring_definition.category_weights;
    const included = assessment.score_formula?.included_categories || [];
    const formulaParts = (assessment.categories || [])
      .filter((category) => included.includes(category.key as keyof typeof weights))
      .map((category) => `${category.name} × ${category.weight}%`);
    return {
      formulaText: formulaParts.length > 0 ? formulaParts.join(' + ') : '暂无参与总分的分类',
      configuredWeights: Object.entries(weights).map(([key, value]) => ({
        key,
        label: CATEGORY_LABELS[key] || key,
        value,
      })),
    };
  }, [assessment]);

  if (!assessment) {
    return (
      <Card>
        <div className="rq-empty">暂无渲染质量评估数据，请先完成测试采集。</div>
      </Card>
    );
  }

  return (
    <div className="render-quality-panel">
      <Row gutter={[16, 16]} className="rq-summary-row">
        <Col xs={24} sm={12} lg={6}>
          <Card className="rq-summary-card">
            <Statistic
              title="总体质量分"
              value={assessment.overall_score ?? '未测试'}
              precision={assessment.overall_score == null ? undefined : 1}
              suffix={assessment.overall_score == null ? '' : ' / 100'}
              valueStyle={{ color: '#1677ff', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="rq-summary-card">
            <Statistic
              title="质量等级"
              value={assessment.grade ?? '-'}
              valueStyle={{ color: '#722ed1', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="rq-summary-card">
            <Statistic
              title="数据完整度"
              value={
                assessment.data_completeness != null
                  ? Math.round(assessment.data_completeness * 100)
                  : '未评估'
              }
              suffix={assessment.data_completeness != null ? '%' : ''}
              valueStyle={{ color: '#08979c', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="rq-summary-card">
            <Statistic
              title="置信等级"
              value={assessment.confidence_grade ?? assessment.evidence.confidence_grade ?? '-'}
              valueStyle={{ color: '#d48806', fontWeight: 600 }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="rq-summary-row">
        <Col xs={24} sm={12}>
          <Card className="rq-summary-card">
            <Statistic
              title="证据样本数"
              value={assessment.evidence.sample_count ?? 0}
              valueStyle={{ color: '#13c2c2', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card className="rq-summary-card">
            <Statistic
              title="已选指标覆盖"
              value={
                assessment.coverage_summary
                  ? `${assessment.coverage_summary.available}/${assessment.coverage_summary.selected} 可用`
                  : '-'
              }
              valueStyle={{ color: '#595959', fontWeight: 600 }}
            />
          </Card>
        </Col>
      </Row>

      {scoringSummary && (
        <Card className="rq-scoring-definition-card" style={{ marginBottom: 16 }}>
          <Typography.Title level={5} style={{ marginTop: 0 }}>
            本次评分定义
          </Typography.Title>
          {assessment.scoring_definition_source === 'builtin_default' && (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message="旧版测试，使用系统内置默认权重 25% / 25% / 25% / 25%"
            />
          )}
          {assessment.scoring_definition_source === 'builtin_default_fallback' && (
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="会话评分定义无效，已回退系统内置默认权重"
              description={assessment.scoring_definition_fallback_reason || undefined}
            />
          )}
          <div className="rq-scoring-definition-grid">
            {scoringSummary.configuredWeights.map((item) => (
              <div key={item.key} className="rq-scoring-definition-item">
                <span>{item.label}</span>
                <strong>{item.value}%</strong>
              </div>
            ))}
          </div>
          <Typography.Paragraph type="secondary" style={{ margin: '12px 0 0' }}>
            参与总分：
            {(assessment.score_formula?.included_categories || [])
              .map((key) => CATEGORY_LABELS[key] || key)
              .join('、') || '无'}
          </Typography.Paragraph>
          {assessment.score_formula?.normalized && (
            <Alert
              type="info"
              showIcon
              style={{ marginTop: 12 }}
              message={`总分按有效权重 ${assessment.score_formula.effective_total_weight}% 归一化计算`}
            />
          )}
          {assessment.overall_score_reason && (
            <Alert
              type="warning"
              showIcon
              style={{ marginTop: 12 }}
              message={assessment.overall_score_reason}
            />
          )}
          <Typography.Paragraph type="secondary" className="rq-footnote" style={{ marginTop: 12, marginBottom: 0 }}>
            总分公式：{scoringSummary.formulaText}
          </Typography.Paragraph>
        </Card>
      )}

      <div className="rq-section-heading">
        <Typography.Title level={5}>光照、材质、后处理与物理仿真评分</Typography.Title>
        <Tag color={assessment.evidence.has_runtime_quality_metrics ? 'blue' : 'orange'}>
          {assessment.evaluation_mode.type ?? '未评估'}
        </Tag>
      </div>

      <Row gutter={[16, 16]}>
        {(assessment.categories || []).map((category) => (
          <Col xs={24} xl={12} key={category.key}>
            <CategoryCard category={category} />
          </Col>
        ))}
      </Row>

      <Typography.Paragraph type="secondary" className="rq-footnote">
        {assessment.evaluation_mode.description}
      </Typography.Paragraph>
    </div>
  );
};

export default RenderQualityPanel;
