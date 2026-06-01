using UnityEngine;
using XRDataCollector.Data;

namespace XRDataCollector.Collectors
{
    /// <summary>
    /// 内存使用采集器
    /// 采集系统内存、托管堆内存和显存使用情况
    /// </summary>
    public class MemoryCollector : IPerformanceCollector
    {
        #region Fields

        private long totalMemoryBytes;
        private long managedMemoryBytes;
        private long graphicsMemoryBytes;
        private long systemMemoryBytes;

        #endregion

        #region IPerformanceCollector Implementation

        /// <summary>
        /// 采集器名称
        /// </summary>
        public string CollectorName => "Memory";

        /// <summary>
        /// 开始采集
        /// </summary>
        public void StartCollecting()
        {
            totalMemoryBytes = 0;
            managedMemoryBytes = 0;
            graphicsMemoryBytes = 0;
            systemMemoryBytes = 0;
        }

        /// <summary>
        /// 停止采集
        /// </summary>
        public void StopCollecting()
        {
        }

        /// <summary>
        /// 采集内存使用数据
        /// 包括总内存、托管堆内存、显存和系统内存
        /// </summary>
        /// <param name="sample">性能样本</param>
        public void Collect(ref PerformanceSample sample)
        {
            CollectMemoryStats();

            sample.totalMemoryMB = BytesToMB(totalMemoryBytes);
            sample.managedMemoryMB = BytesToMB(managedMemoryBytes);
            sample.graphicsMemoryMB = BytesToMB(graphicsMemoryBytes);
            sample.systemMemoryMB = BytesToMB(systemMemoryBytes);
        }

        #endregion

        #region Private Methods

        private void CollectMemoryStats()
        {
            managedMemoryBytes = System.GC.GetTotalMemory(false);

            totalMemoryBytes = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong();

            graphicsMemoryBytes = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();

            systemMemoryBytes = UnityEngine.Profiling.Profiler.GetTotalReservedMemoryLong();
        }

        private static float BytesToMB(long bytes)
        {
            return bytes / (1024f * 1024f);
        }

        #endregion
    }
}
