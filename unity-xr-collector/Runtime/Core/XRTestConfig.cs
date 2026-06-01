using System;
using UnityEngine;

namespace XRDataCollector.Core
{
    /// <summary>
    /// 数据导出格式枚举
    /// </summary>
    public enum ExportFormat
    {
        Json,
        Csv
    }

    /// <summary>
    /// XR 测试配置类
    /// 定义测试会话的各项参数和行为
    /// </summary>
    [Serializable]
    public class XRTestConfig
    {
        /// <summary>
        /// 测试会话名称，用于标识不同的测试运行
        /// </summary>
        [Tooltip("测试会话名称")]
        public string sessionName = "XRTest";

        /// <summary>
        /// 数据采集间隔（秒），控制多久采集一次性能样本
        /// </summary>
        [Tooltip("数据采集间隔（秒）")]
        [Range(0.1f, 60f)]
        public float collectInterval = 1.0f;

        /// <summary>
        /// 是否在启动时自动开始采集
        /// </summary>
        [Tooltip("启动时自动开始采集")]
        public bool autoStart = false;

        /// <summary>
        /// 是否启用网络上传功能
        /// </summary>
        [Tooltip("启用网络数据上传")]
        public bool enableNetworkUpload = false;

        /// <summary>
        /// 数据上传的服务器地址
        /// </summary>
        [Tooltip("数据上传地址")]
        public string uploadUrl = "";

        /// <summary>
        /// 平台 API 根地址。部署到服务器后通常只需要改这里。
        /// </summary>
        [Tooltip("平台 API 根地址")]
        public string platformBaseUrl = "http://localhost:8002/api/v1";

        /// <summary>
        /// 是否由插件自动在平台创建测试会话。
        /// </summary>
        [Tooltip("自动创建平台测试会话")]
        public bool autoCreateSession = true;

        /// <summary>
        /// 自动创建会话时使用的项目 ID。
        /// </summary>
        [Tooltip("平台项目 ID")]
        public int projectId = 1;

        /// <summary>
        /// 自动创建会话时使用的场景 ID。
        /// </summary>
        [Tooltip("平台场景 ID")]
        public int sceneId = 3;

        /// <summary>
        /// 平台访问令牌。正式部署建议改为设备令牌或项目级采集令牌。
        /// </summary>
        [Tooltip("平台访问令牌（Bearer Token，可为空）")]
        public string authToken = "";

        /// <summary>
        /// 本地演示账号。正式部署建议改为采集令牌。
        /// </summary>
        [Tooltip("平台用户名")]
        public string username = "admin";

        /// <summary>
        /// 本地演示密码。正式部署建议改为采集令牌。
        /// </summary>
        [Tooltip("平台密码")]
        public string password = "Admin123!";

        /// <summary>
        /// 默认的数据导出格式
        /// </summary>
        [Tooltip("默认导出格式")]
        public ExportFormat exportFormat = ExportFormat.Json;

        /// <summary>
        /// 是否在应用退出时自动导出数据
        /// </summary>
        [Tooltip("应用退出时自动导出数据")]
        public bool autoExportOnQuit = false;

        /// <summary>
        /// 自动导出文件的路径（相对于 Application.persistentDataPath）
        /// </summary>
        [Tooltip("自动导出路径")]
        public string autoExportPath = "XRTestData";

        /// <summary>
        /// 是否采集帧率数据
        /// </summary>
        [Tooltip("采集帧率")]
        public bool collectFrameRate = true;

        /// <summary>
        /// 是否采集帧时间数据
        /// </summary>
        [Tooltip("采集帧时间")]
        public bool collectFrameTime = true;

        /// <summary>
        /// 是否采集 CPU 使用率
        /// </summary>
        [Tooltip("采集 CPU 使用率")]
        public bool collectCpuUsage = true;

        /// <summary>
        /// 是否采集 GPU 使用率
        /// </summary>
        [Tooltip("采集 GPU 使用率")]
        public bool collectGpuUsage = true;

        /// <summary>
        /// 是否采集内存使用数据
        /// </summary>
        [Tooltip("采集内存使用")]
        public bool collectMemory = true;

        /// <summary>
        /// 是否采集设备信息
        /// </summary>
        [Tooltip("采集设备信息")]
        public bool collectDeviceInfo = true;

        /// <summary>
        /// 最大样本数量限制，超过此数量将停止采集（0 表示无限制）
        /// </summary>
        [Tooltip("最大样本数（0=无限制）")]
        public int maxSamples = 0;

        /// <summary>
        /// 创建默认配置
        /// </summary>
        public XRTestConfig()
        {
        }

        /// <summary>
        /// 使用指定会话名称创建配置
        /// </summary>
        /// <param name="name">会话名称</param>
        public XRTestConfig(string name)
        {
            sessionName = name;
        }
    }
}
