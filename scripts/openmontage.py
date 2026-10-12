#!/usr/bin/env python3
"""Local readiness, export validation, and verified GitHub MP4 delivery."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


class WorkflowError(RuntimeError):
    pass


def run(args, *, cwd=None, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        # Commands are argument arrays; prompt text and file paths never become shell code.
        raise WorkflowError(f"{args[0]} failed: {(result.stderr or result.stdout).strip()[-2500:]}")
    return result.stdout.strip()


def config():
    return json.loads((ROOT / "openmontage.json").read_text())


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_video(path, *, duration, width, height, fps, audio, decode=True):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() != ".mp4" or path.stat().st_size == 0:
        raise WorkflowError("A nonempty .mp4 file is required.")
    if not all(math.isfinite(v) and v > 0 for v in (duration, width, height, fps)):
        raise WorkflowError("Expected duration, dimensions, and FPS must be positive finite values.")
    data = json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    videos = [s for s in data["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1 or "mp4" not in data["format"]["format_name"].split(","):
        raise WorkflowError("Expected an MP4 container with exactly one video stream.")
    video = videos[0]
    actual_fps = float(Fraction(video["avg_frame_rate"]))
    actual_duration = float(video.get("duration", data["format"]["duration"]))
    audio_streams = [s for s in data["streams"] if s["codec_type"] == "audio"]
    errors = []
    if (video["width"], video["height"]) != (width, height):
        errors.append(f"Resolution is {video['width']}x{video['height']}; expected {width}x{height}.")
    if abs(actual_fps - fps) > .001:
        errors.append(f"FPS is {actual_fps}; expected {fps}.")
    if abs(actual_duration - duration) > max(.001, .51 / fps):
        errors.append(f"Video duration is {actual_duration}s; expected {duration}s.")
    expected_frames = round(duration * fps)
    if video.get("nb_frames") and int(video["nb_frames"]) != expected_frames:
        errors.append(f"Frame count is {video['nb_frames']}; expected {expected_frames}.")
    if video["codec_name"] != "h264" or video.get("pix_fmt") not in {"yuv420p", "yuvj420p"}:
        errors.append("Deliver H.264 in 8-bit 4:2:0 for compatible MP4 playback.")
    if audio == "none" and audio_streams:
        errors.append("The silent contract requires zero audio streams, including empty tracks.")
    if audio == "required" and not audio_streams:
        errors.append("The current brief requires audio, but no audio stream is present.")
    if errors:
        raise WorkflowError(" ".join(errors))
    if decode:
        run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(path), "-f", "null", "-"])
    return {"path": str(path), "duration_seconds": actual_duration, "width": width,
            "height": height, "fps": actual_fps, "frames": expected_frames,
            "audio_streams": len(audio_streams), "codec": video["codec_name"],
            "bytes": path.stat().st_size, "sha256": sha256(path), "full_decode_passed": decode}


def require_review(review_path, video_path):
    review_path = Path(review_path).resolve()
    review = json.loads(review_path.read_text())
    if review.get("status") != "pass":
        raise WorkflowError("Final review must pass before publishing.")
    reviewed_path = Path(review.get("output_path", ""))
    if not reviewed_path.is_absolute():
        reviewed_path = review_path.parent / reviewed_path
    if reviewed_path.resolve() != Path(video_path).resolve():
        raise WorkflowError("Final review refers to a different output file.")
    if review.get("metadata", {}).get("export_sha256") != sha256(video_path):
        raise WorkflowError("Final review must record metadata.export_sha256 matching this exact export; re-review changed files.")
    visual = review.get("checks", {}).get("visual_spotcheck", {})
    paths = visual.get("frame_paths", [])
    if visual.get("frames_sampled", 0) < 4 or len(paths) < 4:
        raise WorkflowError("Inspect and record at least four exported frames before publishing.")
    for name in ("black_frames_detected", "broken_overlays", "missing_assets", "unreadable_text"):
        if visual.get(name) is not False:
            raise WorkflowError(f"Visual review has not cleared {name}.")
    for frame in paths:
        candidate = Path(frame)
        if not candidate.is_absolute():
            candidate = review_path.parent / candidate
        if not candidate.is_file() or candidate.stat().st_size == 0:
            raise WorkflowError(f"Missing recorded review frame: {candidate.name}")
    return review


def slug(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", value):
        raise WorkflowError("Project ID must use lowercase letters, digits, and hyphens (1–80 characters).")
    return value


def check_target(repo, delivery):
    target = delivery["repository"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", target):
        raise WorkflowError("Invalid configured GitHub repository.")
    branch = delivery["branch"]
    run(["git", "check-ref-format", f"refs/heads/{branch}"])
    remote = urllib.parse.urlsplit(run(["git", "-C", str(repo), "remote", "get-url", "origin"]))
    remote_repo = remote.path.removeprefix("/").removesuffix(".git").rstrip("/")
    if remote.scheme != "https" or remote.hostname != "github.com" or remote.username or remote.password or remote_repo.lower() != target.lower():
        raise WorkflowError("origin must be the configured HTTPS GitHub repository; no credential-bearing URLs.")
    folder = PurePosixPath(delivery["directory"])
    if folder.is_absolute() or ".." in folder.parts or not folder.parts:
        raise WorkflowError("Invalid repository delivery directory.")
    return target, branch, folder


def download_matches(url, expected, expected_bytes, *, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "OpenMontage-Codex-Delivery/1"})
            with urllib.request.urlopen(request, timeout=45) as response:
                if response.status != 200:
                    raise WorkflowError(f"Download returned HTTP {response.status}.")
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != expected or size != expected_bytes:
                raise WorkflowError("The complete HTTPS download did not match the verified MP4.")
            return
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2 ** (attempt + 1))
    raise WorkflowError(f"Upload exists, but HTTPS download verification failed: {last_error}")


def publish(video_path, review_path, project, expected, *, repo=ROOT, settings=None):
    settings = settings or config()
    delivery = settings["delivery"]
    repo = Path(repo).resolve()
    video_path = Path(video_path).resolve()
    target, branch, folder = check_target(repo, delivery)
    project = slug(project)
    require_review(review_path, video_path)
    verified = verify_video(video_path, **expected)
    if verified["bytes"] > delivery["maximum_file_bytes"]:
        raise WorkflowError("MP4 exceeds the configured 95 MB GitHub file limit; optimize and re-review before publishing.")
    filename = re.sub(r"[^a-z0-9-]+", "-", video_path.stem.lower()).strip("-")[:60] or "video"
    relative = str(folder / project / f"{filename}-{verified['sha256'][:12]}.mp4")
    base_cmd = ["git", "-C", str(repo)]
    blob = run(base_cmd + ["hash-object", "-w", str(video_path)])
    # Only this temporary index sees the video; the user's index/worktree are untouched.
    with tempfile.TemporaryDirectory(prefix="openmontage-index-") as temporary:
        index_env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        author_name = subprocess.run(base_cmd + ["config", "user.name"], capture_output=True, text=True).stdout.strip() or "OpenMontage"
        author_email = subprocess.run(base_cmd + ["config", "user.email"], capture_output=True, text=True).stdout.strip() or "openmontage@users.noreply.github.com"
        commit_env = dict(index_env, GIT_AUTHOR_NAME=author_name, GIT_AUTHOR_EMAIL=author_email,
                          GIT_COMMITTER_NAME=author_name, GIT_COMMITTER_EMAIL=author_email)
        for attempt in range(3):
            run(base_cmd + ["fetch", "--no-tags", "origin", f"refs/heads/{branch}"])
            head = run(base_cmd + ["rev-parse", "FETCH_HEAD"])
            existing = subprocess.run(base_cmd + ["rev-parse", f"{head}:{relative}"], capture_output=True, text=True)
            if existing.returncode == 0:
                if existing.stdout.strip() != blob:
                    raise WorkflowError("Destination collision; refuse to overwrite an earlier deliverable.")
                commit = head
                break
            run(base_cmd + ["read-tree", head], env=index_env)
            run(base_cmd + ["update-index", "--add", "--cacheinfo", "100644", blob, relative], env=index_env)
            tree = run(base_cmd + ["write-tree"], env=index_env)
            commit = run(base_cmd + ["commit-tree", tree, "-p", head, "-m", f"Deliver OpenMontage video: {project}"], env=commit_env)
            pushed = subprocess.run(base_cmd + ["push", "origin", f"{commit}:refs/heads/{branch}"], capture_output=True, text=True)
            if pushed.returncode == 0:
                break
            current = run(base_cmd + ["ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"]).split()[0]
            if current == head or attempt == 2:
                raise WorkflowError(f"GitHub upload failed (no force-push attempted): {pushed.stderr.strip()[-2000:]}")
        else:
            raise WorkflowError("Repository changed repeatedly; retry publication.")
    encoded_path = urllib.parse.quote(relative, safe="/")
    url = f"https://github.com/{target}/raw/{commit}/{encoded_path}"
    download_matches(url, verified["sha256"], verified["bytes"])
    return {"status": "verified", "download_url": url, "repository": target,
            "commit": commit, "repository_path": relative, "project_id": project,
            "timestamp": datetime.now(timezone.utc).isoformat(), "video": verified}


def doctor(settings, render=False):
    problems, checks = [], {}
    for name in ("git", "node", "npm", "ffmpeg", "ffprobe"):
        checks[name] = shutil.which(name)
        if not checks[name]:
            problems.append(f"Missing executable: {name}")
    engine = Path(settings["engine"]["directory"])
    python = Path(settings["engine"]["python"])
    browser = Path(settings["engine"]["browser"])
    for name, path in (("engine", engine / "AGENT_GUIDE.md"), ("python", python), ("chromium", browser), ("remotion", engine / "remotion-composer/node_modules/remotion/package.json")):
        checks[name] = path.exists()
        if not path.exists():
            problems.append(f"Missing prerequisite: {name}; run scripts/setup.sh.")
    if checks.get("engine"):
        checks["engine_revision"] = run(["git", "-C", str(engine), "rev-parse", "HEAD"])
        if checks["engine_revision"] != settings["engine"]["revision"]:
            problems.append("Engine revision differs from the configured pinned revision; do not reset user work.")
    if checks.get("engine") and checks.get("python"):
        try:
            checks["python_dependencies"] = run([str(python), "-c", "import jsonschema, yaml, PIL, requests, playwright; from tools.video.video_compose import VideoCompose; assert VideoCompose().get_info()['render_engines']['remotion']; print('passed')"], cwd=engine)
        except WorkflowError as error:
            problems.append(str(error))
    try:
        _, branch, _ = check_target(ROOT, settings["delivery"])
        checks["github_read"] = run(["git", "-C", str(ROOT), "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"]).split()[0]
    except WorkflowError as error:
        problems.append(str(error))
    if problems:
        raise WorkflowError(" ".join(problems))
    if render:
        checks["render_smoke"] = json.loads(run(["node", str(ROOT / "scripts/runtime_smoke.cjs"), str(engine), str(browser)]))
    return {"status": "ready", "local_checks": checks,
            "note": "Native Git read access verified; Git write is verified only by actual publishing. Optional paid providers and new website domains require prompt-specific checks."}


def parser():
    cfg = config()
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor")
    check.add_argument("--render", action="store_true", help="Exercise actual browser rendering and H.264 export.")
    for command in ("verify", "publish"):
        sub = commands.add_parser(command)
        sub.add_argument("video", type=Path)
        for name, kind in (("duration", float), ("width", int), ("height", int), ("fps", float)):
            key = "duration_seconds" if name == "duration" else name
            sub.add_argument(f"--{name}", type=kind, default=cfg["defaults"][key])
        sub.add_argument("--audio", choices=("none", "required", "any"), default=cfg["defaults"]["audio"])
        if command == "publish":
            sub.add_argument("--review", required=True, type=Path)
            sub.add_argument("--project", required=True)
            sub.add_argument("--receipt", type=Path)
    return cli


def main():
    args = parser().parse_args()
    try:
        if args.command == "doctor":
            result = doctor(config(), args.render)
        else:
            expected = {name: getattr(args, name) for name in ("duration", "width", "height", "fps", "audio")}
            if args.command == "verify":
                result = verify_video(args.video, **expected)
            else:
                result = publish(args.video, args.review, args.project, expected)
                if args.receipt:
                    args.receipt.parent.mkdir(parents=True, exist_ok=True)
                    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except (WorkflowError, OSError, ValueError, KeyError) as error:
        print(f"OpenMontage: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
