from app.utils.session_display import get_session_scene_display_name


def test_scene_display_name_prefers_resource_name():
    name = get_session_scene_display_name(
        config={"scene_resource_name": "Lobby", "unity_scene_path": "Assets/Scenes/Battle.unity"},
        scene_id=3,
    )
    assert name == "Lobby"


def test_scene_display_name_falls_back_to_scene_path_stem():
    name = get_session_scene_display_name(
        config={"unity_scene_path": "Assets/Scenes/Battle.unity"},
        scene_id=3,
    )
    assert name == "Battle"
