using System;
using UnityEngine;

namespace XRDataCollector.Core
{
    /// <summary>
    /// XR 测试会话类
    /// 管理单个测试会话的生命周期和元数据
    /// </summary>
    [Serializable]
    public class XRTestSession
    {
        #region Fields

        private string sessionId;
        private string sessionName;
        private DateTime startTime;
        private DateTime? endTime;
        private bool isActive;

        #endregion

        #region Properties

        /// <summary>
        /// 会话唯一标识符（GUID）
        /// </summary>
        public string SessionId => sessionId;

        /// <summary>
        /// 会话名称
        /// </summary>
        public string SessionName => sessionName;

        /// <summary>
        /// 会话开始时间（UTC）
        /// </summary>
        public DateTime StartTime => startTime;

        /// <summary>
        /// 会话结束时间（UTC），如果会话仍在进行则为 null
        /// </summary>
        public DateTime? EndTime => endTime;

        /// <summary>
        /// 会话是否处于活动状态
        /// </summary>
        public bool IsActive => isActive;

        /// <summary>
        /// 会话已运行时长
        /// </summary>
        public TimeSpan ElapsedTime
        {
            get
            {
                if (!isActive && endTime.HasValue)
                {
                    return endTime.Value - startTime;
                }
                return DateTime.UtcNow - startTime;
            }
        }

        /// <summary>
        /// Unity 应用版本号
        /// </summary>
        public string UnityVersion => Application.unityVersion;

        /// <summary>
        /// 应用产品名称
        /// </summary>
        public string ProductName => Application.productName;

        /// <summary>
        /// 应用版本
        /// </summary>
        public string AppVersion => Application.version;

        /// <summary>
        /// 目标平台
        /// </summary>
        public string Platform => Application.platform.ToString();

        #endregion

        #region Constructors

        /// <summary>
        /// 创建新的测试会话
        /// </summary>
        /// <param name="name">会话名称</param>
        public XRTestSession(string name)
        {
            sessionId = Guid.NewGuid().ToString("N");
            sessionName = name ?? "UnnamedSession";
            startTime = DateTime.UtcNow;
            isActive = false;
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// 启动会话
        /// </summary>
        public void Start()
        {
            if (isActive) return;

            startTime = DateTime.UtcNow;
            endTime = null;
            isActive = true;

            Debug.Log($"[XRTestSession] Session '{sessionName}' ({sessionId}) started at {startTime:O}");
        }

        /// <summary>
        /// 停止会话
        /// </summary>
        public void Stop()
        {
            if (!isActive) return;

            endTime = DateTime.UtcNow;
            isActive = false;

            Debug.Log($"[XRTestSession] Session '{sessionName}' stopped at {endTime:O}. Duration: {ElapsedTime.TotalSeconds:F2}s");
        }

        /// <summary>
        /// 获取会话的摘要信息
        /// </summary>
        /// <returns>会话摘要字符串</returns>
        public string GetSummary()
        {
            var duration = ElapsedTime;
            var status = isActive ? "Active" : "Completed";

            return $"Session: {sessionName}\n" +
                   $"ID: {sessionId}\n" +
                   $"Status: {status}\n" +
                   $"Start: {startTime:O}\n" +
                   $"End: {endTime?.ToString("O") ?? "N/A"}\n" +
                   $"Duration: {duration.TotalSeconds:F2}s\n" +
                   $"Unity: {UnityVersion}\n" +
                   $"App: {ProductName} v{AppVersion}\n" +
                   $"Platform: {Platform}";
        }

        #endregion
    }
}
