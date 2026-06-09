using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Data;
using XRDataCollector.Exporters;
using XRDataCollector.Network;

namespace XRDataCollector.Editor
{
    public class XRTestWindow : EditorWindow
    {
        #region Fields

        private Vector2 scrollPosition;
        private string exportPath = "";
        private string uploadUrl = "";
        private string authToken = "";
        private bool showSessionInfo = true;
        private bool showLatestSample = true;
        private bool showSettings = false;
        private string statusMessage = "";
        private MessageType statusType = MessageType.None;
        private float statusClearTime;
        private readonly List<PlatformProject> platformProjects = new List<PlatformProject>();
        private int selectedProjectIndex = -1;
        private bool isProjectSyncing;
        private double lastRepaintTime;
        private readonly List<LogEntry> logEntries = new List<LogEntry>();
        private Vector2 logScrollPosition;
        private const int MaxLogEntries = 200;

        private const float StatusDisplayDuration = 5f;
        private const string PendingStartAfterPlayModeKey = "XRDataCollector.PendingStartAfterPlayMode";

        private struct LogEntry
        {
            public string message;
            public MessageType type;
            public string timestamp;
        }

        #endregion

        private XRTestManager GetManager()
        {
            return XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
        }

        #region Menu Item

        public static void ShowWindow()
        {
            var window = GetWindow<XRTestWindow>("XR 测试");
            window.minSize = new Vector2(400, 500);
            window.Show();
        }

        #endregion

        #region Unity Editor Lifecycle

        private void OnEnable()
        {
            exportPath = Path.Combine(Application.persistentDataPath, "XRTestData");
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.update += OnEditorUpdate;

            var manager = GetManager();
            if (manager != null)
            {
                if (manager.Config != null)
                {
                    uploadUrl = manager.Config.uploadUrl;
                }

                manager.OnSampleCollected += OnSampleCollected;
                manager.OnSessionStarted += OnSessionStarted;
                manager.OnSessionStopped += OnSessionStopped;
                manager.OnDataExported += OnDataExported;
                manager.OnDataUploaded += OnDataUploaded;
                manager.OnPlatformSessionCreated += OnPlatformSessionCreated;
            }
        }

        private void OnDisable()
        {
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.update -= OnEditorUpdate;

            var manager = GetManager();
            if (manager != null)
            {
                manager.OnSampleCollected -= OnSampleCollected;
                manager.OnSessionStarted -= OnSessionStarted;
                manager.OnSessionStopped -= OnSessionStopped;
                manager.OnDataExported -= OnDataExported;
                manager.OnDataUploaded -= OnDataUploaded;
                manager.OnPlatformSessionCreated -= OnPlatformSessionCreated;
            }
        }

        private void Update()
        {
            if (!string.IsNullOrEmpty(statusMessage) && Time.realtimeSinceStartup > statusClearTime)
            {
                statusMessage = "";
                statusType = MessageType.None;
                Repaint();
            }
        }

        private void OnEditorUpdate()
        {
            if (!Application.isPlaying) return;
            if (EditorApplication.timeSinceStartup - lastRepaintTime < 0.5) return;
            lastRepaintTime = EditorApplication.timeSinceStartup;
            Repaint();
        }

        #endregion

        #region GUI

        private void OnGUI()
        {
            EditorGUILayout.Space(10);
            DrawHeader();
            EditorGUILayout.Space(5);

            DrawCollectionProgress();
            EditorGUILayout.Space(5);

            scrollPosition = EditorGUILayout.BeginScrollView(scrollPosition);

            DrawControlPanel();
            EditorGUILayout.Space(10);

            DrawSessionInfo();
            EditorGUILayout.Space(10);

            DrawLatestSample();
            EditorGUILayout.Space(10);

            DrawExportPanel();
            EditorGUILayout.Space(10);

            DrawUploadPanel();
            EditorGUILayout.Space(10);

            DrawSettings();
            EditorGUILayout.Space(10);

            DrawLogArea();

            EditorGUILayout.EndScrollView();

            DrawStatusBar();
        }

        #endregion

        #region Draw Methods

        private void DrawCollectionProgress()
        {
            var manager = GetManager();
            if (manager == null || !manager.IsCollecting) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("采集进度", EditorStyles.boldLabel);

            float progress = manager.CollectionProgress;
            Rect rect = EditorGUILayout.GetControlRect(false, 20);
            EditorGUI.ProgressBar(rect, progress, $"{(progress * 100f):F0}%");

            EditorGUILayout.LabelField($"{manager.CurrentCollectionPhase}剩余：{manager.CurrentPhaseRemainingSeconds:F1} 秒");
            EditorGUILayout.EndVertical();
        }

        private void DrawLogArea()
        {
            EditorGUILayout.LabelField("日志", EditorStyles.boldLabel);
            logScrollPosition = EditorGUILayout.BeginScrollView(logScrollPosition, GUILayout.Height(150));

            foreach (var entry in logEntries)
            {
                var style = new GUIStyle(EditorStyles.label)
                {
                    normal = { textColor = GetLogColor(entry.type) }
                };
                EditorGUILayout.LabelField($"[{entry.timestamp}] {entry.message}", style);
            }

            if (logEntries.Count == 0)
            {
                EditorGUILayout.HelpBox("暂无日志。", MessageType.Info);
            }

            EditorGUILayout.EndScrollView();
        }

        private void AddLog(string message, MessageType type)
        {
            logEntries.Insert(0, new LogEntry
            {
                message = message,
                type = type,
                timestamp = DateTime.Now.ToString("HH:mm:ss")
            });

            if (logEntries.Count > MaxLogEntries)
            {
                logEntries.RemoveAt(logEntries.Count - 1);
            }

            Repaint();
        }

        private Color GetLogColor(MessageType type)
        {
            switch (type)
            {
                case MessageType.Error:
                    return Color.red;
                case MessageType.Warning:
                    return Color.yellow;
                case MessageType.Info:
                default:
                    return Color.white;
            }
        }

        private void DrawHeader()
        {
            GUIStyle headerStyle = new GUIStyle(EditorStyles.largeLabel)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 18,
                fontStyle = FontStyle.Bold
            };

            EditorGUILayout.LabelField("XR 数据采集器", headerStyle, GUILayout.Height(30));

            GUIStyle subHeaderStyle = new GUIStyle(EditorStyles.label)
            {
                alignment = TextAnchor.MiddleCenter
            };

            EditorGUILayout.LabelField("性能测试与数据采集", subHeaderStyle);
        }

        private void DrawControlPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("控制面板", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            var manager = GetManager();
            bool isCollecting = manager != null && manager.IsCollecting;

            EditorGUILayout.BeginHorizontal();

            GUI.enabled = !isCollecting;
            if (GUILayout.Button("开始采集", GUILayout.Height(40)))
            {
                StartCollection();
            }
            GUI.enabled = true;

            GUI.enabled = isCollecting;
            if (GUILayout.Button("停止采集", GUILayout.Height(40)))
            {
                StopCollection();
            }
            GUI.enabled = true;

            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space(5);

            GUIStyle statusStyle = new GUIStyle(EditorStyles.label)
            {
                alignment = TextAnchor.MiddleCenter,
                fontStyle = FontStyle.Bold
            };

            string statusText = isCollecting ? "采集中..." : "空闲";
            Color statusColor = isCollecting ? Color.green : Color.gray;

            GUI.color = statusColor;
            EditorGUILayout.LabelField($"状态：{statusText}", statusStyle);
            GUI.color = Color.white;

            if (manager != null)
            {
                EditorGUILayout.LabelField($"已采集样本数：{manager.GetSampleCount()}");
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawSessionInfo()
        {
            showSessionInfo = EditorGUILayout.Foldout(showSessionInfo, "会话信息", true, EditorStyles.foldoutHeader);
            if (!showSessionInfo) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null && manager.Session != null)
            {
                var session = manager.Session;

                EditorGUILayout.LabelField("会话名称：", session.SessionName);
                EditorGUILayout.LabelField("会话 ID：", session.SessionId);
                EditorGUILayout.LabelField("平台会话 ID：", session.PlatformSessionId > 0 ? session.PlatformSessionId.ToString() : "尚未同步");
                EditorGUILayout.LabelField("运行索引：", session.PlatformRunIndex > 0 ? session.PlatformRunIndex.ToString() : "-");
                EditorGUILayout.LabelField("开始时间：", session.StartTime.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss"));
                EditorGUILayout.LabelField("已运行时长：", $"{session.ElapsedTime.TotalSeconds:F2} 秒");
                EditorGUILayout.LabelField("状态：", session.IsActive ? "进行中" : "已停止");
                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("Unity 版本：", session.UnityVersion);
                EditorGUILayout.LabelField("产品名称：", session.ProductName);
                EditorGUILayout.LabelField("应用版本：", session.AppVersion);
                EditorGUILayout.LabelField("目标平台：", session.Platform);
            }
            else
            {
                EditorGUILayout.HelpBox("暂无活动会话。开始采集后即可查看会话信息。", MessageType.Info);
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawLatestSample()
        {
            showLatestSample = EditorGUILayout.Foldout(showLatestSample, "最新样本", true, EditorStyles.foldoutHeader);
            if (!showLatestSample) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null)
            {
                var sample = manager.GetLatestSample();

                if (sample != null)
                {
                    EditorGUILayout.LabelField("时间戳：", sample.timestamp.ToLocalTime().ToString("HH:mm:ss.fff"));
                    EditorGUILayout.LabelField("阶段：", sample.collectionPhase ?? "-");
                    EditorGUILayout.LabelField("帧率：", $"{sample.frameRate:F1} FPS");
                    EditorGUILayout.LabelField("帧时间：", $"{sample.frameTimeMs:F2} 毫秒");
                    EditorGUILayout.LabelField("CPU 占用：", $"{sample.cpuUsagePercent:F1} %");
                    EditorGUILayout.LabelField("GPU 占用：", $"{sample.gpuUsagePercent:F1} %");
                    EditorGUILayout.LabelField("Draw Calls：", sample.drawCalls.ToString());
                    EditorGUILayout.LabelField("三角面数：", sample.triangles.ToString());
                    EditorGUILayout.LabelField("总内存：", $"{sample.totalMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("托管内存：", $"{sample.managedMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("显存：", $"{sample.graphicsMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("XR 激活：", sample.isXrActive.ToString());
                    EditorGUILayout.LabelField("XR 设备：", sample.xrDeviceName ?? "无");
                }
                else
                {
                    EditorGUILayout.HelpBox("尚未采集样本。", MessageType.Info);
                }
            }
            else
            {
                EditorGUILayout.HelpBox("场景中未找到 XRTestManager。请通过 XR 测试 → 设置 → 创建 XRTestManager 来添加。", MessageType.Warning);
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawExportPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("导出数据", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            EditorGUILayout.BeginHorizontal();
            exportPath = EditorGUILayout.TextField("导出路径：", exportPath);
            if (GUILayout.Button("浏览", GUILayout.Width(60)))
            {
                string selectedPath = EditorUtility.SaveFolderPanel("选择导出目录", exportPath, "");
                if (!string.IsNullOrEmpty(selectedPath))
                {
                    exportPath = selectedPath;
                }
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space(5);

            EditorGUILayout.BeginHorizontal();

            if (GUILayout.Button("导出为 JSON"))
            {
                ExportData(ExportFormat.Json);
            }

            if (GUILayout.Button("导出为 CSV"))
            {
                ExportData(ExportFormat.Csv);
            }

            EditorGUILayout.EndHorizontal();

            EditorGUILayout.EndVertical();
        }

        private void DrawUploadPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("平台同步", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            var manager = GetManager();
            if (manager != null && manager.Config != null)
            {
                EditorGUILayout.LabelField("平台地址：", manager.Config.platformBaseUrl);
                EditorGUILayout.LabelField("模式：", manager.Config.autoCreateSession ? "自动创建会话并上传" : "上传到指定地址");
                DrawProjectSyncControls(manager);
            }
            else
            {
                EditorGUILayout.HelpBox("未找到 XRTestManager。请通过 XR 测试 → 设置 → 创建 XRTestManager 来添加。", MessageType.Info);
            }

            EditorGUILayout.Space(5);

            GUI.enabled = manager != null;
            if (GUILayout.Button("上传/同步到平台", GUILayout.Height(32)))
            {
                UploadData();
            }
            GUI.enabled = true;

            EditorGUILayout.EndVertical();
        }

        private void DrawProjectSyncControls(XRTestManager manager)
        {
            var config = manager.Config;

            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField("项目同步", EditorStyles.boldLabel);

            EditorGUILayout.BeginHorizontal();
            GUI.enabled = !isProjectSyncing;
            if (GUILayout.Button(isProjectSyncing ? "刷新中..." : "刷新项目列表", GUILayout.Height(24)))
            {
                RefreshPlatformProjects();
            }
            GUI.enabled = true;
            EditorGUILayout.EndHorizontal();

            if (platformProjects.Count > 0)
            {
                SyncSelectedProjectIndex(config);

                string[] options = new string[platformProjects.Count];
                for (int i = 0; i < platformProjects.Count; i++)
                {
                    options[i] = platformProjects[i].DisplayName;
                }

                int currentIndex = selectedProjectIndex >= 0 ? selectedProjectIndex : 0;
                int newIndex = EditorGUILayout.Popup("项目：", currentIndex, options);
                if (newIndex != selectedProjectIndex)
                {
                    SelectPlatformProject(manager, newIndex);
                }
            }
            else
            {
                string projectLabel = string.IsNullOrEmpty(config.projectName)
                    ? $"项目 ID {config.projectId}"
                    : $"{config.projectName} (ID {config.projectId})";
                EditorGUILayout.LabelField("当前项目：", projectLabel);
                EditorGUILayout.HelpBox("在管理后台创建项目后，点击「刷新项目列表」获取。", MessageType.Info);
            }

            if (config.projectId <= 0)
            {
                EditorGUILayout.HelpBox("请先选择项目再开始同步采集。", MessageType.Warning);
            }

            if (manager.PlatformSessionId > 0)
            {
                EditorGUILayout.LabelField("平台会话 ID：", manager.PlatformSessionId.ToString());
            }
        }

        private void DrawSettings()
        {
            showSettings = EditorGUILayout.Foldout(showSettings, "设置", true, EditorStyles.foldoutHeader);
            if (!showSettings) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null && manager.Config != null)
            {
                var config = manager.Config;

                EditorGUI.BeginChangeCheck();

                config.sessionName = EditorGUILayout.TextField("会话名称：", config.sessionName);
                config.collectInterval = EditorGUILayout.Slider("采集间隔（秒）：", config.collectInterval, 0.1f, 10f);
                config.autoStart = EditorGUILayout.Toggle("启动时自动采集：", config.autoStart);
                config.autoExportOnQuit = EditorGUILayout.Toggle("退出时自动导出：", config.autoExportOnQuit);
                config.enableNetworkUpload = EditorGUILayout.Toggle("启用网络上传：", config.enableNetworkUpload);

                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("平台同步", EditorStyles.boldLabel);
                config.platformBaseUrl = EditorGUILayout.TextField("平台 API 地址：", config.platformBaseUrl);
                config.autoCreateSession = EditorGUILayout.Toggle("自动创建会话：", config.autoCreateSession);
                config.projectId = EditorGUILayout.IntField("项目 ID：", config.projectId);
                config.projectName = EditorGUILayout.TextField("项目名称：", config.projectName);
                config.sceneId = EditorGUILayout.IntField("场景 ID：", config.sceneId);
                config.uploadUrl = EditorGUILayout.TextField("固定上传地址：", config.uploadUrl);
                config.deviceToken = EditorGUILayout.PasswordField("设备令牌：", config.deviceToken);
                config.username = EditorGUILayout.TextField("用户名：", config.username);
                config.password = EditorGUILayout.PasswordField("密码：", config.password);

                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("采集器", EditorStyles.boldLabel);

                config.collectFrameRate = EditorGUILayout.Toggle("帧率：", config.collectFrameRate);
                config.collectFrameTime = EditorGUILayout.Toggle("帧时间：", config.collectFrameTime);
                config.collectCpuUsage = EditorGUILayout.Toggle("CPU 占用：", config.collectCpuUsage);
                config.collectGpuUsage = EditorGUILayout.Toggle("GPU 占用：", config.collectGpuUsage);
                config.collectMemory = EditorGUILayout.Toggle("内存：", config.collectMemory);
                config.collectDeviceInfo = EditorGUILayout.Toggle("设备信息：", config.collectDeviceInfo);

                if (EditorGUI.EndChangeCheck())
                {
                    EditorUtility.SetDirty(manager);
                }
            }
            else
            {
                EditorGUILayout.HelpBox("未找到 XRTestManager。请通过 XR 测试 → 设置 → 创建 XRTestManager 来添加。", MessageType.Info);
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawStatusBar()
        {
            if (!string.IsNullOrEmpty(statusMessage))
            {
                EditorGUILayout.Space(5);
                EditorGUILayout.HelpBox(statusMessage, statusType);
            }
        }

        #endregion

        #region Actions

        private void StartCollection()
        {
            if (!EditorApplication.isPlaying)
            {
                SessionState.SetBool(PendingStartAfterPlayModeKey, true);
                EditorApplication.isPlaying = true;
                ShowStatus("正在进入运行模式，采集将自动开始。", MessageType.Info);
                return;
            }

            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("未找到 XRTestManager，请将其添加到场景中的 GameObject 上。", MessageType.Error);
                return;
            }

            if (manager.Config != null &&
                manager.Config.enableNetworkUpload &&
                manager.Config.autoCreateSession &&
                manager.Config.projectId <= 0)
            {
                ShowStatus("请先选择项目再开始同步采集。", MessageType.Error);
                return;
            }

            manager.StartCollection();
        }

        private void StopCollection()
        {
            var manager = GetManager();
            if (manager == null) return;
            manager.StopCollection();
            AddLog("手动停止采集", MessageType.Info);
        }

        private void ExportData(ExportFormat format)
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("未找到 XRTestManager。", MessageType.Error);
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                ShowStatus("没有可导出的样本。", MessageType.Error);
                return;
            }

            string extension = format == ExportFormat.Json ? "json" : "csv";
            string defaultName = $"XRTest_{DateTime.Now:yyyyMMdd_HHmmss}.{extension}";
            string filePath = EditorUtility.SaveFilePanel(
                $"导出为 {format}",
                exportPath,
                defaultName,
                extension
            );

            if (string.IsNullOrEmpty(filePath)) return;

            try
            {
                IDataExporter exporter = format == ExportFormat.Json
                    ? new Exporters.JsonExporter()
                    : new Exporters.CsvExporter();

                manager.ExportData(exporter, filePath);
                ShowStatus($"数据已导出至：{filePath}", MessageType.Info);
            }
            catch (Exception e)
            {
                ShowStatus($"导出失败：{e.Message}", MessageType.Error);
            }
        }

        private void UploadData()
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("未找到 XRTestManager。", MessageType.Error);
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                ShowStatus("没有可上传的样本。", MessageType.Error);
                return;
            }

            AddLog("正在上传数据到平台...", MessageType.Info);
            manager.UploadData("");
        }

        private void RefreshPlatformProjects()
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("XRTestManager 未找到。", MessageType.Error);
                return;
            }

            if (isProjectSyncing) return;

            isProjectSyncing = true;
            ShowStatus("正在刷新平台项目列表...", MessageType.Info);

            if (!EditorApplication.isPlaying)
            {
                try
                {
                    var projects = LoadProjectsInEditor(manager.Config);
                    ApplyLoadedProjects(manager, projects);
                    ShowStatus($"已加载 {platformProjects.Count} 个平台项目。", MessageType.Info);
                }
                catch (Exception e)
                {
                    ShowStatus($"刷新项目列表失败：{e.Message}", MessageType.Error);
                }
                finally
                {
                    isProjectSyncing = false;
                    Repaint();
                }
                return;
            }

            var uploader = new TestDataUploader();
            uploader.LoadProjectsAsync(manager.Config, (projects, error) =>
            {
                isProjectSyncing = false;
                if (!string.IsNullOrEmpty(error))
                {
                    ShowStatus(error, MessageType.Error);
                    Repaint();
                    return;
                }
                ApplyLoadedProjects(manager, projects);
                ShowStatus($"已加载 {platformProjects.Count} 个平台项目。", MessageType.Info);
                Repaint();
            });
        }

        #endregion

        #region Event Handlers

        private void OnSampleCollected(PerformanceSample sample)
        {
            var manager = GetManager();
            int count = manager != null ? manager.GetSampleCount() : 0;
            if (count % 10 == 0)
                AddLog($"已采集 {count} 个样本", MessageType.Info);
            Repaint();
        }

        private void OnSessionStarted()
        {
            AddLog("采集会话已开始（前30秒：帧率采集，后30秒：指标采集）", MessageType.Info);
            Repaint();
        }

        private void OnSessionStopped()
        {
            var manager = GetManager();
            int count = manager != null ? manager.GetSampleCount() : 0;
            AddLog($"采集会话已停止，共采集 {count} 个样本", MessageType.Info);
            Repaint();
        }

        private void OnDataExported(string path)
        {
            AddLog($"数据已导出至：{path}", MessageType.Info);
            Repaint();
        }

        private void OnDataUploaded(bool success)
        {
            if (success)
                AddLog("数据上传成功", MessageType.Info);
            else
                AddLog("数据上传失败", MessageType.Error);
            Repaint();
        }

        private void OnPlatformSessionCreated(int sessionId)
        {
            AddLog($"平台会话 {sessionId} 已创建", MessageType.Info);
            Repaint();
        }

        private void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.EnteredPlayMode)
            {
                AddLog("进入运行模式", MessageType.Info);
            }
            else if (state == PlayModeStateChange.ExitingPlayMode)
            {
                AddLog("退出运行模式", MessageType.Info);
            }

            if (state != PlayModeStateChange.EnteredPlayMode) return;
            if (!SessionState.GetBool(PendingStartAfterPlayModeKey, false)) return;

            SessionState.SetBool(PendingStartAfterPlayModeKey, false);
            EditorApplication.delayCall += StartPendingCollection;
        }

        private void StartPendingCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("进入运行模式后未找到 XRTestManager。", MessageType.Error);
                return;
            }
            manager.StartCollection();
        }

        #endregion

        #region Helpers

        private void ShowStatus(string message, MessageType type)
        {
            statusMessage = message;
            statusType = type;
            statusClearTime = Time.realtimeSinceStartup + StatusDisplayDuration;
            AddLog(message, type);
            Repaint();
        }

        private void SyncSelectedProjectIndex(XRTestConfig config)
        {
            selectedProjectIndex = -1;
            if (config == null) return;

            for (int i = 0; i < platformProjects.Count; i++)
            {
                if (platformProjects[i].id == config.projectId)
                {
                    selectedProjectIndex = i;
                    return;
                }
            }
        }

        private void ApplyLoadedProjects(XRTestManager manager, List<PlatformProject> projects)
        {
            platformProjects.Clear();
            if (projects != null)
                platformProjects.AddRange(projects);

            SyncSelectedProjectIndex(manager.Config);
            if (selectedProjectIndex < 0 && platformProjects.Count > 0)
                SelectPlatformProject(manager, 0);

            EditorUtility.SetDirty(manager);
        }

        private List<PlatformProject> LoadProjectsInEditor(XRTestConfig config)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
                throw new InvalidOperationException("平台 API 地址为空。");

            if (string.IsNullOrEmpty(authToken))
            {
                authToken = DeviceTokenLoginInEditor(baseUrl, config.deviceToken);
                if (string.IsNullOrEmpty(authToken))
                    authToken = LoginInEditor(baseUrl, config.username, config.password);
            }

            if (string.IsNullOrEmpty(authToken))
                throw new InvalidOperationException("平台登录失败，请检查平台地址、设备令牌或用户名密码。");

            string json = SendEditorRequest("GET", $"{baseUrl}/data-collection/platform/projects?limit=100", null, null, authToken);
            return ParseProjectList(json);
        }

        private string DeviceTokenLoginInEditor(string baseUrl, string deviceToken)
        {
            if (string.IsNullOrEmpty(deviceToken))
                return null;

            string body = "{\"device_token\":\"" + Uri.EscapeDataString(deviceToken ?? "") + "\"}";
            try
            {
                string json = SendEditorRequest("POST", $"{baseUrl}/auth/device-token/login",
                    "application/json", body, null);
                return ExtractStringField(json, "access_token");
            }
            catch (WebException)
            {
                return null;
            }
        }

        private string LoginInEditor(string baseUrl, string username, string password)
        {
            string body = "username=" + Uri.EscapeDataString(username ?? "") +
                          "&password=" + Uri.EscapeDataString(password ?? "");
            try
            {
                string json = SendEditorRequest("POST", $"{baseUrl}/auth/login",
                    "application/x-www-form-urlencoded", body, null);
                return ExtractStringField(json, "access_token");
            }
            catch (WebException)
            {
                return null;
            }
        }

        private string SendEditorRequest(string method, string url, string contentType, string body, string token)
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = method;
            request.Timeout = 30000;

            if (!string.IsNullOrEmpty(token))
                request.Headers["Authorization"] = "Bearer " + token;

            if (!string.IsNullOrEmpty(body))
            {
                byte[] raw = Encoding.UTF8.GetBytes(body);
                request.ContentType = contentType ?? "application/json";
                request.ContentLength = raw.Length;
                using (var stream = request.GetRequestStream())
                    stream.Write(raw, 0, raw.Length);
            }

            using (var response = (HttpWebResponse)request.GetResponse())
            using (var reader = new StreamReader(response.GetResponseStream()))
            {
                return reader.ReadToEnd();
            }
        }

        private List<PlatformProject> ParseProjectList(string json)
        {
            var response = JsonUtility.FromJson<PlatformProjectListResponse>(json);
            return response != null && response.items != null
                ? response.items
                : new List<PlatformProject>();
        }

        private string NormalizeBaseUrl(string value)
        {
            return XRTestConfig.NormalizePlatformBaseUrl(value);
        }

        private string ExtractStringField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*\"([^\"]+)\"");
            return match.Success ? match.Groups[1].Value : null;
        }

        private void SelectPlatformProject(XRTestManager manager, int index)
        {
            if (manager == null || manager.Config == null || index < 0 || index >= platformProjects.Count)
                return;

            var project = platformProjects[index];
            selectedProjectIndex = index;
            manager.Config.projectId = project.id;
            manager.Config.projectName = project.name;
            manager.Config.sessionName = string.IsNullOrEmpty(project.name) ? "Unity Test" : project.name + " Unity Test";

            EditorUtility.SetDirty(manager);
            ShowStatus($"已选择项目 {project.name}（下次会话 #{project.next_session_index}）。", MessageType.Info);
            Repaint();
        }

        #endregion
    }
}
