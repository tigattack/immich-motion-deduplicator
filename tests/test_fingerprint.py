import pytest  # pyright: ignore[reportMissingImports]

from immich_motion_deduplicator import fingerprint


def test_sha256_file_same_content_same_hash(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    data = b"same content"
    first.write_bytes(data)
    second.write_bytes(data)

    assert fingerprint.sha256_file(str(first)) == fingerprint.sha256_file(str(second))


def test_sha256_file_different_content_different_hash(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"content-a")
    second.write_bytes(b"content-b")

    assert fingerprint.sha256_file(str(first)) != fingerprint.sha256_file(str(second))


def test_videos_match_byte_identical_files_uses_checksum(tmp_path):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    payload = b"identical video bytes"
    first.write_bytes(payload)
    second.write_bytes(payload)

    assert fingerprint.videos_match(str(first), str(second)) == (True, "checksum", 1.0)


def test_videos_match_returns_none_when_perceptual_hashes_are_empty(tmp_path, monkeypatch):
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"video-a")
    second.write_bytes(b"video-b")

    monkeypatch.setattr(fingerprint, "perceptual_hashes", lambda path, fps=5.0: [])

    assert fingerprint.videos_match(str(first), str(second)) == (False, "none", 0.0)


def test_extract_frames_raises_runtime_error_when_ffmpeg_missing(monkeypatch, tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not real video")

    def fake_popen(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(fingerprint.subprocess, "Popen", fake_popen)

    with pytest.raises(RuntimeError, match="ffmpeg not found"):
        fingerprint.extract_frames(str(video))
