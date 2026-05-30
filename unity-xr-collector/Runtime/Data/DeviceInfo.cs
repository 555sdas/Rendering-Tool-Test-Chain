using System;

namespace XRDataCollector.Data
{
    /// <summary>
    /// 设备信息数据结构
    /// 存储 XR 设备和运行环境的硬件信息
    /// </summary>
    [Serializable]
    public class DeviceInfo
    {
        #region Basic Device Info

        /// <summary>
        /// 设备型号
        /// </summary>
        public string deviceModel;

        /// <summary>
        /// 设备名称
        /// </summary>
        public string deviceName;

        /// <summary>
        /// 设备类型（Desktop、Handheld 等）
        /// </summary>
        public string deviceType;

        /// <summary>
        /// 操作系统版本
        /// </summary>
        public string operatingSystem;

        #endregion

        #region Processor Info

        /// <summary>
        /// 处理器型号
        /// </summary>
        public string processorType;

        /// <summary>
        /// 处理器核心数
        /// </summary>
        public int processorCount;

        /// <summary>
        /// 系统内存大小（MB）
        /// </summary>
        public int systemMemorySize;

        #endregion

        #region Graphics Info

        /// <summary>
        /// 显卡名称
        /// </summary>
        public string graphicsDeviceName;

        /// <summary>
        /// 显卡厂商
        /// </summary>
        public string graphicsDeviceVendor;

        /// <summary>
        /// 显卡驱动版本
        /// </summary>
        public string graphicsDeviceVersion;

        /// <summary>
        /// 显存大小（MB）
        /// </summary>
        public int graphicsMemorySize;

        /// <summary>
        /// 着色器模型等级
        /// </summary>
        public int graphicsShaderLevel;

        /// <summary>
        /// 最大纹理尺寸
        /// </summary>
        public int maxTextureSize;

        #endregion

        #region XR Info

        /// <summary>
        /// 是否支持 VR/AR
        /// </summary>
        public bool supportsVr;

        /// <summary>
        /// XR 设备是否处于活动状态
        /// </summary>
        public bool xrDeviceActive;

        /// <summary>
        /// XR 设备名称
        /// </summary>
        public string xrDeviceName;

        /// <summary>
        /// XR 渲染视口缩放比例
        /// </summary>
        public float xrRenderViewportScale;

        #endregion

        #region Display Info

        /// <summary>
        /// 屏幕分辨率（格式：宽x高）
        /// </summary>
        public string screenResolution;

        /// <summary>
        /// 屏幕 DPI
        /// </summary>
        public float screenDpi;

        /// <summary>
        /// 目标帧率
        /// </summary>
        public int targetFrameRate;

        #endregion

        #region Methods

        /// <summary>
        /// 获取设备信息的摘要
        /// </summary>
        /// <returns>设备信息摘要字符串</returns>
        public string GetSummary()
        {
            return $"Device: {deviceModel}\n" +
                   $"OS: {operatingSystem}\n" +
                   $"CPU: {processorType} ({processorCount} cores)\n" +
                   $"RAM: {systemMemorySize}MB\n" +
                   $"GPU: {graphicsDeviceName}\n" +
                   $"VRAM: {graphicsMemorySize}MB\n" +
                   $"Screen: {screenResolution} @ {screenDpi:F0} DPI\n" +
                   $"XR: {xrDeviceName} (Active: {xrDeviceActive})";
        }

        #endregion
    }
}
