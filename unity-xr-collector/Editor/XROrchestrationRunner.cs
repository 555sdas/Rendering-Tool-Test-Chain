using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Networking;
using XRDataCollector.Core;
using XRDataCollector.Network;

namespace XRDataCollector.Editor
{
    public static class XROrchestrationRunner
    {
        private const string ConfigPathKey = "XROrchestration.ConfigPath";
        private const string ActiveBatchIdKey = "XROrchestration.ActiveBatchId";
        private const string ActiveSceneIndexKey = "XROrchestration.ActiveSceneIndex";
        private const string ActiveBatchItemIdKey = "XROrchestration.ActiveBatchItemId";
        private const string ActiveAttemptKey = "XROrchestration.ActiveAttempt";
        private const string OrchestrationStateKey = "XROrchestration.State";
        private const string PendingDecisionVersionKey = "XROrchestration.PendingDecisionVersion";
        private const string ProcessedCommandIdsKey = "XROrchestration.ProcessedCommandIds";
        private const string ActiveFlagKey = "XROrchestration.Active";
        private const string CollectionReadyAtKey = "XROrchestration.CollectionReadyAt";
        private const string ExitReadyAtKey = "XROrchestration.ExitReadyAt";
        private const string UploadResultReceivedKey = "XROrchestration.UploadResultReceived";
        private const string UploadSucceededKey = "XROrchestration.UploadSucceeded";
        private const string PendingExitCodeKey = "XRDataCollector.BatchPendingExitCode";
        private const string QuitOnCompleteKey = "XRDataCollector.BatchQuitOnComplete";

        private const double CollectionReadyDelaySeconds = 2.0d;
        private const double ExitDelayAfterUploadSeconds = 3.5d;
        private const double ExitDelayAfterPlayModeExitSeconds = 2.5d;
        private const double CommandPollIntervalSeconds = 1.0d;

        private enum OrchestrationState
        {
            Idle = 0,
            PreparingScene = 1,
            EnteringPlayMode = 2,
            Collecting = 3,
            Uploading = 4,
            ExitingPlayMode = 5,
            PreparingNextScene = 6,
            AwaitingUserDecision = 7,
            Completed = 8,
            Aborted = 9
        }

        private static XROrchestrationTaskConfig orchestrationConfig;
        private static string configFilePath;
        private static XRSceneRunConfig currentScene;
        private static OrchestrationState state;
        private static bool uploadResultReceived;
        private static bool uploadSucceeded;
        private static bool shutdownScheduled;
        private static double nextCommandPollAt;
        private static string lastFailureMessage;

        [InitializeOnLoadMethod]
        private static void ResumeOnDomainReload()
        {
            DetachAllCallbacks();

            if (!IsOrchestrationActive())
                return;

            if (!TryLoadPersistedConfig(out orchestrationConfig, out configFilePath))
            {
                ClearOrchestrationSessionState();
                return;
            }

            state = (OrchestrationState)SessionState.GetInt(OrchestrationStateKey, (int)OrchestrationState.Idle);
            currentScene = ResolveCurrentScene(orchestrationConfig);
            shutdownScheduled = false;
            uploadResultReceived = SessionState.GetBool(UploadResultReceivedKey, false);
            uploadSucceeded = SessionState.GetBool(UploadSucceededKey, false);

            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.update += Tick;

            if (state == OrchestrationState.Collecting && EditorApplication.isPlaying)
            {
                var manager = FindManager();
                if (manager != null && manager.IsCollecting)
                    EditorApplication.update += ReapplyConfigWhileCollectingOnce;
            }

            LogOrchestration("域重载后恢复编排状态：" + state);
        }

        public static bool IsOrchestrationActive()
        {
            return SessionState.GetBool(ActiveFlagKey, false);
        }

        public static void RunFromConfigPath(string configPath, string json = null)
        {
            if (string.IsNullOrEmpty(configPath))
                throw new InvalidOperationException("缺少编排配置文件路径。");
            if (!File.Exists(configPath))
                throw new FileNotFoundException("编排配置文件不存在。", configPath);

            if (json == null)
                json = File.ReadAllText(configPath);
            if (!XROrchestrationConfigParser.TryParse(json, out orchestrationConfig, out string error))
                throw new InvalidOperationException(error);

            DetachAllCallbacks();
            configFilePath = configPath;
            shutdownScheduled = false;
            uploadResultReceived = false;
            uploadSucceeded = false;
            PersistUploadResult(false, false);
            lastFailureMessage = null;

            PersistOrchestrationState(orchestrationConfig, configPath, 0, OrchestrationState.PreparingScene);
            XRBatchTestRunner.EnableFrameTimingStatsInternal();

            LogOrchestration($"已读取编排配置：{configPath}，共 {orchestrationConfig.scenes.Length} 个场景。");

            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.update += Tick;
            TransitionTo(OrchestrationState.PreparingScene);
        }

        private static void Tick()
        {
            if (!IsOrchestrationActive() || orchestrationConfig == null)
            {
                DetachAllCallbacks();
                return;
            }

            PollStopRequest();

            switch (state)
            {
                case OrchestrationState.PreparingScene:
                    TickPreparingScene();
                    break;
                case OrchestrationState.EnteringPlayMode:
                    TickEnteringPlayMode();
                    break;
                case OrchestrationState.Collecting:
                    TickCollecting();
                    break;
                case OrchestrationState.Uploading:
                    TickUploading();
                    break;
                case OrchestrationState.ExitingPlayMode:
                    TickExitingPlayMode();
                    break;
                case OrchestrationState.PreparingNextScene:
                    TickPreparingNextScene();
                    break;
                case OrchestrationState.AwaitingUserDecision:
                    TickAwaitingUserDecision();
                    break;
            }
        }

        private static void TickPreparingScene()
        {
            if (!EditorReadyForScenePrep())
                return;

            currentScene = ResolveCurrentScene(orchestrationConfig);
            if (currentScene == null)
            {
                FinishBatch(1, "当前场景索引超出范围。");
                return;
            }

            PersistSceneCursor(currentScene, OrchestrationState.PreparingScene);

            try
            {
                CleanupSceneRuntime();
                XRBatchTestRunner.OpenConfiguredSceneInternal(
                    orchestrationConfig.unityProjectPath,
                    currentScene.unityScenePath);
                var manager = XRBatchTestRunner.EnsureManagerInternal();
                XRBatchTestRunner.ApplySceneRunConfig(manager, currentScene, orchestrationConfig);
                LogScene("场景已打开，准备进入 Play Mode。");
                PostBatchProgress("running", currentScene, "running", null);
                TransitionTo(OrchestrationState.EnteringPlayMode);
            }
            catch (Exception exception)
            {
                HandleSceneFailure("场景准备失败：" + exception.Message);
            }
        }

        private static void TickEnteringPlayMode()
        {
            if (EditorApplication.isPlaying)
                return;

            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            EditorApplication.isPlaying = true;
        }

        private static void TickCollecting()
        {
            if (!EditorApplication.isPlaying || EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            if (!double.TryParse(SessionState.GetString(CollectionReadyAtKey, "0"), out double readyAt))
                readyAt = 0d;
            if (EditorApplication.timeSinceStartup < readyAt)
                return;

            var manager = FindManager();
            if (manager == null)
            {
                HandleSceneFailure("进入运行模式后未找到 XRTestManager。");
                return;
            }

            if (manager.IsCollecting)
            {
                SessionState.EraseString(CollectionReadyAtKey);
                return;
            }

            if (uploadResultReceived)
                return;

            AttachManagerCallbacks(manager);
            XRBatchTestRunner.ApplySceneRunConfig(manager, currentScene, orchestrationConfig);
            manager.Initialize(manager.Config);
            manager.StartCollection();
            SessionState.EraseString(CollectionReadyAtKey);
            LogScene("Editor 已稳定，采集已开始。");
        }

        private static void TickUploading()
        {
            if (!uploadResultReceived)
                return;

            if (uploadSucceeded)
            {
                PostBatchProgress("running", currentScene, "completed", null);
                TransitionTo(OrchestrationState.ExitingPlayMode);
                return;
            }

            HandleSceneFailure(string.IsNullOrEmpty(lastFailureMessage) ? "上传失败。" : lastFailureMessage);
        }

        private static void TickExitingPlayMode()
        {
            if (EditorApplication.isPlaying)
            {
                EditorApplication.isPlaying = false;
                return;
            }

            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            CleanupSceneRuntime();
            TransitionTo(OrchestrationState.PreparingNextScene);
        }

        private static void TickPreparingNextScene()
        {
            int nextIndex = SessionState.GetInt(ActiveSceneIndexKey, 0) + 1;
            if (nextIndex >= orchestrationConfig.scenes.Length)
            {
                FinishBatch(0, "全部场景已完成。");
                return;
            }

            uploadResultReceived = false;
            uploadSucceeded = false;
            PersistUploadResult(false, false);
            PersistOrchestrationState(orchestrationConfig, configFilePath, nextIndex, OrchestrationState.PreparingScene);
            TransitionTo(OrchestrationState.PreparingScene);
        }

        private static void TickAwaitingUserDecision()
        {
            if (EditorApplication.isPlaying)
            {
                EditorApplication.isPlaying = false;
                return;
            }

            if (EditorApplication.isPlayingOrWillChangePlaymode || EditorApplication.isCompiling || EditorApplication.isUpdating)
                return;

            if (EditorApplication.timeSinceStartup < nextCommandPollAt)
                return;

            nextCommandPollAt = EditorApplication.timeSinceStartup + CommandPollIntervalSeconds;

            string commandPath = GetCommandFilePath(orchestrationConfig.batchId);
            if (!File.Exists(commandPath))
                return;

            try
            {
                string commandJson = File.ReadAllText(commandPath);
                var command = JsonUtility.FromJson<XROrchestrationCommandFile>(commandJson);
                if (command == null)
                    throw new InvalidOperationException("控制命令解析失败。");
                if (command.schemaVersion != XROrchestrationCommandFile.SupportedSchemaVersion)
                    throw new InvalidOperationException($"不支持的控制命令 schemaVersion={command.schemaVersion}。");
                if (command.batchId != orchestrationConfig.batchId)
                    throw new InvalidOperationException("控制命令 batchId 不匹配。");
                if (WasCommandProcessed(command.commandId))
                {
                    File.Delete(commandPath);
                    return;
                }
                if (command.expectedSceneIndex != SessionState.GetInt(ActiveSceneIndexKey, 0))
                    return;
                if (command.expectedBatchItemId != SessionState.GetInt(ActiveBatchItemIdKey, 0))
                    return;

                int pendingDecisionVersion = SessionState.GetInt(PendingDecisionVersionKey, 0);
                if (command.decisionVersion > 0 && command.decisionVersion < pendingDecisionVersion)
                    return;

                switch (command.action)
                {
                    case "retry":
                        if (command.retrySceneConfig == null)
                            throw new InvalidOperationException("retry 命令缺少 retrySceneConfig。");
                        HandleRetryCommand(command);
                        break;
                    case "skip":
                        HandleSkipCommand();
                        break;
                    case "abort":
                        FinishBatch(0, "用户终止整批。", "cancelled");
                        break;
                    default:
                        LogOrchestration("忽略未知控制命令 action=" + command.action);
                        return;
                }
                MarkCommandProcessed(command.commandId);
                File.Delete(commandPath);
            }
            catch (Exception exception)
            {
                LogOrchestration("处理控制命令失败：" + exception.Message);
            }
        }

        private static void HandleRetryCommand(XROrchestrationCommandFile command)
        {
            if (command.retrySceneConfig == null)
            {
                LogOrchestration("retry 命令缺少 retrySceneConfig，保持等待。");
                return;
            }

            currentScene = command.retrySceneConfig;
            orchestrationConfig.scenes[SessionState.GetInt(ActiveSceneIndexKey, 0)] = currentScene;
            uploadResultReceived = false;
            uploadSucceeded = false;
            PersistUploadResult(false, false);
            lastFailureMessage = null;
            PersistSceneCursor(currentScene, OrchestrationState.PreparingScene);
            PostBatchProgress("running", currentScene, null, null);
            LogScene("收到 retry 命令，重新运行当前场景。");
            TransitionTo(OrchestrationState.PreparingScene);
        }

        private static void HandleSkipCommand()
        {
            PostBatchProgress("running", currentScene, "skipped", null);
            LogScene("收到 skip 命令，跳过当前场景。");
            TransitionTo(OrchestrationState.PreparingNextScene);
        }

        private static void OnPlayModeStateChanged(PlayModeStateChange playModeChange)
        {
            if (!IsOrchestrationActive())
                return;

            if (playModeChange == PlayModeStateChange.EnteredPlayMode && state == OrchestrationState.EnteringPlayMode)
            {
                SessionState.SetString(
                    CollectionReadyAtKey,
                    (EditorApplication.timeSinceStartup + CollectionReadyDelaySeconds).ToString("R"));
                RequestFlythroughIfConfigured();
                TransitionTo(OrchestrationState.Collecting);
                return;
            }

            if (playModeChange == PlayModeStateChange.ExitingPlayMode)
            {
                DetachManagerCallbacks();
                SessionState.EraseString(CollectionReadyAtKey);
            }
        }

        private static void OnDataUploaded(bool success)
        {
            uploadResultReceived = true;
            uploadSucceeded = success;
            PersistUploadResult(true, success);
            if (!success)
                lastFailureMessage = "上传失败。";
            TransitionTo(OrchestrationState.Uploading);
        }

        private static void OnSessionStopped()
        {
            var manager = FindManager();
            if (manager == null || manager.Config == null || !manager.Config.enableNetworkUpload)
            {
                uploadResultReceived = true;
                uploadSucceeded = true;
                PersistUploadResult(true, true);
            }

            // Stop TickCollecting from starting a second collection while the
            // asynchronous upload is still authenticating or building its payload.
            TransitionTo(OrchestrationState.Uploading);
        }

        private static void ReapplyConfigWhileCollectingOnce()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
                return;
            }

            var manager = FindManager();
            if (manager == null || !manager.IsCollecting || currentScene == null)
            {
                EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
                return;
            }

            EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
            XRBatchTestRunner.ApplySceneRunConfig(manager, currentScene, orchestrationConfig);
            manager.Initialize(manager.Config);
            manager.EnsureCollectorsActiveAfterReload();
            RequestFlythroughIfConfigured();
            AttachManagerCallbacks(manager);
            LogScene("脚本重载后已恢复进行中的采集任务。");
        }

        private static void TransitionTo(OrchestrationState nextState)
        {
            state = nextState;
            SessionState.SetInt(OrchestrationStateKey, (int)state);
        }

        private static void HandleSceneFailure(string message)
        {
            if (state == OrchestrationState.AwaitingUserDecision)
                return;

            lastFailureMessage = message;
            LogSceneError(message);

            var manager = FindManager();
            if (manager != null)
            {
                DetachManagerCallbacks();
                CleanupManagerSafely(manager, "场景失败");
            }

            uploadResultReceived = false;
            uploadSucceeded = false;
            PersistUploadResult(false, false);
            SessionState.EraseString(CollectionReadyAtKey);
            SchedulePlayModeExit();

            PostBatchProgress("awaiting_user_decision", currentScene, "failed", message);
            SessionState.SetInt(PendingDecisionVersionKey, SessionState.GetInt(PendingDecisionVersionKey, 0) + 1);
            nextCommandPollAt = EditorApplication.timeSinceStartup;
            TransitionTo(OrchestrationState.AwaitingUserDecision);
        }

        private static void FinishBatch(int exitCode, string message, string batchStatus = null)
        {
            if (shutdownScheduled)
                return;
            shutdownScheduled = true;

            DetachAllCallbacks();
            CleanupSceneRuntime();
            SchedulePlayModeExit();

            bool quitEditor = orchestrationConfig != null && orchestrationConfig.quitOnComplete;
            if (orchestrationConfig != null)
            {
                string status = batchStatus ?? (exitCode == 0 ? "completed" : "failed");
                PostBatchProgress(status, currentScene, null, message);
            }

            LogOrchestration(message);

            if (!quitEditor)
            {
                ClearOrchestrationSessionState();
                Debug.Log("[XROrchestrationRunner] 编排结束，保持 Unity Editor 打开。");
                return;
            }

            SessionState.SetBool(QuitOnCompleteKey, true);
            SessionState.SetInt(PendingExitCodeKey, exitCode);
            SessionState.SetString(
                ExitReadyAtKey,
                (EditorApplication.timeSinceStartup + ExitDelayAfterUploadSeconds).ToString("R"));
            ClearOrchestrationSessionState();
            XRBatchTestRunner.ScheduleEditorExitPollingInternal();
            Debug.Log($"[XROrchestrationRunner] 已安排 Editor 退出（exitCode={exitCode}）。");
        }

        private static void PollStopRequest()
        {
            if (orchestrationConfig == null || orchestrationConfig.parentTaskId <= 0)
                return;

            string path = Path.GetFullPath($"Library/XRDataCollector/stop-task-{orchestrationConfig.parentTaskId}");
            if (!File.Exists(path))
                return;

            File.Delete(path);
            LogOrchestration($"收到网页停止请求，父任务 {orchestrationConfig.parentTaskId}。");
            FinishBatch(0, "用户停止整批。", "cancelled");
        }

        private static void CleanupSceneRuntime()
        {
            DetachManagerCallbacks();

            var manager = FindManager();
            if (manager != null)
                CleanupManagerSafely(manager, "场景切换");

            TestDataUploader.DestroyInstance();
            SessionState.EraseString(CollectionReadyAtKey);
        }

        private static void CleanupManagerSafely(XRTestManager manager, string context)
        {
            if (manager == null)
                return;

            try
            {
                if (manager.IsCollecting)
                    manager.StopCollection(false);
            }
            catch (Exception exception)
            {
                LogOrchestration($"{context}时停止采集失败，继续清理：{exception.Message}");
            }

            try
            {
                manager.PrepareForShutdown();
            }
            catch (Exception exception)
            {
                LogOrchestration($"{context}时关闭采集器失败，继续清理：{exception.Message}");
            }
        }

        private static void AttachManagerCallbacks(XRTestManager manager)
        {
            if (manager == null)
                return;

            manager.OnDataUploaded -= OnDataUploaded;
            manager.OnDataUploaded += OnDataUploaded;
            manager.OnSessionStopped -= OnSessionStopped;
            manager.OnSessionStopped += OnSessionStopped;
        }

        private static void DetachManagerCallbacks()
        {
            var manager = FindManager();
            if (manager == null)
                return;

            manager.OnDataUploaded -= OnDataUploaded;
            manager.OnSessionStopped -= OnSessionStopped;
        }

        private static void DetachAllCallbacks()
        {
            EditorApplication.update -= Tick;
            EditorApplication.update -= ReapplyConfigWhileCollectingOnce;
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            DetachManagerCallbacks();
        }

        private static void SchedulePlayModeExit()
        {
            EditorApplication.delayCall += () =>
            {
                if (EditorApplication.isPlaying)
                    EditorApplication.isPlaying = false;
            };
        }

        private static bool EditorReadyForScenePrep()
        {
            return !EditorApplication.isPlaying &&
                   !EditorApplication.isPlayingOrWillChangePlaymode &&
                   !EditorApplication.isCompiling &&
                   !EditorApplication.isUpdating;
        }

        private static XRTestManager FindManager()
        {
            return XRTestManager.Instance != null
                ? XRTestManager.Instance
                : UnityEngine.Object.FindObjectOfType<XRTestManager>();
        }

        private static void RequestFlythroughIfConfigured()
        {
            if (currentScene == null || !currentScene.forceAutoFlythroughOnStart)
                return;
            TestSceneFlythroughActivator.RequestActivation(FindManager());
        }

        private static XRSceneRunConfig ResolveCurrentScene(XROrchestrationTaskConfig config)
        {
            if (config?.scenes == null || config.scenes.Length == 0)
                return null;

            int index = SessionState.GetInt(ActiveSceneIndexKey, 0);
            if (index < 0 || index >= config.scenes.Length)
                return null;

            return config.scenes[index];
        }

        private static bool TryLoadPersistedConfig(out XROrchestrationTaskConfig config, out string path)
        {
            config = null;
            path = SessionState.GetString(ConfigPathKey, string.Empty);
            if (string.IsNullOrEmpty(path) || !File.Exists(path))
                return false;

            string json = File.ReadAllText(path);
            return XROrchestrationConfigParser.TryParse(json, out config, out _);
        }

        private static void PersistOrchestrationState(
            XROrchestrationTaskConfig config,
            string path,
            int sceneIndex,
            OrchestrationState nextState)
        {
            SessionState.SetBool(ActiveFlagKey, true);
            SessionState.SetString(ConfigPathKey, path);
            SessionState.SetInt(ActiveBatchIdKey, config.batchId);
            SessionState.SetInt(ActiveSceneIndexKey, sceneIndex);
            SessionState.SetInt(OrchestrationStateKey, (int)nextState);
            SessionState.SetBool(QuitOnCompleteKey, config.quitOnComplete);
            state = nextState;
            currentScene = ResolveCurrentScene(config);
            if (currentScene != null)
                PersistSceneCursor(currentScene, nextState);
        }

        private static void PersistSceneCursor(XRSceneRunConfig scene, OrchestrationState nextState)
        {
            SessionState.SetInt(ActiveBatchItemIdKey, scene.batchItemId);
            SessionState.SetInt(ActiveAttemptKey, scene.attempt > 0 ? scene.attempt : 1);
            SessionState.SetInt(OrchestrationStateKey, (int)nextState);
            currentScene = scene;
        }

        private static void ClearOrchestrationSessionState()
        {
            SessionState.EraseBool(ActiveFlagKey);
            SessionState.EraseString(ConfigPathKey);
            SessionState.EraseInt(ActiveBatchIdKey);
            SessionState.EraseInt(ActiveSceneIndexKey);
            SessionState.EraseInt(ActiveBatchItemIdKey);
            SessionState.EraseInt(ActiveAttemptKey);
            SessionState.EraseInt(OrchestrationStateKey);
            SessionState.EraseInt(PendingDecisionVersionKey);
            SessionState.EraseString(ProcessedCommandIdsKey);
            SessionState.EraseString(CollectionReadyAtKey);
            SessionState.EraseString(ExitReadyAtKey);
            SessionState.EraseBool(UploadResultReceivedKey);
            SessionState.EraseBool(UploadSucceededKey);
            orchestrationConfig = null;
            configFilePath = null;
            currentScene = null;
            state = OrchestrationState.Idle;
        }

        private static string GetCommandFilePath(int batchId)
        {
            return Path.GetFullPath($"Library/XRDataCollector/orchestration-command-{batchId}.json");
        }

        private static void PersistUploadResult(bool received, bool succeeded)
        {
            SessionState.SetBool(UploadResultReceivedKey, received);
            SessionState.SetBool(UploadSucceededKey, succeeded);
        }

        private static bool WasCommandProcessed(string commandId)
        {
            if (string.IsNullOrEmpty(commandId))
                return false;

            string processed = SessionState.GetString(ProcessedCommandIdsKey, string.Empty);
            return processed.IndexOf("|" + commandId + "|", StringComparison.Ordinal) >= 0;
        }

        private static void MarkCommandProcessed(string commandId)
        {
            if (string.IsNullOrEmpty(commandId))
                return;

            string processed = SessionState.GetString(ProcessedCommandIdsKey, string.Empty);
            if (processed.IndexOf("|" + commandId + "|", StringComparison.Ordinal) >= 0)
                return;

            if (string.IsNullOrEmpty(processed))
                processed = "|";
            SessionState.SetString(ProcessedCommandIdsKey, processed + commandId + "|");
        }

        private static void PostBatchProgress(
            string batchStatus,
            XRSceneRunConfig scene,
            string sceneStatus,
            string errorMessage)
        {
            if (orchestrationConfig == null || string.IsNullOrEmpty(orchestrationConfig.progressUrl))
                return;

            var payload = new OrchestrationProgressPayload
            {
                task_id = orchestrationConfig.parentTaskId,
                session_id = scene?.platformSessionId ?? 0,
                phase = ResolveProgressPhase(sceneStatus),
                phase_label = ResolveProgressPhaseLabel(sceneStatus),
                progress = ResolveSceneProgress(sceneStatus),
                run_mode = XROrchestrationTaskConfig.RunModeMultiScene,
                batch_id = orchestrationConfig.batchId,
                batch_status = batchStatus,
                batch_item_id = scene?.batchItemId ?? 0,
                scene_index = scene?.sceneIndex ?? SessionState.GetInt(ActiveSceneIndexKey, 0),
                scene_total = scene?.sceneTotal ?? orchestrationConfig.scenes.Length,
                scene_session_id = scene?.platformSessionId ?? 0,
                scene_task_id = scene?.taskId ?? 0,
                attempt = scene?.attempt ?? SessionState.GetInt(ActiveAttemptKey, 1),
                scene_progress = ResolveSceneProgress(sceneStatus),
                overall_progress = ResolveOverallProgress(scene, sceneStatus),
                scene_display_name = ResolveSceneDisplayName(scene),
                scene_status = sceneStatus ?? string.Empty,
                error_message = errorMessage ?? string.Empty
            };

            EditorApplication.delayCall += () => SendProgressRequest(payload);
        }

        private static float ResolveSceneProgress(string sceneStatus)
        {
            if (sceneStatus == "completed" || sceneStatus == "skipped")
                return 1f;
            return 0f;
        }

        private static float ResolveOverallProgress(XRSceneRunConfig scene, string sceneStatus)
        {
            int sceneTotal = Math.Max(scene?.sceneTotal ?? orchestrationConfig?.scenes?.Length ?? 1, 1);
            int sceneIndex = scene?.sceneIndex ?? SessionState.GetInt(ActiveSceneIndexKey, 0);
            return Mathf.Clamp01((sceneIndex + ResolveSceneProgress(sceneStatus)) / sceneTotal);
        }

        private static string ResolveProgressPhase(string sceneStatus)
        {
            if (sceneStatus == "completed" || sceneStatus == "skipped")
                return "scene_completed";
            if (sceneStatus == "failed")
                return "scene_failed";
            return "orchestration";
        }

        private static string ResolveProgressPhaseLabel(string sceneStatus)
        {
            if (sceneStatus == "completed")
                return "场景完成";
            if (sceneStatus == "skipped")
                return "场景已跳过";
            if (sceneStatus == "failed")
                return "等待失败决策";
            return "场景编排";
        }

        private static void SendProgressRequest(OrchestrationProgressPayload payload)
        {
            if (orchestrationConfig == null || string.IsNullOrEmpty(orchestrationConfig.progressUrl))
                return;

            try
            {
                byte[] body = System.Text.Encoding.UTF8.GetBytes(JsonUtility.ToJson(payload));
                using (var request = new UnityWebRequest(orchestrationConfig.progressUrl, "POST"))
                {
                    request.uploadHandler = new UploadHandlerRaw(body);
                    request.downloadHandler = new DownloadHandlerBuffer();
                    request.SetRequestHeader("Content-Type", "application/json");
                    if (!string.IsNullOrEmpty(orchestrationConfig.deviceToken))
                        request.SetRequestHeader("X-Device-Token", orchestrationConfig.deviceToken);
                    request.timeout = 8;
                    var operation = request.SendWebRequest();
                    while (!operation.isDone)
                    {
                    }
                }
            }
            catch (Exception exception)
            {
                LogOrchestration("进度上报失败：" + exception.Message);
            }
        }

        private static string ResolveSceneDisplayName(XRSceneRunConfig scene)
        {
            if (scene == null)
                return "Unknown";

            if (!string.IsNullOrEmpty(scene.sceneDisplayName))
                return scene.sceneDisplayName;
            if (!string.IsNullOrEmpty(scene.sessionName))
                return scene.sessionName;
            if (string.IsNullOrEmpty(scene.unityScenePath))
                return "Unknown";

            return Path.GetFileNameWithoutExtension(scene.unityScenePath.Replace("\\", "/"));
        }

        private static void LogOrchestration(string message)
        {
            int batchId = orchestrationConfig?.batchId ?? SessionState.GetInt(ActiveBatchIdKey, 0);
            Debug.Log($"[批次 {batchId}] {message}");
        }

        private static void LogScene(string message)
        {
            Debug.Log(BuildSceneLogPrefix() + message);
        }

        private static void LogSceneError(string message)
        {
            Debug.LogError(BuildSceneLogPrefix() + message);
        }

        private static string BuildSceneLogPrefix()
        {
            int batchId = orchestrationConfig?.batchId ?? SessionState.GetInt(ActiveBatchIdKey, 0);
            var scene = currentScene ?? ResolveCurrentScene(orchestrationConfig);
            int sceneIndex = scene?.sceneIndex ?? SessionState.GetInt(ActiveSceneIndexKey, 0);
            int sceneTotal = scene?.sceneTotal ?? orchestrationConfig?.scenes?.Length ?? 0;
            int attempt = scene?.attempt ?? SessionState.GetInt(ActiveAttemptKey, 1);
            string sceneName = ResolveSceneDisplayName(scene);
            int displayIndex = sceneIndex + 1;
            return $"[批次 {batchId}][场景 {displayIndex}/{Math.Max(sceneTotal, displayIndex)} {sceneName}][尝试 {attempt}] ";
        }

        [Serializable]
        private class OrchestrationProgressPayload
        {
            public int task_id;
            public int session_id;
            public string phase;
            public string phase_label;
            public float progress;
            public string run_mode;
            public int batch_id;
            public string batch_status;
            public int batch_item_id;
            public int scene_index;
            public int scene_total;
            public int scene_session_id;
            public int scene_task_id;
            public int attempt;
            public float scene_progress;
            public float overall_progress;
            public string scene_display_name;
            public string scene_status;
            public string error_message;
        }
    }
}
