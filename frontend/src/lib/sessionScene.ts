type SessionSceneSource = {
  scene_display_name?: string | null;
  scene_id?: number | null;
  config?: Record<string, unknown> | null;
};

export function getSessionSceneLabel(session: SessionSceneSource): string {
  if (session.scene_display_name && session.scene_display_name.trim()) {
    return session.scene_display_name.trim();
  }

  const config = session.config || {};
  const nameKeys = ['scene_resource_name', 'scene_name', 'sceneName', 'unity_scene_name'];
  for (const key of nameKeys) {
    const value = config[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }

  const pathValue = config.unity_scene_path ?? config.unityScenePath;
  if (typeof pathValue === 'string' && pathValue.trim()) {
    const fileName = pathValue.replace(/\\/g, '/').split('/').pop() || '';
    const stem = fileName.replace(/\.unity$/i, '');
    if (stem) return stem;
  }

  if (session.scene_id) {
    return `场景 #${session.scene_id}`;
  }
  return '-';
}
