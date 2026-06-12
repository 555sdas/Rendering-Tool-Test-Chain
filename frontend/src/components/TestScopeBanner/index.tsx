import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Collapse, Tag } from 'antd';
import type { MetricCatalog, TestScope, TestScopeSummary } from '@/lib/testScope';
import {
  buildScopeDisplayGroups,
  buildScopeSummary,
  fillScopeKeys,
  formatScopeGroupStatus,
  isLegacyInferredScope,
} from '@/lib/testScope';
import './TestScopeBanner.css';

interface TestScopeBannerProps {
  scope?: TestScope | null;
  summary?: TestScopeSummary | null;
  catalog?: MetricCatalog | null;
  style?: React.CSSProperties;
}

const TestScopeBanner: React.FC<TestScopeBannerProps> = ({ scope, summary, catalog, style }) => {
  const resolvedScope = useMemo(() => (scope ? fillScopeKeys(scope) : null), [scope]);
  const resolvedSummary = summary || (resolvedScope ? buildScopeSummary(resolvedScope, catalog) : null);

  const groups = useMemo(
    () => (resolvedScope ? buildScopeDisplayGroups(resolvedScope, catalog) : []),
    [resolvedScope, catalog],
  );

  const defaultActiveKeys = useMemo(
    () =>
      groups
        .filter((group) => group.selectedCount > 0 && group.selectedCount < group.totalCount)
        .map((group) => group.id),
    [groups],
  );

  const [activeKeys, setActiveKeys] = useState<string[]>(defaultActiveKeys);

  useEffect(() => {
    setActiveKeys(defaultActiveKeys);
  }, [defaultActiveKeys]);

  if (!resolvedSummary) return null;

  const allGroupKeys = groups.map((group) => group.id);
  const allExpanded = allGroupKeys.length > 0 && activeKeys.length === allGroupKeys.length;
  const allCollapsed = activeKeys.length === 0;

  const collapseItems = groups.map((group) => {
    const statusText = formatScopeGroupStatus(group);
    const isActive = group.selectedCount > 0;

    return {
      key: group.id,
      label: (
        <div className="test-scope-banner__group-header">
          <span className="test-scope-banner__group-title">{group.label}</span>
          <span
            className={`test-scope-banner__group-status ${
              isActive ? 'test-scope-banner__group-status--active' : 'test-scope-banner__group-status--none'
            }`}
          >
            {statusText}
          </span>
        </div>
      ),
      children: (
        <div className="test-scope-banner__tags">
          {group.items.map((item) => (
            <Tag
              key={item.id}
              color={item.enabled ? 'blue' : 'default'}
              className="test-scope-banner__tag"
            >
              {item.label}
              {!item.enabled ? ' · 跳过' : ''}
            </Tag>
          ))}
        </div>
      ),
    };
  });

  return (
    <Alert
      type="info"
      showIcon
      style={{ marginBottom: 16, ...style }}
      message="本次测试范围"
      description={
        <div>
          {isLegacyInferredScope(resolvedScope) && (
            <div className="test-scope-banner__legacy">
              该会话由旧版本创建，测试范围按旧版本「全部启用」规则推断。
            </div>
          )}

          <div className="test-scope-banner__toolbar">
            <div className="test-scope-banner__summary">
              共纳入 <strong>{resolvedSummary.selected_count}</strong> 项测试
              {resolvedSummary.skipped_count > 0 && (
                <>
                  ，跳过 <strong>{resolvedSummary.skipped_count}</strong> 项
                </>
              )}
              。点击大类可展开查看明细。
            </div>
            {groups.length > 0 && (
              <div className="test-scope-banner__actions">
                <Button
                  type="link"
                  size="small"
                  disabled={allExpanded}
                  onClick={() => setActiveKeys(allGroupKeys)}
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

          {groups.length > 0 ? (
            <Collapse
              className="test-scope-banner__collapse"
              bordered={false}
              expandIconPosition="end"
              size="small"
              activeKey={activeKeys}
              onChange={(keys) => setActiveKeys(Array.isArray(keys) ? keys : [keys])}
              items={collapseItems}
            />
          ) : (
            <div className="test-scope-banner__tags">
              {resolvedSummary.selected_labels.map((label) => (
                <Tag key={label} color="blue" className="test-scope-banner__tag">
                  {label}
                </Tag>
              ))}
            </div>
          )}
        </div>
      }
    />
  );
};

export default TestScopeBanner;
