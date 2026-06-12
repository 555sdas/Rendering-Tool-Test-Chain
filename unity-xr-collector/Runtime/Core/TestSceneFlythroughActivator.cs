using System;
using System.Collections;
using System.Reflection;
using UnityEngine;
using UnityEngine.Playables;

namespace XRDataCollector.Core
{
    /// <summary>
    /// 自动化测试启动时进入巡航/演示模式。
    /// - Garden/Oasis：PlayerManager + FlythroughDirector
    /// - Cockpit：无 PlayerManager，使用 SceneMetaData.SequenceDirector
    /// - Terminal：枢纽场景，需等待子场景异步加载后再启动全片 Timeline
    /// </summary>
    public static class TestSceneFlythroughActivator
    {
        private const string PlayerManagerTypeName = "PlayerManager";
        private const string SceneMetaDataTypeName = "SceneMetaData";
        private const string MediaSceneLoaderTypeName = "MediaSceneLoader";
        private const string SceneTransitionManagerTypeName = "SceneTransitionManager";
        private const int MaxActivationAttempts = 40;
        private const int TerminalHubMaxWaitFrames = 600;

        public static void RequestActivation(MonoBehaviour host)
        {
            var runner = ResolveCoroutineHost(host);
            if (runner == null)
                return;

            runner.StopAllCoroutines();
            runner.StartCoroutine(ActivateWhenReady());
        }

        private static MonoBehaviour ResolveCoroutineHost(MonoBehaviour host)
        {
            if (host != null && host.isActiveAndEnabled)
                return host;

            var manager = host != null ? host : XRTestManager.Instance;
            if (manager == null)
                manager = UnityEngine.Object.FindObjectOfType<XRTestManager>();
            if (manager != null)
                return manager;

            return FlythroughCoroutineHost.EnsureInstance();
        }

        private static IEnumerator ActivateWhenReady()
        {
            if (IsTerminalHubScene())
            {
                Debug.Log("[TestSceneFlythroughActivator] 检测到 Terminal 枢纽场景，等待子场景加载完成…");
                yield return WaitForTerminalHubReady();
            }

            for (int attempt = 0; attempt < MaxActivationAttempts; attempt++)
            {
                yield return null;

                if (attempt == 0 || attempt == 2 || attempt % 10 == 0)
                    EnsureDemoSceneVisible();

                if (TryEnablePlayerFlythrough() && IsPlayerFlythroughActive())
                {
                    Debug.Log($"[TestSceneFlythroughActivator] 已通过 PlayerManager 启动巡航（第 {attempt + 1} 次尝试）。");
                    yield break;
                }

                if (TryPlaySequenceDirector() && IsSequenceDirectorActive())
                {
                    Debug.Log($"[TestSceneFlythroughActivator] 已通过 SequenceDirector 启动演示（第 {attempt + 1} 次尝试）。");
                    yield break;
                }
            }

            if (TryEnablePlayerFlythrough())
                Debug.Log("[TestSceneFlythroughActivator] 已调用 PlayerManager.EnableFlythrough，但未能确认 Timeline 正在播放。");
            else if (TryPlaySequenceDirector())
                Debug.Log("[TestSceneFlythroughActivator] 已调用 SequenceDirector.Play，但未能确认 Timeline 正在播放。");
            else
                Debug.Log("[TestSceneFlythroughActivator] 未找到可用的巡航入口（PlayerManager 或 SequenceDirector）。");
        }

        private static bool IsTerminalHubScene()
        {
            Type mediaLoaderType = FindType(MediaSceneLoaderTypeName);
            return mediaLoaderType != null &&
                   UnityEngine.Object.FindObjectOfType(mediaLoaderType) != null;
        }

        private static IEnumerator WaitForTerminalHubReady()
        {
            Type stmType = FindType(SceneTransitionManagerTypeName);
            if (stmType == null)
                yield break;

            var isAvailableMethod = stmType.GetMethod(
                "IsAvailable",
                BindingFlags.Public | BindingFlags.Static);
            if (isAvailableMethod == null)
                yield break;

            for (int frame = 0; frame < TerminalHubMaxWaitFrames; frame++)
            {
                yield return null;

                if (!(bool)isAvailableMethod.Invoke(null, null))
                    continue;

                int loading = GetSceneTransitionLoadingCount(stmType);
                int registered = GetRegisteredSceneCount(stmType);
                if (loading <= 0 && registered >= 3)
                {
                    Debug.Log(
                        $"[TestSceneFlythroughActivator] Terminal 子场景已就绪：registered={registered}，loading={loading}。");
                    yield break;
                }
            }

            Debug.LogWarning(
                "[TestSceneFlythroughActivator] Terminal 子场景加载等待超时；若随后卡死，请改用 Garden/Oasis 或关闭自动巡航。");
        }

        private static int GetSceneTransitionLoadingCount(Type stmType)
        {
            object instance = GetSceneTransitionManagerInstance(stmType);
            if (instance == null)
                return int.MaxValue;

            var field = stmType.GetField(
                "m_ScenesLoading",
                BindingFlags.Instance | BindingFlags.NonPublic);
            return field != null ? (int)field.GetValue(instance) : int.MaxValue;
        }

        private static int GetRegisteredSceneCount(Type stmType)
        {
            object instance = GetSceneTransitionManagerInstance(stmType);
            if (instance == null)
                return 0;

            var field = stmType.GetField(
                "registeredScenes",
                BindingFlags.Instance | BindingFlags.NonPublic);
            if (field?.GetValue(instance) is System.Collections.IDictionary dict)
                return dict.Count;

            return 0;
        }

        private static object GetSceneTransitionManagerInstance(Type stmType)
        {
            var field = stmType.GetField("instance", BindingFlags.Static | BindingFlags.NonPublic);
            return field?.GetValue(null);
        }

        /// <summary>
        /// Garden/Oasis/Cockpit 等子场景独立打开时，SceneMetaData 会在 Start 中隐藏 Root（StartActive=0）。
        /// </summary>
        private static void EnsureDemoSceneVisible()
        {
            Type metaType = FindType(SceneMetaDataTypeName);
            if (metaType == null)
                return;

            foreach (var meta in UnityEngine.Object.FindObjectsOfType(metaType))
            {
                var root = metaType.GetField("Root", BindingFlags.Instance | BindingFlags.Public)
                    ?.GetValue(meta) as GameObject;
                if (root != null && !root.activeInHierarchy)
                {
                    root.SetActive(true);
                    Debug.Log("[TestSceneFlythroughActivator] 已启用演示场景 Root。");
                }
            }
        }

        private static bool TryEnablePlayerFlythrough()
        {
            Type playerManagerType = FindType(PlayerManagerTypeName);
            if (playerManagerType == null)
                return false;

            var instance = UnityEngine.Object.FindObjectOfType(playerManagerType);
            if (instance == null)
                return false;

            var directorField = playerManagerType.GetField(
                "FlythroughDirector",
                BindingFlags.Instance | BindingFlags.Public);
            var director = directorField?.GetValue(instance) as PlayableDirector;
            if (director == null)
                return false;

            if (!director.gameObject.activeInHierarchy)
                director.gameObject.SetActive(true);

            var method = playerManagerType.GetMethod(
                "EnableFlythrough",
                BindingFlags.Instance | BindingFlags.Public);
            if (method == null)
                return false;

            method.Invoke(instance, null);
            return true;
        }

        /// <summary>
        /// CockpitScene 等场景没有 PlayerManager/FlythroughDirector，演示由 SequenceDirector 驱动。
        /// </summary>
        private static bool TryPlaySequenceDirector()
        {
            Type metaType = FindType(SceneMetaDataTypeName);
            if (metaType == null)
                return false;

            foreach (var meta in UnityEngine.Object.FindObjectsOfType(metaType))
            {
                var flythrough = metaType.GetField(
                    "FlythroughDirector",
                    BindingFlags.Instance | BindingFlags.Public)?.GetValue(meta) as PlayableDirector;
                if (flythrough != null)
                    continue;

                var sequence = metaType.GetField(
                    "SequenceDirector",
                    BindingFlags.Instance | BindingFlags.Public)?.GetValue(meta) as PlayableDirector;
                if (sequence == null)
                    continue;

                if (!sequence.gameObject.activeInHierarchy)
                    sequence.gameObject.SetActive(true);

                sequence.time = 0;
                sequence.Play();
                return true;
            }

            return false;
        }

        private static bool IsPlayerFlythroughActive()
        {
            Type playerManagerType = FindType(PlayerManagerTypeName);
            if (playerManagerType == null)
                return false;

            var instance = UnityEngine.Object.FindObjectOfType(playerManagerType);
            if (instance == null)
                return false;

            var director = playerManagerType.GetField(
                "FlythroughDirector",
                BindingFlags.Instance | BindingFlags.Public)?.GetValue(instance) as PlayableDirector;
            if (director == null)
                return false;

            return director.gameObject.activeInHierarchy &&
                   director.state == PlayState.Playing;
        }

        private static bool IsSequenceDirectorActive()
        {
            Type metaType = FindType(SceneMetaDataTypeName);
            if (metaType == null)
                return false;

            foreach (var meta in UnityEngine.Object.FindObjectsOfType(metaType))
            {
                var sequence = metaType.GetField(
                    "SequenceDirector",
                    BindingFlags.Instance | BindingFlags.Public)?.GetValue(meta) as PlayableDirector;
                if (sequence == null)
                    continue;

                if (sequence.gameObject.activeInHierarchy &&
                    sequence.state == PlayState.Playing)
                    return true;
            }

            return false;
        }

        /// <summary>
        /// 测试结束前停止巡航/Timeline，避免退出 Play Mode 时 Cinemachine 仍在驱动导致 Editor 崩溃。
        /// </summary>
        public static void StopPresentation()
        {
            Type playerManagerType = FindType(PlayerManagerTypeName);
            if (playerManagerType != null)
            {
                var instance = UnityEngine.Object.FindObjectOfType(playerManagerType);
                if (instance != null && Application.isPlaying)
                {
                    var restoreMethod = playerManagerType.GetMethod(
                        "EnableFirstPersonController",
                        BindingFlags.Instance | BindingFlags.Public);
                    if (restoreMethod != null)
                    {
                        try
                        {
                            restoreMethod.Invoke(instance, null);
                        }
                        catch (TargetInvocationException exception)
                        {
                            string message = exception.InnerException?.Message ?? exception.Message;
                            Debug.LogWarning(
                                "[TestSceneFlythroughActivator] 恢复第一人称控制器失败，继续执行关闭清理：" + message);
                        }
                        catch (Exception exception)
                        {
                            Debug.LogWarning(
                                "[TestSceneFlythroughActivator] 恢复第一人称控制器失败，继续执行关闭清理：" + exception.Message);
                        }
                    }
                }
            }

            var directors = UnityEngine.Object.FindObjectsOfType<PlayableDirector>();
            foreach (var director in directors)
            {
                if (director == null)
                    continue;
                if (director.state == PlayState.Playing)
                {
                    try
                    {
                        director.Stop();
                    }
                    catch (Exception exception)
                    {
                        Debug.LogWarning(
                            "[TestSceneFlythroughActivator] 停止 Timeline 失败，继续执行关闭清理：" + exception.Message);
                    }
                }
            }
        }

        private static Type FindType(string typeName)
        {
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                Type type = assembly.GetType(typeName);
                if (type != null)
                    return type;
            }

            return null;
        }
    }

    internal class FlythroughCoroutineHost : MonoBehaviour
    {
        private static FlythroughCoroutineHost instance;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void ResetDomainState()
        {
            instance = null;
        }

        public static FlythroughCoroutineHost EnsureInstance()
        {
            if (instance != null)
                return instance;

            var go = new GameObject("XRFlythroughHost");
            instance = go.AddComponent<FlythroughCoroutineHost>();
            go.hideFlags = HideFlags.DontSave;
            return instance;
        }

        private void Awake()
        {
            if (instance != null && instance != this)
            {
                Destroy(gameObject);
                return;
            }

            instance = this;
            hideFlags = HideFlags.DontSave;
        }

        private void OnDestroy()
        {
            if (instance == this)
                instance = null;
        }
    }
}
