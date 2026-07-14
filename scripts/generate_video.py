#!/usr/bin/env python3
"""Generate videos via grok-imagine-video (async: submit + poll)."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _norm_path(p: str) -> str:
    p = str(p).strip()
    if not p.startswith("/"):
        p = "/" + p
    return p


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (skill_dir() / "config.json")
    if not cfg_path.is_file():
        example = skill_dir() / "config.example.json"
        raise SystemExit(
            f"Missing config: {cfg_path}\n"
            f"Copy {example} to config.json and fill base_url + api_key."
        )
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {cfg_path}: {e}") from e

    base_url = str(data.get("base_url", "")).strip().rstrip("/")
    api_key = str(data.get("api_key", "")).strip()
    if not base_url or base_url.endswith("your-endpoint.example/v1"):
        raise SystemExit(f"Set a real base_url in {cfg_path}")
    if not api_key or api_key == "your-api-key":
        raise SystemExit(f"Set a real api_key in {cfg_path}")

    return {
        "base_url": base_url,
        "api_key": api_key,
        "video_model": str(data.get("video_model") or "grok-imagine-video"),
        "timeout_sec": int(data.get("timeout_sec") or 120),
        "video_timeout_sec": int(data.get("video_timeout_sec") or 600),
        "video_poll_interval_sec": float(data.get("video_poll_interval_sec") or 3),
        "video_default_duration": int(data.get("video_default_duration") or 6),
        "video_default_aspect_ratio": str(data.get("video_default_aspect_ratio") or "16:9"),
        "video_default_resolution": str(data.get("video_default_resolution") or "720p"),
        "video_generations_path": _norm_path(
            data.get("video_generations_path") or "/videos/generations"
        ),
        "video_status_path": str(data.get("video_status_path") or "/videos/{request_id}"),
    }


def ensure_requests():
    try:
        import requests  # noqa: F401
    except ImportError as e:
        raise SystemExit("Missing dependency: pip install requests") from e
    import requests

    return requests


def auth_headers(api_key: str, json_body: bool = True) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def post_json(url: str, api_key: str, body: dict[str, Any], timeout: int) -> Any:
    requests = ensure_requests()
    try:
        resp = requests.post(url, headers=auth_headers(api_key), json=body, timeout=timeout)
    except requests.exceptions.Timeout as e:
        raise SystemExit(f"Request timed out after {timeout}s: {url}") from e
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Request failed: {e}") from e
    if resp.status_code >= 400:
        raise SystemExit(f"HTTP {resp.status_code} from {url}\n{resp.text[:2000]}")
    try:
        return resp.json()
    except Exception as e:
        raise SystemExit(f"Non-JSON response from {url}: {resp.text[:500]}") from e


def get_json(url: str, api_key: str, timeout: int) -> Any:
    requests = ensure_requests()
    try:
        resp = requests.get(url, headers=auth_headers(api_key, json_body=False), timeout=timeout)
    except requests.exceptions.Timeout as e:
        raise SystemExit(f"Poll timed out after {timeout}s: {url}") from e
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Poll failed: {e}") from e
    if resp.status_code >= 400:
        raise SystemExit(f"HTTP {resp.status_code} from {url}\n{resp.text[:2000]}")
    try:
        return resp.json()
    except Exception as e:
        raise SystemExit(f"Non-JSON poll response from {url}: {resp.text[:500]}") from e


def dig(obj: Any, *keys: str) -> Any:
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def extract_request_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in (
        "request_id",
        "requestId",
        "id",
        "task_id",
        "taskId",
        "job_id",
        "jobId",
        "video_id",
        "videoId",
    ):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)):
            return str(val)
    for nest in ("data", "result", "task", "job", "video"):
        nested = payload.get(nest)
        if isinstance(nested, dict):
            rid = extract_request_id(nested)
            if rid:
                return rid
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            rid = extract_request_id(nested[0])
            if rid:
                return rid
    return None


def extract_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("status", "state", "phase"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    for nest in ("data", "result", "task", "job", "video"):
        nested = payload.get(nest)
        if isinstance(nested, dict):
            st = extract_status(nested)
            if st:
                return st
    return ""


def is_success(status: str, payload: Any) -> bool:
    if status in {
        "succeeded",
        "success",
        "successful",
        "completed",
        "complete",
        "done",
        "finished",
        "ready",
    }:
        return True
    # some gateways omit status but include video bytes/url
    return bool(extract_video_ref(payload))


def is_failure(status: str) -> bool:
    return status in {
        "failed",
        "failure",
        "error",
        "cancelled",
        "canceled",
        "timeout",
        "expired",
    }


def extract_video_ref(payload: Any) -> dict[str, str] | None:
    """Return {kind: url|b64|path, value: ...} if a final video is present."""
    found: list[dict[str, str]] = []

    def walk(obj: Any, depth: int = 0) -> None:
        if depth > 8 or obj is None:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = str(k).lower()
                if isinstance(v, str) and v.strip():
                    if kl in {
                        "b64_json",
                        "b64",
                        "video_b64",
                        "base64",
                        "video_base64",
                    } or (kl.endswith("_b64") and "video" in kl):
                        found.append({"kind": "b64", "value": v})
                    elif kl in {
                        "url",
                        "video_url",
                        "download_url",
                        "file_url",
                        "mp4_url",
                        "result_url",
                        "output_url",
                    } or (kl.endswith("_url") and ("video" in kl or "mp4" in kl or "result" in kl)):
                        found.append({"kind": "url", "value": v})
                    elif v.startswith("data:video") and ";base64," in v:
                        found.append({"kind": "b64", "value": v})
                    elif v.startswith("http") and any(
                        ext in v.lower() for ext in (".mp4", ".webm", ".mov", "video")
                    ):
                        found.append({"kind": "url", "value": v})
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, depth + 1)

    walk(payload)
    # prefer explicit b64 then url
    for kind in ("b64", "url"):
        for item in found:
            if item["kind"] == kind:
                return item
    return found[0] if found else None


def strip_data_url(s: str) -> str:
    m = re.match(r"^data:video/[^;]+;base64,(.+)$", s, re.DOTALL | re.I)
    return m.group(1) if m else s


def decode_b64(s: str) -> bytes:
    cleaned = re.sub(r"\s+", "", strip_data_url(s.strip()))
    try:
        return base64.b64decode(cleaned, validate=False)
    except Exception as e:
        raise SystemExit(f"Failed to decode base64 video: {e}") from e


def sniff_video_ext(data: bytes) -> str:
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return ".mp4"
    if data[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return ".avi"
    return ".mp4"


def download_url(url: str, api_key: str, timeout: int, retries: int = 3) -> bytes:
    requests = ensure_requests()
    header_sets = [
        {"Authorization": f"Bearer {api_key}", "Accept": "*/*"},
        {"Accept": "*/*"},  # signed CDN URLs often need no auth
    ]
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        for headers in header_sets:
            try:
                # Fail fast on blocked CDN; long only for read once connected
                connect_t = 20
                read_t = max(timeout, 180)
                resp = requests.get(
                    url,
                    headers=headers,
                    timeout=(connect_t, read_t),
                    stream=True,
                )
                if resp.status_code >= 400:
                    last_err = SystemExit(
                        f"HTTP {resp.status_code} downloading video\n{resp.text[:500]}"
                    )
                    continue
                chunks: list[bytes] = []
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        chunks.append(chunk)
                data = b"".join(chunks)
                if data:
                    return data
                last_err = SystemExit("Downloaded video is empty")
            except requests.exceptions.RequestException as e:
                last_err = e
        if attempt < retries:
            time.sleep(min(5, attempt * 2))
    raise SystemExit(f"Failed to download video after {retries} tries: {last_err}")


def resolve_out_path(out: str | None, data: bytes) -> Path:
    ext = sniff_video_ext(data)
    if out:
        p = Path(out)
        if not p.suffix:
            p = Path(str(p) + ext)
        return p.resolve()
    return Path.cwd().resolve() / f"grok-imagine-video{ext}"


def status_url(cfg: dict[str, Any], request_id: str) -> str:
    template = cfg["video_status_path"]
    if "{request_id}" in template:
        path = template.replace("{request_id}", request_id)
    else:
        path = _norm_path(template.rstrip("/") + "/" + request_id)
    if not path.startswith("/"):
        path = "/" + path
    return cfg["base_url"] + path


def generate_video(
    prompt: str,
    *,
    out: str | None,
    duration: int | None,
    aspect_ratio: str | None,
    resolution: str | None,
    model: str | None,
    config_path: Path | None,
    poll_interval: float | None,
    max_wait: int | None,
) -> Path:
    cfg = load_config(config_path)
    body: dict[str, Any] = {
        "model": model or cfg["video_model"],
        "prompt": prompt,
        "duration": int(duration if duration is not None else cfg["video_default_duration"]),
        "aspect_ratio": aspect_ratio or cfg["video_default_aspect_ratio"],
        "resolution": resolution or cfg["video_default_resolution"],
    }
    submit_url = cfg["base_url"] + cfg["video_generations_path"]
    print(f"Submitting video job: model={body['model']} duration={body['duration']}s", file=sys.stderr)
    submit = post_json(submit_url, cfg["api_key"], body, cfg["timeout_sec"])

    # rare sync response with video immediately
    ref = extract_video_ref(submit)
    request_id = extract_request_id(submit)
    if ref and not request_id:
        return save_video_ref(ref, out, cfg, request_id=None)

    if not request_id:
        # still try treat submit as final
        if ref:
            return save_video_ref(ref, out, cfg, request_id=None)
        raise SystemExit(
            "No request_id in video submit response:\n"
            + json.dumps(submit, ensure_ascii=False)[:1500]
        )

    print(f"request_id={request_id}", file=sys.stderr)
    interval = float(poll_interval if poll_interval is not None else cfg["video_poll_interval_sec"])
    wait_limit = int(max_wait if max_wait is not None else cfg["video_timeout_sec"])
    deadline = time.time() + wait_limit
    poll_url = status_url(cfg, request_id)
    last_status = ""
    last_payload: Any = None

    while time.time() < deadline:
        payload = get_json(poll_url, cfg["api_key"], cfg["timeout_sec"])
        last_payload = payload
        status = extract_status(payload)
        if status and status != last_status:
            print(f"status={status}", file=sys.stderr)
            last_status = status
        if is_failure(status):
            err = dig(payload, "error") or dig(payload, "message") or payload
            raise SystemExit(f"Video job failed (status={status}): {err}")
        if is_success(status, payload):
            ref = extract_video_ref(payload)
            if not ref:
                raise SystemExit(
                    "Job completed but no video url/b64 found:\n"
                    + json.dumps(payload, ensure_ascii=False)[:1500]
                )
            return save_video_ref(ref, out, cfg, request_id=request_id)
        # also accept intermediate payload that already has video
        ref = extract_video_ref(payload)
        if ref and status in ("", "processing", "running", "pending", "queued", "in_progress"):
            # only accept if status is empty or success-like already handled
            if status in ("",) or is_success(status, payload):
                return save_video_ref(ref, out, cfg, request_id=request_id)
        time.sleep(max(0.5, interval))

    raise SystemExit(
        f"Timed out after {wait_limit}s waiting for request_id={request_id}.\n"
        f"Last status={last_status or 'unknown'}\n"
        + (json.dumps(last_payload, ensure_ascii=False)[:1000] if last_payload else "")
    )


def save_video_ref(
    ref: dict[str, str],
    out: str | None,
    cfg: dict[str, Any],
    request_id: str | None = None,
) -> Path:
    if ref["kind"] == "b64":
        data = decode_b64(ref["value"])
        path = resolve_out_path(out, data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    if ref["kind"] != "url":
        raise SystemExit(f"Unknown video ref kind: {ref}")

    url = ref["value"]
    if url.startswith("/"):
        parsed = urlparse(cfg["base_url"])
        url = f"{parsed.scheme}://{parsed.netloc}{url}"

    # Prefer .mp4 path for naming even if download fails
    preferred = Path(out).resolve() if out else (Path.cwd().resolve() / "grok-imagine-video.mp4")
    if not preferred.suffix:
        preferred = preferred.with_suffix(".mp4")
    preferred.parent.mkdir(parents=True, exist_ok=True)

    try:
        data = download_url(url, cfg["api_key"], max(cfg["timeout_sec"], 300))
    except SystemExit as e:
        # CDN may be blocked; write sidecar with URL so user can fetch elsewhere
        meta = {
            "request_id": request_id,
            "video_url": url,
            "error": str(e),
            "hint": "Video job succeeded but direct CDN download failed. Open video_url in browser or download on a network that can reach the CDN.",
        }
        side = preferred.with_suffix(preferred.suffix + ".url.json")
        side.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        # also write a Windows .url internet shortcut
        shortcut = preferred.with_suffix(preferred.suffix + ".url")
        shortcut.write_text(
            "[InternetShortcut]\nURL=" + url + "\n",
            encoding="utf-8",
        )
        raise SystemExit(
            f"{e}\n"
            f"Saved download links:\n  {side}\n  {shortcut}\n"
            f"video_url={url}"
        ) from e

    if not data:
        raise SystemExit("Downloaded/decoded video is empty")
    # keep preferred name if it has a video suffix; else sniff
    if preferred.suffix.lower() in {".mp4", ".webm", ".mov", ".avi"}:
        path = preferred
    else:
        path = resolve_out_path(str(preferred), data)
    path.write_bytes(data)
    return path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate video with grok-imagine-video (submit + poll)."
    )
    p.add_argument("--prompt", "-p", required=True, help="Text prompt")
    p.add_argument("--out", "-o", help="Output path (default: ./grok-imagine-video.mp4)")
    p.add_argument("--duration", "-d", type=int, help="Duration seconds (default from config)")
    p.add_argument("--aspect-ratio", "-a", help='e.g. "16:9"')
    p.add_argument("--resolution", "-r", help='e.g. "720p"')
    p.add_argument("--model", "-m", help="Override video model")
    p.add_argument("--config", "-c", help="Path to config.json")
    p.add_argument("--poll-interval", type=float, help="Seconds between status polls")
    p.add_argument("--max-wait", type=int, help="Max seconds to wait for completion")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    path = generate_video(
        args.prompt,
        out=args.out,
        duration=args.duration,
        aspect_ratio=args.aspect_ratio,
        resolution=args.resolution,
        model=args.model,
        config_path=config_path,
        poll_interval=args.poll_interval,
        max_wait=args.max_wait,
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
