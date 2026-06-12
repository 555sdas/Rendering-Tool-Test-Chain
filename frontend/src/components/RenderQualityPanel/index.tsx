import React from 'react';
import { Card, Col, Progress, Row, Statistic, Tag, Typography } from 'antd';
import type { RenderQualityAssessment, RenderQualityCategory } from '@/api/analysis';
import { buildMetricDisplayItems, getStatusColor } from '@/lib/renderQualityLabels';
import './RenderQualityPanel.css';

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

function CategoryCard({ category }: { category: RenderQualityCategory }) {
  const metricItems = buildMetricDisplayItems(category.metrics);
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
                    <span className="rq-metric-list__label">{item.label}</span>
                    <span className="rq-metric-list__value">{item.value}</span>
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

const RenderQualityPanel: React.FC<RenderQualityPanelProps> = ({ assessment }) => {
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
        <Col xs={24} sm={8}>
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
        <Col xs={24} sm={8}>
          <Card className="rq-summary-card">
            <Statistic
              title="质量等级"
              value={assessment.grade ?? '-'}
              valueStyle={{ color: '#722ed1', fontWeight: 600 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card className="rq-summary-card">
            <Statistic
              title="证据样本数"
              value={assessment.evidence.sample_count ?? 0}
              valueStyle={{ color: '#13c2c2', fontWeight: 600 }}
            />
          </Card>
        </Col>
      </Row>

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
