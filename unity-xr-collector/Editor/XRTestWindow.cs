using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using XRDataCollector.Core;
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
        private bool showSessionInfo = true;
        private bool showLatestSample = true;
        private bool showSettings = false;
        private string statusMessage = "";
        private MessageType statusType = MessageType.None;
        private float statusClearTime;

        private const float StatusDisplayDuration = 5f;

        #endregion

        #region Menu Item

        /// <summary>
        /// 打开 XR 测试窗口
        /// </summary>
        [MenuItem("XR Test/Open Test Window", false, 0)]
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

            if (XRTestManager.Instance != null)
            {
                XRTestManager.Instance.OnSampleCollected += OnSampleCollected;
                XRTestManager.Instance.OnSessionStarted += OnSessionStarted;
                XRTestManager.Instance.OnSessionStopped += OnSessionStopped;
                XRTestManager.Instance.OnDataExported += OnDataExported;
                XRTestManager.Instance.OnDataUploaded += OnDataUploaded;
            }
        }

        private void OnDisable()
        {
            if (XRTestManager.Instance != null)
            {
                XRTestManager.Instance.OnSampleCollected -= OnSampleCollected;
                XRTestManager.Instance.OnSessionStarted -= OnSessionStarted;
                XRTestManager.Instance.OnSessionStopped -= OnSessionStopped;
                XRTestManager.Instance.OnDataExported -= OnDataExported;
                XRTestManager.Instance.OnDataUploaded -= OnDataUploaded;
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

            bool isCollecting = XRTestManager.Instance != null && XRTestManager.Instance.IsCollecting;

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

            if (XRTestManager.Instance != null)
            {
                EditorGUILayout.LabelField($"Samples Collected: {XRTestManager.Instance.GetSampleCount()}");
            }

            EditorGUILayout.EndVertical();
        }

        private void DrawSessionInfo()
        {
            showSessionInfo = EditorGUILayout.Foldout(showSessionInfo, "Session Info", true, EditorStyles.foldoutHeader);

            if (!showSessionInfo) return;

            EditorGUILayout.BeginVertical(EditorStyles.helpBox);

            if (XRTestManager.Instance != null && XRTestManager.Instance.Session != null)
            {
                var session = XRTestManager.Instance.Session;

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

            if (XRTestManager.Instance != null)
            {
                var sample = XRTestManager.Instance.GetLatestSample();

                if (sample != null)
                {
                    EditorGUILayout.LabelField("Timestamp:", sample.timestamp.ToLocalTime().ToString("HH:mm:ss.fff"));
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
                EditorGUILayout.HelpBox("XRTestManager not found in scene.", MessageType.Warning);
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
            EditorGUILayout.LabelField("Network Upload", EditorStyles.boldLabel);
            EditorGUILayout.Space(5);

            uploadUrl = EditorGUILayout.TextField("Upload URL:", uploadUrl);

            EditorGUILayout.Space(5);

            GUI.enabled = !string.IsNullOrEmpty(uploadUrl);
            if (GUILayout.Button("Upload Data"))
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

            if (XRTestManager.Instance != null && XRTestManager.Instance.Config != null)
            {
                var config = XRTestManager.Instance.Config;

                EditorGUI.BeginChangeCheck();

                config.sessionName = EditorGUILayout.TextField("Session Name:", config.sessionName);
                config.collectInterval = EditorGUILayout.Slider("Collect Interval (s):", config.collectInterval, 0.1f, 10f);
                config.autoStart = EditorGUILayout.Toggle("Auto Start:", config.autoStart);
                config.autoExportOnQuit = EditorGUILayout.Toggle("Auto Export On Quit:", config.autoExportOnQuit);

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
                    EditorUtility.SetDirty(XRTestManager.Instance);
                }
            }
            else
            {
                EditorGUILayout.HelpBox("XRTestManager not found or not configured.", MessageType.Info);
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
            if (XRTestManager.Instance == null)
            {
                ShowStatus("XRTestManager not found. Please add it to a GameObject in the scene.", MessageType.Error);
                return;
            }

            XRTestManager.Instance.StartCollection();
        }

        private void StopCollection()
        {
            if (XRTestManager.Instance == null) return;

            XRTestManager.Instance.StopCollection();
        }

        private void ExportData(ExportFormat format)
        {
            if (XRTestManager.Instance == null)
            {
                ShowStatus("XRTestManager not found.", MessageType.Error);
                return;
            }

            if (XRTestManager.Instance.GetSampleCount() == 0)
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

                XRTestManager.Instance.ExportData(exporter, filePath);
            }
            catch (Exception e)
            {
                ShowStatus($"Export failed: {e.Message}", MessageType.Error);
            }
        }

        private void UploadData()
        {
            if (XRTestManager.Instance == null)
            {
                ShowStatus("XRTestManager not found.", MessageType.Error);
                return;
            }

            if (XRTestManager.Instance.GetSampleCount() == 0)
            {
                ShowStatus("No samples to upload.", MessageType.Warning);
                return;
            }

            if (string.IsNullOrEmpty(uploadUrl))
            {
                ShowStatus("Please enter an upload URL.", MessageType.Warning);
                return;
            }

            XRTestManager.Instance.UploadData(uploadUrl);
            ShowStatus("Uploading data...", MessageType.Info);
        }

        #endregion

        #region Event Handlers

        private void OnSampleCollected(Data.PerformanceSample sample)
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
