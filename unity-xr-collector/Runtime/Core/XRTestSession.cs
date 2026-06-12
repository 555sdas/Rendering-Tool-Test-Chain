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
        private long startTimeUtcTicks;
        private long endTimeUtcTicks;
        private bool isActive;
        private int platformSessionId;
        private int platformRunIndex;

        #endregion

        #region Properties

        public string SessionId => sessionId;
        public string SessionName => sessionName;
        public int PlatformSessionId => platformSessionId;
        public int PlatformRunIndex => platformRunIndex;
        public DateTime StartTime => startTimeUtcTicks > 0
            ? new DateTime(startTimeUtcTicks, DateTimeKind.Utc)
            : startTime;
        public DateTime? EndTime => endTimeUtcTicks > 0
            ? new DateTime(endTimeUtcTicks, DateTimeKind.Utc)
            : endTime;
        public bool IsActive => isActive;

        public TimeSpan ElapsedTime
        {
            get
            {
                var effectiveStart = StartTime;
                var effectiveEnd = EndTime;
                if (!isActive && effectiveEnd.HasValue)
                    return effectiveEnd.Value - effectiveStart;
                return DateTime.UtcNow - effectiveStart;
            }
        }

        public string UnityVersion => Application.unityVersion;
        public string ProductName => Application.productName;
        public string AppVersion => Application.version;
        public string Platform => Application.platform.ToString();

        #endregion

        #region Constructors

        public XRTestSession(string name)
        {
            sessionId = Guid.NewGuid().ToString("N");
            sessionName = name ?? "未命名会话";
            startTime = DateTime.UtcNow;
            startTimeUtcTicks = startTime.Ticks;
            isActive = false;
        }

        #endregion

        #region Public Methods

        public void Start()
        {
            if (isActive) return;
            startTime = DateTime.UtcNow;
            startTimeUtcTicks = startTime.Ticks;
            endTime = null;
            endTimeUtcTicks = 0;
            isActive = true;
            Debug.Log($"[XRTestSession] 会话 '{sessionName}' ({sessionId}) 开始于 {startTime:O}");
        }

        public void Stop()
        {
            if (!isActive) return;
            endTime = DateTime.UtcNow;
            endTimeUtcTicks = endTime.Value.Ticks;
            isActive = false;
            Debug.Log($"[XRTestSession] 会话 '{sessionName}' 结束于 {endTime:O}，时长：{ElapsedTime.TotalSeconds:F2}秒");
        }

        public void BindPlatformSession(int sessionId, int runIndex, string platformSessionName)
        {
            platformSessionId = sessionId;
            platformRunIndex = runIndex;
            if (!string.IsNullOrEmpty(platformSessionName))
                sessionName = platformSessionName;
            Debug.Log($"[XRTestSession] 本地会话已绑定到平台会话 {platformSessionId}，运行 #{platformRunIndex}。");
        }

        public string GetSummary()
        {
            var duration = ElapsedTime;
            var status = isActive ? "进行中" : "已完成";
            return $"会话：{sessionName}\n" +
                   $"ID：{sessionId}\n" +
                   $"平台会话 ID：{(platformSessionId > 0 ? platformSessionId.ToString() : "无")}\n" +
                   $"状态：{status}\n" +
                   $"开始：{StartTime:O}\n" +
                   $"结束：{EndTime?.ToString("O") ?? "无"}\n" +
                   $"时长：{duration.TotalSeconds:F2}秒\n" +
                   $"Unity：{UnityVersion}\n" +
                   $"应用：{ProductName} v{AppVersion}\n" +
                   $"平台：{Platform}";
        }

        #endregion
    }
}
