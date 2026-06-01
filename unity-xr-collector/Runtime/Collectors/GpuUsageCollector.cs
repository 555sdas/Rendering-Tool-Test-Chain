using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// GPU 使用率采集器
    /// 采集 GPU 相关性能指标
    /// </summary>
    public class GpuUsageCollector : IPerformanceCollector
    {
        #region Fields

        private float gpuUsagePercent;
        private int drawCalls;
        private int triangles;
        private int vertices;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "GpuUsage";

        /// <summary>
        /// 开始采集
        /// </summary>
        public void StartCollecting()
        {
            gpuUsagePercent = 0f;
            drawCalls = 0;
            triangles = 0;
            vertices = 0;
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集 GPU 相关指标
        /// 包括渲染统计信息和 GPU 使用率估算
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            CollectRenderStats();
            EstimateGpuUsage();

            sample.gpuUsagePercent = gpuUsagePercent;
            sample.drawCalls = drawCalls;
            sample.triangles = triangles;
            sample.vertices = vertices;
        }

        #endregion

        #region Private Methods

        private void CollectRenderStats()
        {
            drawCalls = 0;
            triangles = 0;
            vertices = 0;

            var renderers = Object.FindObjectsOfType<Renderer>();
            foreach (var renderer in renderers)
            {
                if (renderer == null || !renderer.enabled || !renderer.gameObject.activeInHierarchy)
                {
                    continue;
                }

                drawCalls += renderer.sharedMaterials != null ? renderer.sharedMaterials.Length : 1;

                Mesh mesh = null;
                if (renderer is SkinnedMeshRenderer skinnedMeshRenderer)
                {
                    mesh = skinnedMeshRenderer.sharedMesh;
                }
                else
                {
                    var meshFilter = renderer.GetComponent<MeshFilter>();
                    if (meshFilter != null)
                    {
                        mesh = meshFilter.sharedMesh;
                    }
                }

                if (mesh == null)
                {
                    continue;
                }

                vertices += mesh.vertexCount;
                triangles += mesh.triangles != null ? mesh.triangles.Length / 3 : 0;
            }
        }

        private void EstimateGpuUsage()
        {
            float frameTime = Time.unscaledDeltaTime * 1000f;
            float cpuTime = frameTime;

            float estimatedGpuTime = frameTime * 0.7f;

            if (Application.targetFrameRate > 0)
            {
                float targetMs = 1000f / Application.targetFrameRate;
                gpuUsagePercent = Mathf.Clamp((estimatedGpuTime / targetMs) * 100f, 0f, 100f);
            }
            else
            {
                gpuUsagePercent = Mathf.Clamp(estimatedGpuTime / 16.67f * 100f, 0f, 100f);
            }
        }

        #endregion
    }
}
