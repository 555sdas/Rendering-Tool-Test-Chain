using UnityEngine;
using UnityEngine.XR;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 设备信息采集器
    /// 采集 XR 设备和运行环境的相关信息
    /// </summary>
    public class DeviceInfoCollector : IPerformanceCollector
    {
        #region Fields

        private DeviceInfo cachedDeviceInfo;
        private bool isXrActive;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "DeviceInfo";

        /// <summary>
        /// 开始采集，缓存设备信息
        /// </summary>
        public void StartCollecting()
        {
            cachedDeviceInfo = GatherDeviceInfo();
            isXrActive = XRSettings.isDeviceActive;
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集设备信息
        /// 将设备信息附加到性能样本中
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            if (cachedDeviceInfo == null)
            {
                cachedDeviceInfo = GatherDeviceInfo();
            }

            sample.deviceInfo = cachedDeviceInfo;
            sample.isXrActive = XRSettings.isDeviceActive;
            sample.xrDeviceName = XRSettings.loadedDeviceName;
        }

        #endregion

        #region Private Methods

        private DeviceInfo GatherDeviceInfo()
        {
            var info = new DeviceInfo
            {
                deviceModel = SystemInfo.deviceModel,
                deviceName = SystemInfo.deviceName,
                deviceType = SystemInfo.deviceType.ToString(),
                operatingSystem = SystemInfo.operatingSystem,
                unityVersion = Application.unityVersion,
                applicationPlatform = Application.platform.ToString(),
                runtimeMode = Application.isEditor ? "Unity Editor" : "Unity Player",
                renderPipeline = GetRenderPipelineName(),
                processorType = SystemInfo.processorType,
                processorCount = SystemInfo.processorCount,
                systemMemorySize = SystemInfo.systemMemorySize,
                graphicsDeviceName = SystemInfo.graphicsDeviceName,
                graphicsDeviceVendor = SystemInfo.graphicsDeviceVendor,
                graphicsDeviceVersion = SystemInfo.graphicsDeviceVersion,
                graphicsDeviceType = SystemInfo.graphicsDeviceType.ToString(),
                graphicsMemorySize = SystemInfo.graphicsMemorySize,
                graphicsShaderLevel = SystemInfo.graphicsShaderLevel,
                maxTextureSize = SystemInfo.maxTextureSize,
                supportsVr = SystemInfo.supportsVibration,
                xrDeviceActive = XRSettings.isDeviceActive,
                xrDeviceName = XRSettings.loadedDeviceName,
                xrRenderViewportScale = XRSettings.renderViewportScale,
                screenResolution = $"{Screen.currentResolution.width}x{Screen.currentResolution.height}",
                screenDpi = Screen.dpi,
                targetFrameRate = Application.targetFrameRate
            };

            return info;
        }

        private string GetRenderPipelineName()
        {
            var pipeline = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline;
            return pipeline != null ? pipeline.GetType().Name : "Built-in Render Pipeline";
        }

        #endregion
    }
}
