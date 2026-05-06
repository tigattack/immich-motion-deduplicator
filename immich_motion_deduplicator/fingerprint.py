import hashlib
import importlib
import subprocess
from io import BytesIO
from typing import Any, List


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def sha256_file(path: str) -> str:
    hasher = hashlib.sha256()

    with open(path, "rb") as file_obj:
        while True:
            chunk = file_obj.read(64 * 1024)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def _run_ffprobe_duration(path: str) -> float:
    process = subprocess.Popen(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = process.communicate()
    try:
        return float(stdout.decode("utf-8").strip() or 0.0)
    except ValueError:
        return 0.0


def _extract_frames_with_offset(path: str, fps: float, start_seconds: float = 0.0):
    command = [
        "ffmpeg",
        "-i",
        path,
    ]
    if start_seconds > 0:
        command.extend(["-ss", str(start_seconds)])
    command.extend(
        [
            "-vf",
            f"fps={fps}",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]
    )

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = process.communicate()

    frames = []
    for chunk in stdout.split(PNG_MAGIC):
        if not chunk:
            continue
        from PIL import Image  # type: ignore[reportMissingImports]

        image = Image.open(BytesIO(PNG_MAGIC + chunk))
        frames.append(image.copy())
        image.close()

    return frames


def extract_frames(path: str, fps: float = 5.0) -> List[Any]:
    try:
        frames = _extract_frames_with_offset(path, fps)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found")

    if frames:
        return frames

    duration = _run_ffprobe_duration(path)
    if duration <= 0:
        return []

    try:
        frames = _extract_frames_with_offset(path, fps, duration / 2.0)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found")

    return frames


def perceptual_hashes(path: str, fps: float = 5.0) -> List[Any]:
    try:
        imagehash = importlib.import_module("imagehash")
    except ImportError as exc:
        raise RuntimeError("imagehash not found") from exc

    frames = extract_frames(path, fps=fps)
    return [imagehash.phash(frame) for frame in frames]


def videos_match(
    path1: str,
    path2: str,
    hamming_threshold: int = 8,
    fps: float = 5.0,
) -> tuple[bool, str, float]:
    if sha256_file(path1) == sha256_file(path2):
        return True, "checksum", 1.0

    hashes1 = perceptual_hashes(path1, fps=fps)
    hashes2 = perceptual_hashes(path2, fps=fps)

    if not hashes1 or not hashes2:
        return False, "none", 0.0

    distances = [hash1 - hash2 for hash1, hash2 in zip(hashes1, hashes2)]
    if not distances:
        return False, "none", 0.0

    average_distance = sum(distances) / float(len(distances))
    if average_distance <= hamming_threshold:
        return True, "perceptual", 1.0 - (average_distance / 64.0)

    return False, "none", 0.0
