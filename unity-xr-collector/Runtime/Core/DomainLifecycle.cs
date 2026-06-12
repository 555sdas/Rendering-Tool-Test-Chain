using UnityEngine;
using XRDataCollector.Collectors;

namespace XRDataCollector.Core
{
    /// <summary>
    /// 脚本域重载时清理静态引用，避免 "Release of invalid GC handle" 告警。
    /// </summary>
    internal static class DomainLifecycle
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void ResetStatics()
        {
            XRTestManager.ResetDomainState();
            FrameTimingHelper.ResetDomainState();
        }
    }
}
