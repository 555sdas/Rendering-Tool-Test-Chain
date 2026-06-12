import React, { useMemo, useState } from 'react';
import { Alert, Button, Card, Checkbox, Col, Collapse, Row, Tooltip, Typography } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import type { MetricCatalog, TestScope } from '@/lib/testScope';
import {
  applyParentRules,
  buildScopeSummary,
  fillScopeKeys,
  getCategoryCheckState,
  getMetricDescription,
  hasAnyEnabledLeaf,
  setAllScopeMetrics,
  toggleCategory,
  toggleQualityMetric,
  TOTAL_LEAF_METRIC_COUNT,
} from '@/lib/testScope';
import './MetricScopeSelector.css';

interface MetricLabelWithHelpProps {
  label: string;
  metricId: string;
  catalog?: MetricCatalog | null;
}

const MetricLabelWithHelp: React.FC<MetricLabelWithHelpProps> = ({ label, metricId, catalog }) => {
  const description = getMetricDescription(metricId, catalog);
  if (!description) return <>{label}</>;

  return (
    <span className="metric-scope-selector__metric-label">
      {label}
      <Tooltip title={description} placement="top">
        <QuestionCircleOutlined
          className="metric-scope-selector__help-icon"
          onClick={(event) => event.preventDefault()}
          onMouseDown={(event) => event.stopPropagation()}
        />
      </Tooltip>
    </span>
  );
};

interface MetricScopeSelectorProps {
  value: TestScope;
  catalog?: MetricCatalog | null;
  onChange: (scope: TestScope) => void;
  showSummary?: boolean;
}

const MetricScopeSelector: React.FC<MetricScopeSelectorProps> = ({
  value,
  catalog,
  onChange,
  showSummary = true,
}) => {
  const scope = useMemo(() => applyParentRules(fillScopeKeys(value)), [value]);
  const summary = useMemo(() => buildScopeSummary(scope, catalog), [scope, catalog]);

  const basicMetrics = catalog?.basic_metrics || [];
  const qualityCategories = catalog?.quality_categories || [];
  const qualityMetrics = catalog?.quality_metrics || [];

  const metricsByCategory = useMemo(() => {
    const grouped: Record<string, typeof qualityMetrics> = {};
    for (const entry of qualityMetrics) {
      const parent = entry.parent_id || entry.id.split('.')[0];
      grouped[parent] = grouped[parent] || [];
      grouped[parent].push(entry);
    }
    return grouped;
  }, [qualityMetrics]);

  const categoryIds = useMemo(
    () =>
      (qualityCategories.length > 0
        ? qualityCategories
        : [{ id: 'lighting', label: '光照与阴影' }]
      ).map((category) => category.id),
    [qualityCategories],
  );

  const [activeKeys, setActiveKeys] = useState<string[]>([]);

  const allSelected = summary.selected_count === TOTAL_LEAF_METRIC_COUNT;
  const noneSelected = summary.selected_count === 0;
  const allExpanded = categoryIds.length > 0 && activeKeys.length === categoryIds.length;
  const allCollapsed = activeKeys.length === 0;

  const categoryPanels = (qualityCategories.length > 0
    ? qualityCategories
    : [{ id: 'lighting', label: '光照与阴影' }]
  ).map((category) => {
    const categoryState = getCategoryCheckState(scope, category.id);
    const children = metricsByCategory[category.id] || [];
    const selectedChildCount = children.filter((entry) => scope.quality_metrics[entry.id]).length;

    return {
      key: category.id,
      label: (
        <div className="metric-scope-selector__category-header">
          <span onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()}>
            <Checkbox
              checked={categoryState.checked}
              indeterminate={categoryState.indeterminate}
              onChange={(event) => onChange(toggleCategory(scope, category.id, event.target.checked))}
              onClick={(event) => event.stopPropagation()}
            />
          </span>
          <span className="metric-scope-selector__category-title">{category.label}</span>
          {children.length > 0 && (
            <span className="metric-scope-selector__category-meta">
              {selectedChildCount}/{children.length} 项已选
            </span>
          )}
        </div>
      ),
      children:
        children.length > 0 ? (
          <Row gutter={[12, 8]} className="metric-scope-selector__child-grid">
            {children.map((entry) => (
              <Col key={entry.id} xs={24} sm={12} md={8}>
                <Checkbox
                  checked={Boolean(scope.quality_metrics[entry.id])}
                  disabled={!scope.quality_categories[category.id]}
                  onChange={(event) => onChange(toggleQualityMetric(scope, entry.id, event.target.checked))}
                >
                  <MetricLabelWithHelp label={entry.label} metricId={entry.id} catalog={catalog} />
                </Checkbox>
              </Col>
            ))}
          </Row>
        ) : (
          <Typography.Text type="secondary">暂无细分指标</Typography.Text>
        ),
    };
  });

  return (
    <div className="metric-scope-selector">
      {showSummary && (
        <Alert
          type={hasAnyEnabledLeaf(scope) ? 'info' : 'warning'}
          showIcon
          style={{ marginBottom: 16 }}
          message={
            hasAnyEnabledLeaf(scope)
              ? `本次将测试 ${summary.selected_count} 项，跳过 ${summary.skipped_count} 项`
              : '请至少选择一个测试指标'
          }
        />
      )}

      <div className="metric-scope-selector__toolbar">
        <div className="metric-scope-selector__action-group">
          <Button
            type="link"
            size="small"
            disabled={allSelected}
            onClick={() => onChange(setAllScopeMetrics(scope, true))}
          >
            全选
          </Button>
          <Button
            type="link"
            size="small"
            disabled={noneSelected}
            onClick={() => onChange(setAllScopeMetrics(scope, false))}
          >
            全不选
          </Button>
        </div>
        {categoryIds.length > 0 && (
          <div className="metric-scope-selector__action-group">
            <Button
              type="link"
              size="small"
              disabled={allExpanded}
              onClick={() => setActiveKeys(categoryIds)}
            >
              全部展开
            </Button>
            <Button
              type="link"
              size="small"
              disabled={allCollapsed}
              onClick={() => setActiveKeys([])}
            >
              全部折叠
            </Button>
          </div>
        )}
      </div>

      <Card title={catalog?.labels?.basic_metric || '基础性能指标'} size="small" style={{ marginBottom: 16 }}>
        <Checkbox.Group
          value={Object.entries(scope.basic_metrics)
            .filter(([, enabled]) => enabled)
            .map(([id]) => id)}
          onChange={(checkedValues) => {
            const next = { ...scope.basic_metrics };
            for (const entry of basicMetrics) next[entry.id] = false;
            for (const id of checkedValues as string[]) next[id] = true;
            onChange(applyParentRules({ ...scope, basic_metrics: next }));
          }}
        >
          <Row gutter={[12, 12]}>
            {basicMetrics.map((entry) => (
              <Col key={entry.id} xs={24} sm={12} md={8}>
                <Checkbox value={entry.id}>
                  <MetricLabelWithHelp label={entry.label} metricId={entry.id} catalog={catalog} />
                </Checkbox>
              </Col>
            ))}
          </Row>
        </Checkbox.Group>
      </Card>

      <Collapse
        className="metric-scope-selector__collapse"
        bordered={false}
        expandIconPosition="end"
        activeKey={activeKeys}
        onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys : [keys])}
        items={categoryPanels}
      />
    </div>
  );
};

export default MetricScopeSelector;
