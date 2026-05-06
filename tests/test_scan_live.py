import csv
from unittest.mock import MagicMock

import pytest

import immich_motion_deduplicator.scan_live as scan_live_module
from immich_motion_deduplicator.scan_live import CSV_FIELDNAMES, run


def _make_fake_require_env(csv_path):
    def fake_require_env(key):
        return {
            "IMMICH_API_KEY": "test-api-key",
            "LIVE_CANDIDATES_CSV": str(csv_path),
            "IMMICH_SERVER_PATH_PREFIX": "/srv",
        }[key]
    return fake_require_env


def _silent_console():
    m = MagicMock()
    m.print = MagicMock()
    m.log = MagicMock()
    return m


def _apply_common_mocks(monkeypatch, tmp_path):
    csv_path = tmp_path / "out.csv"
    monkeypatch.setattr(scan_live_module, "get_immich_api_url", lambda: "http://test")
    monkeypatch.setattr(scan_live_module, "require_env", _make_fake_require_env(csv_path))
    monkeypatch.setattr(scan_live_module, "require_directory_env", lambda key: str(tmp_path))
    monkeypatch.setattr(scan_live_module, "console", _silent_console())
    monkeypatch.setattr(scan_live_module, "error_console", _silent_console())
    monkeypatch.setattr(scan_live_module, "print_summary", lambda *args, **kwargs: None)
    return csv_path


def _read_csv_rows(csv_path):
    with open(str(csv_path), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture
def live_photo():
    return {
        "id": "photo-1",
        "livePhotoVideoId": "vid-motion-1",
        "localDateTime": "2024-01-01T12:00:00",
    }


@pytest.fixture
def motion_video():
    return {
        "id": "vid-motion-1",
        "localDateTime": "2024-01-01T12:00:00",
        "originalPath": "/srv/motion.mp4",
    }


def test_live_photo_video_id_excluded_from_standalone_candidates(
    monkeypatch, tmp_path, live_photo, motion_video
):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(
        scan_live_module,
        "search_assets",
        MagicMock(side_effect=[[live_photo], [motion_video]]),
    )
    monkeypatch.setattr(
        scan_live_module, "videos_match", MagicMock(return_value=(True, "perceptual", 1.0))
    )

    result = run()

    assert result == 0
    assert _read_csv_rows(csv_path) == []


def test_time_window_asset_within_window_is_candidate(
    monkeypatch, tmp_path, live_photo, motion_video
):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)

    standalone_file = tmp_path / "standalone.mp4"
    standalone_file.write_bytes(b"fake-video")
    motion_file = tmp_path / "motion.mp4"
    motion_file.write_bytes(b"fake-video")

    standalone_video_30s_after = {
        "id": "vid-standalone-1",
        "localDateTime": "2024-01-01T12:00:30",
        "originalPath": "/srv/standalone.mp4",
    }

    monkeypatch.setattr(
        scan_live_module,
        "search_assets",
        MagicMock(side_effect=[[live_photo], [motion_video, standalone_video_30s_after]]),
    )

    def fake_resolve(path, prefix, root):
        return str(standalone_file) if path == "/srv/standalone.mp4" else str(motion_file)

    monkeypatch.setattr(scan_live_module, "resolve_server_path", fake_resolve)
    monkeypatch.setattr(
        scan_live_module, "videos_match", MagicMock(return_value=(True, "perceptual", 1.0))
    )

    result = run()

    assert result == 1
    rows = _read_csv_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]["asset_id"] == "vid-standalone-1"
    assert rows[0]["live_photo_asset_id"] == "photo-1"
    assert rows[0]["live_photo_video_asset_id"] == "vid-motion-1"


def test_time_window_asset_outside_window_skipped(
    monkeypatch, tmp_path, live_photo, motion_video
):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)

    standalone_video_1h_after = {
        "id": "vid-standalone-1",
        "localDateTime": "2024-01-01T13:00:00",
        "originalPath": "/srv/standalone.mp4",
    }

    monkeypatch.setattr(
        scan_live_module,
        "search_assets",
        MagicMock(side_effect=[[live_photo], [motion_video, standalone_video_1h_after]]),
    )
    monkeypatch.setattr(
        scan_live_module, "videos_match", MagicMock(return_value=(True, "perceptual", 1.0))
    )

    result = run()

    assert result == 0
    assert _read_csv_rows(csv_path) == []


def test_missing_original_path_skipped_no_crash(
    monkeypatch, tmp_path, live_photo, motion_video
):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)

    standalone_video_no_path = {
        "id": "vid-standalone-1",
        "localDateTime": "2024-01-01T12:00:30",
    }

    monkeypatch.setattr(
        scan_live_module,
        "search_assets",
        MagicMock(side_effect=[[live_photo], [motion_video, standalone_video_no_path]]),
    )
    monkeypatch.setattr(
        scan_live_module, "videos_match", MagicMock(return_value=(True, "perceptual", 1.0))
    )

    result = run()

    assert result == 0
    assert _read_csv_rows(csv_path) == []


def test_zero_candidates_csv_header_only(monkeypatch, tmp_path):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)
    monkeypatch.setattr(
        scan_live_module, "search_assets", MagicMock(side_effect=[[], []])
    )

    result = run()

    assert result == 0
    assert csv_path.exists()
    with open(str(csv_path), newline="", encoding="utf-8") as fh:
        content = fh.read()
    assert content.strip() == ",".join(CSV_FIELDNAMES)


def test_csv_output_has_correct_columns_and_asset_id(
    monkeypatch, tmp_path, live_photo, motion_video
):
    csv_path = _apply_common_mocks(monkeypatch, tmp_path)

    standalone_file = tmp_path / "standalone.mp4"
    standalone_file.write_bytes(b"fake-video")
    motion_file = tmp_path / "motion.mp4"
    motion_file.write_bytes(b"fake-video")

    standalone_video = {
        "id": "vid-standalone-1",
        "localDateTime": "2024-01-01T12:00:30",
        "originalPath": "/srv/standalone.mp4",
    }

    monkeypatch.setattr(
        scan_live_module,
        "search_assets",
        MagicMock(side_effect=[[live_photo], [motion_video, standalone_video]]),
    )

    def fake_resolve(path, prefix, root):
        return str(standalone_file) if path == "/srv/standalone.mp4" else str(motion_file)

    monkeypatch.setattr(scan_live_module, "resolve_server_path", fake_resolve)
    monkeypatch.setattr(
        scan_live_module, "videos_match", MagicMock(return_value=(True, "perceptual", 1.0))
    )

    run()

    rows = _read_csv_rows(csv_path)
    assert len(rows) == 1
    for field in CSV_FIELDNAMES:
        assert field in rows[0]
    assert rows[0]["asset_id"] == "vid-standalone-1"
    assert rows[0]["match_method"] == "perceptual"
    assert rows[0]["similarity_score"] == "1.0"
