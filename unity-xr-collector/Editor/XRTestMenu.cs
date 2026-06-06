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

        [MenuItem("XR 测试/打开测试窗口", false, 0)]
        public static void OpenTestWindow()
        {
            XRTestWindow.ShowWindow();
        }

        #endregion

        #region Session Control

        [MenuItem("XR 测试/会话/开始采集", false, 100)]
        public static void StartCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] 未找到 XRTestManager，请将其添加到场景中的 GameObject 上。");
                EditorUtility.DisplayDialog("XR 测试", "场景中未找到 XRTestManager，请先将其添加到 GameObject 上。", "确定");
                return;
            }

            manager.StartCollection();
            Debug.Log("[XRTestMenu] 采集已开始。");
        }

        [MenuItem("XR 测试/会话/停止采集", false, 101)]
        public static void StopCollection()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] 未找到 XRTestManager。");
                return;
            }

            manager.StopCollection();
            Debug.Log("[XRTestMenu] 采集已停止。");
        }

        [MenuItem("XR 测试/会话/清除样本", false, 102)]
        public static void ClearSamples()
        {
            var manager = GetManager();
            if (manager == null)
            {
                Debug.LogWarning("[XRTestMenu] 未找到 XRTestManager。");
                return;
            }

            int count = manager.GetSampleCount();
            manager.ClearSamples();
            Debug.Log($"[XRTestMenu] 已清除 {count} 个样本。");
        }

        #endregion

        #region Export

        [MenuItem("XR 测试/导出/导出为 JSON", false, 200)]
        public static void ExportAsJson()
        {
            ExportData(ExportFormat.Json);
        }

        [MenuItem("XR 测试/导出/导出为 CSV", false, 201)]
        public static void ExportAsCsv()
        {
            ExportData(ExportFormat.Csv);
        }

        private static void ExportData(ExportFormat format)
        {
            var manager = GetManager();
            if (manager == null)
            {
                EditorUtility.DisplayDialog("XR 测试", "场景中未找到 XRTestManager。", "确定");
                return;
            }

            if (manager.GetSampleCount() == 0)
            {
                EditorUtility.DisplayDialog("XR 测试", "没有可导出的样本。", "确定");
                return;
            }

            string extension = format == ExportFormat.Json ? "json" : "csv";
            string defaultName = $"XRTest_{System.DateTime.Now:yyyyMMdd_HHmmss}.{extension}";

            string path = EditorUtility.SaveFilePanel(
                $"导出为 {format}",
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
                EditorUtility.DisplayDialog("XR 测试", $"数据已导出至：\n{path}", "确定");
            }
            catch (System.Exception e)
            {
                EditorUtility.DisplayDialog("XR 测试", $"导出失败：\n{e.Message}", "确定");
            }
        }

        #endregion

        #region Scene Setup

        [MenuItem("XR 测试/设置/创建 XRTestManager", false, 300)]
        public static void CreateXRTestManager()
        {
            var existing = Object.FindObjectOfType<XRTestManager>();
            if (existing != null)
            {
                EditorUtility.DisplayDialog("XR 测试", "场景中已存在 XRTestManager。", "确定");
                Selection.activeGameObject = existing.gameObject;
                return;
            }

            var go = new GameObject("XRTestManager");
            go.AddComponent<XRTestManager>();

            Undo.RegisterCreatedObjectUndo(go, "创建 XRTestManager");
            Selection.activeGameObject = go;

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());

            Debug.Log("[XRTestMenu] 已在场景中创建 XRTestManager。");
        }

        [MenuItem("XR 测试/设置/查找 XRTestManager", false, 301)]
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
                EditorUtility.DisplayDialog("XR 测试", "场景中未找到 XRTestManager。", "确定");
            }
        }

        #endregion

        #region Validation

        [MenuItem("XR 测试/会话/开始采集", true)]
        public static bool ValidateStartCollection()
        {
            var manager = GetManager();
            return manager != null && !manager.IsCollecting;
        }

        [MenuItem("XR 测试/会话/停止采集", true)]
        public static bool ValidateStopCollection()
        {
            var manager = GetManager();
            return manager != null && manager.IsCollecting;
        }

        [MenuItem("XR 测试/会话/清除样本", true)]
        public static bool ValidateClearSamples()
        {
            var manager = GetManager();
            return manager != null && manager.GetSampleCount() > 0;
        }

        #endregion

        #region Help

        [MenuItem("XR 测试/帮助/文档", false, 400)]
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
                EditorUtility.DisplayDialog("XR 测试", "未找到文档。", "确定");
            }
        }

        [MenuItem("XR 测试/帮助/关于", false, 401)]
        public static void ShowAbout()
        {
            EditorUtility.DisplayDialog(
                "关于 XR 数据采集器",
                "XR 数据采集器 v1.0.0\n\n" +
                "Unity XR 性能数据采集与测试插件。\n\n" +
                "支持：帧率、帧时间、CPU/GPU 占用、内存、设备信息\n" +
                "导出：JSON、CSV\n" +
                "网络：HTTP 上传\n\n" +
                "Unity 2022.3 LTS | OpenXR 兼容",
                "确定"
            );
        }

        #endregion
    }
}
