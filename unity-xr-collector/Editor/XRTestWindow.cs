using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Data;
using XRDataCollector.Exporters;

namespace XRDataCollector.Editor
{
    /// <summary>
    /// XR 测试 Editor 窗口
    /// 提供可视化的测试控制面板，用于在 Unity Editor 中管理测试会话
    /// </summary>
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

        private const float StatusDisplayDuration = 5f;
        private const string PendingStartAfterPlayModeKey = "XRDataCollector.PendingStartAfterPlayMode";

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
            var window = GetWindow<XRTestWindow>("XR Test");
            window.minSize = new Vector2(400, 500);
            window.Show();
        }

        #endregion

        #region Unity Editor Lifecycle

        private void OnEnable()
        {
            exportPath = Path.Combine(Application.persistentDataPath, "XRTestData");
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;

            var manager = GetManager();
            if (manager != null)
            {
                if (manager.Config != null)
                {
                    uploadUrl = manager.Config.uploadUrl;
                    authToken = manager.Config.authToken;
                }

                manager.OnSampleCollected += OnSampleCollected;
                manager.OnSessionStarted += OnSessionStarted;
                manager.OnSessionStopped += OnSessionStopped;
                manager.OnDataExported += OnDataExported;
                manager.OnDataUploaded += OnDataUploaded;
            }
        }

        private void OnDisable()
        {
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;

            var manager = GetManager();
            if (manager != null)
            {
                manager.OnSampleCollected -= OnSampleCollected;
                manager.OnSessionStarted -= OnSessionStarted;
                manager.OnSessionStopped -= OnSessionStopped;
                manager.OnDataExported -= OnDataExported;
                manager.OnDataUploaded -= OnDataUploaded;
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

        #endregion

        #region GUI

        private void OnGUI()
        {
            EditorGUILayout.Space(10);
            DrawHeader();
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

            EditorGUILayout.EndScrollView();

            DrawStatusBar();
        }

        #endregion

        #region Draw Methods

        private void DrawHeader()
        {
            GUIStyle headerStyle = new GUIStyle(EditorStyles.largeLabel)
            {
                alignment = TextAnchor.MiddleCenter,
                fontSize = 18,
                fontStyle = FontStyle.Bold
            };

            EditorGUILayout.LabelField("XR Data Collector", headerStyle, GUILayout.Height(30));

            GUIStyle subHeaderStyle = new GUIStyle(EditorStyles.label)
            {
                alignment = TextAnchor.MiddleCenter
            };

            EditorGUILayout.LabelField("Performance Testing & Data Collection", subHeaderStyle);
        }

        private void DrawControlPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("Control Panel", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            var manager = GetManager();
            bool isCollecting = manager != null && manager.IsCollecting;

            EditorGUILayout.BeginHorizontal();

            GUI.enabled = !isCollecting;
            if (GUILayout.Button("Start Collection", GUILayout.Height(40)))
            {
                StartCollection();
            }
            GUI.enabled = true;

            GUI.enabled = isCollecting;
            if (GUILayout.Button("Stop Collection", GUILayout.Height(40)))
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

            string statusText = isCollecting ? "Collecting..." : "Idle";
            Color statusColor = isCollecting ? Color.green : Color.gray;

            GUI.color = statusColor;
            EditorGUILayout.LabelField($"Status: {statusText}", statusStyle);
            GUI.color = Color.white;

            if (manager != null)
            {
                EditorGUILayout.LabelField($"Phase: {manager.CurrentCollectionPhase}");
                if (manager.IsCollecting)
                {
                    EditorGUILayout.LabelField($"Phase Remaining: {manager.CurrentPhaseRemainingSeconds:F1} s");
                }
                EditorGUILayout.LabelField($"Samples Collected: {manager.GetSampleCount()}");
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawSessionInfo()
        {
            showSessionInfo = EditorGUILayout.Foldout(showSessionInfo, "Session Info", true, EditorStyles.foldoutHeader);

            if (!showSessionInfo) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null && manager.Session != null)
            {
                var session = manager.Session;

                EditorGUILayout.LabelField("Session Name:", session.SessionName);
                EditorGUILayout.LabelField("Session ID:", session.SessionId);
                EditorGUILayout.LabelField("Start Time:", session.StartTime.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss"));
                EditorGUILayout.LabelField("Duration:", $"{session.ElapsedTime.TotalSeconds:F2} s");
                EditorGUILayout.LabelField("Status:", session.IsActive ? "Active" : "Stopped");
                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("Unity Version:", session.UnityVersion);
                EditorGUILayout.LabelField("Product:", session.ProductName);
                EditorGUILayout.LabelField("App Version:", session.AppVersion);
                EditorGUILayout.LabelField("Platform:", session.Platform);
            }
            else
            {
                EditorGUILayout.HelpBox("No active session. Start collection to see session info.", MessageType.Info);
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawLatestSample()
        {
            showLatestSample = EditorGUILayout.Foldout(showLatestSample, "Latest Sample", true, EditorStyles.foldoutHeader);

            if (!showLatestSample) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null)
            {
                var sample = manager.GetLatestSample();

                if (sample != null)
                {
                    EditorGUILayout.LabelField("Timestamp:", sample.timestamp.ToLocalTime().ToString("HH:mm:ss.fff"));
                    EditorGUILayout.LabelField("Phase:", sample.collectionPhase ?? "-");
                    EditorGUILayout.LabelField("Frame Rate:", $"{sample.frameRate:F1} FPS");
                    EditorGUILayout.LabelField("Frame Time:", $"{sample.frameTimeMs:F2} ms");
                    EditorGUILayout.LabelField("CPU Usage:", $"{sample.cpuUsagePercent:F1} %");
                    EditorGUILayout.LabelField("GPU Usage:", $"{sample.gpuUsagePercent:F1} %");
                    EditorGUILayout.LabelField("Draw Calls:", sample.drawCalls.ToString());
                    EditorGUILayout.LabelField("Triangles:", sample.triangles.ToString());
                    EditorGUILayout.LabelField("Total Memory:", $"{sample.totalMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("Managed Memory:", $"{sample.managedMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("Graphics Memory:", $"{sample.graphicsMemoryMB:F1} MB");
                    EditorGUILayout.LabelField("XR Active:", sample.isXrActive.ToString());
                    EditorGUILayout.LabelField("XR Device:", sample.xrDeviceName ?? "N/A");
                }
                else
                {
                    EditorGUILayout.HelpBox("No samples collected yet.", MessageType.Info);
                }
            }
            else
            {
                EditorGUILayout.HelpBox("XRTestManager not found in scene. Use XR Test -> Setup -> Create XRTestManager first.", MessageType.Warning);
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawExportPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("Export Data", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            EditorGUILayout.BeginHorizontal();
            exportPath = EditorGUILayout.TextField("Export Path:", exportPath);
            if (GUILayout.Button("Browse", GUILayout.Width(60)))
            {
                string selectedPath = EditorUtility.SaveFolderPanel("Select Export Directory", exportPath, "");
                if (!string.IsNullOrEmpty(selectedPath))
                {
                    exportPath = selectedPath;
                }
            }
            EditorGUILayout.EndHorizontal();

            EditorGUILayout.Space(5);

            EditorGUILayout.BeginHorizontal();

            if (GUILayout.Button("Export as JSON"))
            {
                ExportData(ExportFormat.Json);
            }

            if (GUILayout.Button("Export as CSV"))
            {
                ExportData(ExportFormat.Csv);
            }

            EditorGUILayout.EndHorizontal();

            EditorGUILayout.EndVertical();
        }

        private void DrawUploadPanel()
        {
            EditorGUILayout.BeginVertical(EditorStyles.helpBox);
            EditorGUILayout.LabelField("Platform Sync", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            var manager = GetManager();
            if (manager != null && manager.Config != null)
            {
                EditorGUILayout.LabelField("Platform:", manager.Config.platformBaseUrl);
                EditorGUILayout.LabelField("Mode:", manager.Config.autoCreateSession ? "Auto create session and upload" : "Upload to configured URL");
            }
            else
            {
                EditorGUILayout.HelpBox("XRTestManager not found. Use XR Test -> Setup -> Create XRTestManager first.", MessageType.Info);
            }

            EditorGUILayout.Space(5);

            GUI.enabled = manager != null;
            if (GUILayout.Button("Upload / Sync to Platform", GUILayout.Height(32)))
            {
                UploadData();
            }
            GUI.enabled = true;

            EditorGUILayout.EndVertical();
        }

        private void DrawSettings()
        {
            showSettings = EditorGUILayout.Foldout(showSettings, "Settings", true, EditorStyles.foldoutHeader);

            if (!showSettings) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            var manager = GetManager();
            if (manager != null && manager.Config != null)
            {
                var config = manager.Config;

                EditorGUI.BeginChangeCheck();

                config.sessionName = EditorGUILayout.TextField("Session Name:", config.sessionName);
                config.collectInterval = EditorGUILayout.Slider("Collect Interval (s):", config.collectInterval, 0.1f, 10f);
                config.autoStart = EditorGUILayout.Toggle("Auto Start:", config.autoStart);
                config.autoExportOnQuit = EditorGUILayout.Toggle("Auto Export On Quit:", config.autoExportOnQuit);
                config.enableNetworkUpload = EditorGUILayout.Toggle("Enable Network Upload:", config.enableNetworkUpload);

                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("Platform Sync", EditorStyles.boldLabel);
                config.platformBaseUrl = EditorGUILayout.TextField("Platform API Base URL:", config.platformBaseUrl);
                config.autoCreateSession = EditorGUILayout.Toggle("Auto Create Session:", config.autoCreateSession);
                config.projectId = EditorGUILayout.IntField("Project ID:", config.projectId);
                config.sceneId = EditorGUILayout.IntField("Scene ID:", config.sceneId);
                config.uploadUrl = EditorGUILayout.TextField("Fixed Upload URL:", config.uploadUrl);
                config.authToken = EditorGUILayout.PasswordField("Bearer Token:", config.authToken);
                config.username = EditorGUILayout.TextField("Username:", config.username);
                config.password = EditorGUILayout.PasswordField("Password:", config.password);

                EditorGUILayout.Space(5);
                EditorGUILayout.LabelField("Collectors", EditorStyles.boldLabel);

                config.collectFrameRate = EditorGUILayout.Toggle("Frame Rate:", config.collectFrameRate);
                config.collectFrameTime = EditorGUILayout.Toggle("Frame Time:", config.collectFrameTime);
                config.collectCpuUsage = EditorGUILayout.Toggle("CPU Usage:", config.collectCpuUsage);
                config.collectGpuUsage = EditorGUILayout.Toggle("GPU Usage:", config.collectGpuUsage);
                config.collectMemory = EditorGUILayout.Toggle("Memory:", config.collectMemory);
                config.collectDeviceInfo = EditorGUILayout.Toggle("Device Info:", config.collectDeviceInfo);

                if (EditorGUI.EndChangeCheck())
                {
                    EditorUtility.SetDirty(manager);
                }
            }
            else
            {
                EditorGUILayout.HelpBox("XRTestManager not found. Use XR Test -> Setup -> Create XRTestManager first.", MessageType.Info);
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
                ShowStatus("Entering Play Mode. Collection will start automatically.", MessageType.Info);
                return;
            }

            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("XRTestManager not found. Please add it to a GameObject in the scene.", MessageType.Error);
                return;
            }

            manager.StartCollection();
        }

        private void StopCollection()
        {
            var manager = GetManager();
            if (manager == null) return;

            manager.StopCollection();
        }

        private void ExportData(ExportFormat format)
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("XRTestManager not found.", MessageType.Error);
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                ShowStatus("No samples to export.", MessageType.Warning);
                return;
            }

            try
            {
                string fileName = $"XRTest_{DateTime.Now:yyyyMMdd_HHmmss}";
                IDataExporter exporter;
                string extension;

                if (format == ExportFormat.Json)
                {
                    exporter = new JsonExporter();
                    extension = ".json";
                }
                else
                {
                    exporter = new CsvExporter();
                    extension = ".csv";
                }

                string filePath = Path.Combine(exportPath, fileName + extension);

                if (!Directory.Exists(exportPath))
                {
                    Directory.CreateDirectory(exportPath);
                }

                manager.ExportData(exporter, filePath);
            }
            catch (Exception e)
            {
                ShowStatus($"Export failed: {e.Message}", MessageType.Error);
            }
        }

        private void UploadData()
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("XRTestManager not found.", MessageType.Error);
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                ShowStatus("No samples to upload.", MessageType.Warning);
                return;
            }

            manager.UploadData("", null);
            ShowStatus("Syncing data to platform...", MessageType.Info);
        }

        #endregion

        #region Event Handlers

        private void OnSampleCollected(PerformanceSample sample)
        {
            Repaint();
        }

        private void OnSessionStarted()
        {
            ShowStatus("Session started.", MessageType.Info);
            Repaint();
        }

        private void OnSessionStopped()
        {
            ShowStatus("Session stopped.", MessageType.Info);
            Repaint();
        }

        private void OnDataExported(string path)
        {
            ShowStatus($"Data exported to: {path}", MessageType.Info);
            Repaint();
        }

        private void OnDataUploaded(bool success)
        {
            if (success)
            {
                ShowStatus("Data uploaded successfully.", MessageType.Info);
            }
            else
            {
                ShowStatus("Data upload failed.", MessageType.Error);
            }
            Repaint();
        }

        private void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode)
            {
                return;
            }

            if (!SessionState.GetBool(PendingStartAfterPlayModeKey, false))
            {
                return;
            }

            SessionState.SetBool(PendingStartAfterPlayModeKey, false);
            EditorApplication.delayCall += StartPendingCollection;
        }

        private void StartPendingCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                ShowStatus("XRTestManager not found after entering Play Mode.", MessageType.Error);
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
        }

        #endregion
    }
}
