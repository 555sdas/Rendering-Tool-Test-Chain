using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using XRDataCollector.Core;
using XRDataCollector.Exporters;

namespace XRDataCollector.Editor
{
    /// <summary>
    /// XR 测试菜单项
    /// 提供 Unity Editor 菜单中的快捷操作
    /// </summary>
    public static class XRTestMenu
    {
        private static XRTestManager GetManager()
        {
            return XRTestManager.Instance != null
                ? XRTestManager.Instance
                : Object.FindObjectOfType<XRTestManager>();
        }

        #region Window Menu

        /// <summary>
        /// 打开 XR 测试窗口
        /// </summary>
        [MenuItem("XR Test/Open Test Window", false, 0)]
        public static void OpenTestWindow()
        {
            XRTestWindow.ShowWindow();
        }

        #endregion

        #region Session Control

        /// <summary>
        /// 开始测试会话
        /// </summary>
        [MenuItem("XR Test/Session/Start Collection", false, 100)]
        public static void StartCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] XRTestManager not found. Please add it to a GameObject in the scene.");
                EditorUtility.DisplayDialog("XR Test", "XRTestManager not found in scene. Please add it to a GameObject first.", "OK");
                return;
            }

            manager.StartCollection();
            Debug.Log("[XRTestMenu] Collection started.");
        }

        /// <summary>
        /// 停止测试会话
        /// </summary>
        [MenuItem("XR Test/Session/Stop Collection", false, 101)]
        public static void StopCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] XRTestManager not found.");
                return;
            }

            manager.StopCollection();
            Debug.Log("[XRTestMenu] Collection stopped.");
        }

        /// <summary>
        /// 清除所有样本
        /// </summary>
        [MenuItem("XR Test/Session/Clear Samples", false, 102)]
        public static void ClearSamples()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] XRTestManager not found.");
                return;
            }

            int count = manager.GetSampleCount();
            manager.ClearSamples();
            Debug.Log($"[XRTestMenu] Cleared {count} samples.");
        }

        #endregion

        #region Export

        /// <summary>
        /// 导出为 JSON
        /// </summary>
        [MenuItem("XR Test/Export/Export as JSON", false, 200)]
        public static void ExportAsJson()
        {
            ExportData(ExportFormat.Json);
        }

        /// <summary>
        /// 导出为 CSV
        /// </summary>
        [MenuItem("XR Test/Export/Export as CSV", false, 201)]
        public static void ExportAsCsv()
        {
            ExportData(ExportFormat.Csv);
        }

        private static void ExportData(ExportFormat format)
        {
            var manager = GetManager();
            if (manager == null)
            {
                EditorUtility.DisplayDialog("XR Test", "XRTestManager not found in scene.", "OK");
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                EditorUtility.DisplayDialog("XR Test", "No samples to export.", "OK");
                return;
            }

            string extension = format == ExportFormat.Json ? "json" : "csv";
            string defaultName = $"XRTest_{System.DateTime.Now:yyyyMMdd_HHmmss}.{extension}";

            string path = EditorUtility.SaveFilePanel(
                $"Export as {format}",
                Application.persistentDataPath,
                defaultName,
                extension
            );

            if (string.IsNullOrEmpty(path)) return;

            try
            {
                IDataExporter exporter = format == ExportFormat.Json
                    ? new Exporters.JsonExporter()
                    : new Exporters.CsvExporter();

                manager.ExportData(exporter, path);
                EditorUtility.DisplayDialog("XR Test", $"Data exported to:\n{path}", "OK");
            }
            catch (System.Exception e)
            {
                EditorUtility.DisplayDialog("XR Test", $"Export failed:\n{e.Message}", "OK");
            }
        }

        #endregion

        #region Scene Setup

        /// <summary>
        /// 在当前场景中创建 XRTestManager
        /// </summary>
        [MenuItem("XR Test/Setup/Create XRTestManager", false, 300)]
        public static void CreateXRTestManager()
        {
            var existing = Object.FindObjectOfType<XRTestManager>();
            if (existing != null)
            {
                EditorUtility.DisplayDialog("XR Test", "XRTestManager already exists in the scene.", "OK");
                Selection.activeGameObject = existing.gameObject;
                return;
            }

            var go = new GameObject("XRTestManager");
            go.AddComponent<XRTestManager>();

            Undo.RegisterCreatedObjectUndo(go, "Create XRTestManager");
            Selection.activeGameObject = go;

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());

            Debug.Log("[XRTestMenu] Created XRTestManager in scene.");
        }

        /// <summary>
        /// 查找场景中的 XRTestManager
        /// </summary>
        [MenuItem("XR Test/Setup/Find XRTestManager", false, 301)]
        public static void FindXRTestManager()
        {
            var manager = Object.FindObjectOfType<XRTestManager>();
            if (manager != null)
            {
                Selection.activeGameObject = manager.gameObject;
                EditorGUIUtility.PingObject(manager.gameObject);
            }
            else
            {
                EditorUtility.DisplayDialog("XR Test", "XRTestManager not found in scene.", "OK");
            }
        }

        #endregion

        #region Validation

        /// <summary>
        /// 验证是否可以开始采集
        /// </summary>
        [MenuItem("XR Test/Session/Start Collection", true)]
        public static bool ValidateStartCollection()
        {
            var manager = GetManager();
            return manager != null && !manager.IsCollecting;
        }

        /// <summary>
        /// 验证是否可以停止采集
        /// </summary>
        [MenuItem("XR Test/Session/Stop Collection", true)]
        public static bool ValidateStopCollection()
        {
            var manager = GetManager();
            return manager != null && manager.IsCollecting;
        }

        /// <summary>
        /// 验证是否可以清除样本
        /// </summary>
        [MenuItem("XR Test/Session/Clear Samples", true)]
        public static bool ValidateClearSamples()
        {
            var manager = GetManager();
            return manager != null && manager.GetSampleCount() > 0;
        }

        #endregion

        #region Help

        /// <summary>
        /// 打开文档
        /// </summary>
        [MenuItem("XR Test/Help/Documentation", false, 400)]
        public static void OpenDocumentation()
        {
            string packagePath = "Packages/com.xr.testdatacollector/README.md";
            string readmePath = System.IO.Path.GetFullPath(packagePath);

            if (System.IO.File.Exists(readmePath))
            {
                Application.OpenURL("file://" + readmePath);
            }
            else
            {
                EditorUtility.DisplayDialog("XR Test", "Documentation not found.", "OK");
            }
        }

        /// <summary>
        /// 关于
        /// </summary>
        [MenuItem("XR Test/Help/About", false, 401)]
        public static void ShowAbout()
        {
            EditorUtility.DisplayDialog(
                "About XR Data Collector",
                "XR Data Collector v1.0.0\n\n" +
                "Unity XR performance data collection and testing plugin.\n\n" +
                "Supports: Frame Rate, Frame Time, CPU/GPU Usage, Memory, Device Info\n" +
                "Export: JSON, CSV\n" +
                "Network: HTTP Upload\n\n" +
                "Unity 2022.3 LTS | OpenXR Compatible",
                "OK"
            );
        }

        #endregion
    }
}
