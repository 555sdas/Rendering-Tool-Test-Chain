import React from 'react';
import { Card, Col, Descriptions, Row } from 'antd';
import type { FullReport } from '@/api/analysis';
import { getConfigNumber, getConfigString } from '@/lib/sessionConfig';

interface SessionDeviceInfoPanelProps {
  sessionInfo: FullReport['session_info'] | null | undefined;
}

const SessionDeviceInfoPanel: React.FC<SessionDeviceInfoPanelProps> = ({ sessionInfo }) => {
  if (!sessionInfo) {
    return (
      <Card>
        <div style={{ textAlign: 'center', color: '#8c8c8c', padding: 40 }}>
          暂无设备信息，请先运行测试采集
        </div>
      </Card>
    );
  }

  const reportConfig = sessionInfo.config;
  const getReportString = (keys: string[], fallback = '-') => getConfigString(reportConfig, keys, fallback);
  const getReportNumber = (keys: string[]) => getConfigNumber(reportConfig, keys);
  const unityVersion = getReportString(['unity_version', 'unityVersion'], '');
  const engineDisplay = getReportString(['engine'], unityVersion ? `Unity ${unityVersion}` : '-');
  const graphicsApiDisplay = getReportString(
    ['graphics_api', 'graphicsApi', 'graphicsDeviceType'],
    getReportString(['gpu_version', 'graphicsDeviceVersion']),
  );

  return (
    <Card>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Descriptions title="设备概况" bordered size="small" column={1}>
            <Descriptions.Item label="设备名称">
              {getReportString(['device_name', 'deviceName'], sessionInfo.device_model || '-')}
            </Descriptions.Item>
            <Descriptions.Item label="设备型号">
              {getReportString(['device_model', 'deviceModel'], sessionInfo.device_model || '-')}
            </Descriptions.Item>
            <Descriptions.Item label="操作系统">
              {getReportString(['os_version', 'operatingSystem'], sessionInfo.os_version || '-')}
            </Descriptions.Item>
            <Descriptions.Item label="屏幕分辨率">
              {getReportString(['screen_resolution', 'screenResolution'])}
            </Descriptions.Item>
            <Descriptions.Item label="运行环境">
              {getReportString(['xr_runtime', 'xrRuntime', 'runtime_mode', 'runtimeMode'], sessionInfo.xr_runtime || '-')}
            </Descriptions.Item>
            <Descriptions.Item label="应用版本">
              {getReportString(['app_version', 'appVersion'], sessionInfo.app_version || '-')}
            </Descriptions.Item>
          </Descriptions>
        </Col>
        <Col xs={24} sm={12}>
          <Descriptions title="硬件规格" bordered size="small" column={1}>
            <Descriptions.Item label="CPU 型号">
              {getReportString(['cpu_model', 'processorType'])}
            </Descriptions.Item>
            <Descriptions.Item label="CPU 核心数">
              {String(getReportNumber(['processor_count', 'processorCount']) ?? '-')}
            </Descriptions.Item>
            <Descriptions.Item label="GPU 型号">
              {getReportString(['gpu_model', 'graphicsDeviceName'])}
            </Descriptions.Item>
            <Descriptions.Item label="GPU 厂商">
              {getReportString(['gpu_vendor', 'graphicsDeviceVendor'])}
            </Descriptions.Item>
            <Descriptions.Item label="GPU 驱动版本">
              {getReportString(['gpu_version', 'graphicsDeviceVersion'])}
            </Descriptions.Item>
            <Descriptions.Item label="显存">
              {getReportNumber(['gpu_memory_mb', 'graphicsMemorySize']) != null
                ? `${getReportNumber(['gpu_memory_mb', 'graphicsMemorySize'])} MB`
                : '-'}
            </Descriptions.Item>
          </Descriptions>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12}>
          <Descriptions title="内存与引擎" bordered size="small" column={1}>
            <Descriptions.Item label="系统内存">
              {getReportNumber(['system_memory_mb', 'systemMemorySize']) != null
                ? `${getReportNumber(['system_memory_mb', 'systemMemorySize'])} MB`
                : getReportNumber(['ram_gb']) != null
                  ? `${getReportNumber(['ram_gb'])} GB`
                  : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="Unity 版本">
              {engineDisplay}
            </Descriptions.Item>
            <Descriptions.Item label="图形 API">
              {graphicsApiDisplay}
            </Descriptions.Item>
            <Descriptions.Item label="渲染管线">
              {getReportString(['render_pipeline', 'renderPipeline'])}
            </Descriptions.Item>
            <Descriptions.Item label="XR 设备名称">
              {getReportString(['xr_device_name', 'xrDeviceName'])}
            </Descriptions.Item>
            <Descriptions.Item label="样本数">
              {String(getReportNumber(['sample_count', 'sampleCount']) ?? '-')}
            </Descriptions.Item>
          </Descriptions>
        </Col>
      </Row>
    </Card>
  );
};

export default SessionDeviceInfoPanel;
