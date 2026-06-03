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
        private readonly List<PlatformProject> platformProjects = new List<PlatformProject>();
        private int selectedProjectIndex = -1;
        private bool isProjectSyncing;

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
                manager.OnPlatformSessionCreated += OnPlatformSessionCreated;
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
                EditorGUILayout.LabelField("Platform Session ID:", session.PlatformSessionId > 0 ? session.PlatformSessionId.ToString() : "Not synced yet");
                EditorGUILayout.LabelField("Platform Run Index:", session.PlatformRunIndex > 0 ? session.PlatformRunIndex.ToString() : "-");
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
                DrawProjectSyncControls(manager);
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

        private void DrawProjectSyncControls(XRTestManager manager)
        {
            var config = manager.Config;

            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField("Project Sync", EditorStyles.boldLabel);

            EditorGUILayout.BeginHorizontal();
            GUI.enabled = !isProjectSyncing;
            if (GUILayout.Button(isProjectSyncing ? "Refreshing..." : "Refresh Projects", GUILayout.Height(24)))
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
                int newIndex = EditorGUILayout.Popup("Project:", currentIndex, options);
                if (newIndex != selectedProjectIndex)
                {
                    SelectPlatformProject(manager, newIndex);
                }
            }
            else
            {
                string projectLabel = string.IsNullOrEmpty(config.projectName)
                    ? $"Project ID {config.projectId}"
                    : $"{config.projectName} (ID {config.projectId})";
                EditorGUILayout.LabelField("Selected Project:", projectLabel);
                EditorGUILayout.HelpBox("Click Refresh Projects after creating a project in the web platform.", MessageType.Info);
            }

            if (config.projectId <= 0)
            {
                EditorGUILayout.HelpBox("Select a platform project before starting synced collection.", MessageType.Warning);
            }

            if (manager.PlatformSessionId > 0)
            {
                EditorGUILayout.LabelField("Platform Session ID:", manager.PlatformSessionId.ToString());
            }
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
                config.projectName = EditorGUILayout.TextField("Project Name:", config.projectName);
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

            if (manager.Config != null &&
                manager.Config.enableNetworkUpload &&
                manager.Config.autoCreateSession &&
                manager.Config.projectId <= 0)
            {
                ShowStatus("Select a platform project before starting synced collection.", MessageType.Error);
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

        private void RefreshPlatformProjects()
        {
            var manager = GetManager();
            if (manager == null || manager.Config == null)
            {
                ShowStatus("XRTestManager not found.", MessageType.Error);
                return;
            }

            if (isProjectSyncing)
            {
                return;
            }

            isProjectSyncing = true;
            ShowStatus("Refreshing platform projects...", MessageType.Info);

            if (!EditorApplication.isPlaying)
            {
                try
                {
                    var projects = LoadProjectsInEditor(manager.Config);
                    ApplyLoadedProjects(manager, projects);
                    ShowStatus($"Loaded {platformProjects.Count} platform projects.", MessageType.Info);
                }
                catch (Exception e)
                {
                    ShowStatus($"Refresh projects failed: {e.Message}", MessageType.Error);
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
                ShowStatus($"Loaded {platformProjects.Count} platform projects.", MessageType.Info);
                Repaint();
            });
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

        private void OnPlatformSessionCreated(int sessionId)
        {
            ShowStatus($"Platform session {sessionId} created.", MessageType.Info);
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

        private void SyncSelectedProjectIndex(XRTestConfig config)
        {
            selectedProjectIndex = -1;
            if (config == null)
            {
                return;
            }

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
            {
                platformProjects.AddRange(projects);
            }

            SyncSelectedProjectIndex(manager.Config);
            if (selectedProjectIndex < 0 && platformProjects.Count > 0)
            {
                SelectPlatformProject(manager, 0);
            }

            EditorUtility.SetDirty(manager);
        }

        private List<PlatformProject> LoadProjectsInEditor(XRTestConfig config)
        {
            string baseUrl = NormalizeBaseUrl(config.platformBaseUrl);
            if (string.IsNullOrEmpty(baseUrl))
            {
                throw new InvalidOperationException("Platform base URL is empty.");
            }

            string token = config.authToken;
            if (string.IsNullOrEmpty(token))
            {
                token = LoginInEditor(baseUrl, config.username, config.password);
                config.authToken = token;
            }

            if (string.IsNullOrEmpty(token))
            {
                throw new InvalidOperationException("Login failed. Check username, password, or token.");
            }

            string json = SendEditorRequest(
                "GET",
                $"{baseUrl}/data-collection/platform/projects?limit=100",
                null,
                null,
                token);
            return ParseProjectList(json);
        }

        private string LoginInEditor(string baseUrl, string username, string password)
        {
            string body =
                "username=" + Uri.EscapeDataString(username ?? "") +
                "&password=" + Uri.EscapeDataString(password ?? "");
            string json = SendEditorRequest(
                "POST",
                $"{baseUrl}/auth/login",
                "application/x-www-form-urlencoded",
                body,
                null);
            return ExtractStringField(json, "access_token");
        }

        private string SendEditorRequest(string method, string url, string contentType, string body, string token)
        {
            var request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = method;
            request.Timeout = 30000;

            if (!string.IsNullOrEmpty(token))
            {
                request.Headers["Authorization"] = "Bearer " + token;
            }

            if (!string.IsNullOrEmpty(body))
            {
                byte[] raw = Encoding.UTF8.GetBytes(body);
                request.ContentType = contentType ?? "application/json";
                request.ContentLength = raw.Length;
                using (var stream = request.GetRequestStream())
                {
                    stream.Write(raw, 0, raw.Length);
                }
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
            if (string.IsNullOrEmpty(value))
            {
                return "";
            }
            return value.Trim().TrimEnd('/');
        }

        private string ExtractStringField(string json, string field)
        {
            var match = Regex.Match(json, $"\"{field}\"\\s*:\\s*\"([^\"]+)\"");
            return match.Success ? match.Groups[1].Value : null;
        }

        private void SelectPlatformProject(XRTestManager manager, int index)
        {
            if (manager == null || manager.Config == null || index < 0 || index >= platformProjects.Count)
            {
                return;
            }

            var project = platformProjects[index];
            selectedProjectIndex = index;
            manager.Config.projectId = project.id;
            manager.Config.projectName = project.name;
            manager.Config.sessionName = string.IsNullOrEmpty(project.name) ? "Unity Test" : project.name + " Unity Test";

            EditorUtility.SetDirty(manager);
            ShowStatus($"Selected project {project.name} (next session #{project.next_session_index}).", MessageType.Info);
            Repaint();
        }

        #endregion
    }
}
