#!/usr/bin/env python3
"""Generate or edit images via grok-imagine-image / grok-imagine-edit (b64_json)."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any


def skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent


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
        "model": str(data.get("model") or "grok-imagine-image"),
        "edit_model": str(data.get("edit_model") or "grok-imagine-edit"),
        "default_size": str(data.get("default_size") or "1024x1024"),
        "timeout_sec": int(data.get("timeout_sec") or 120),
        "generations_path": _norm_path(data.get("generations_path") or "/images/generations"),
        "edits_path": _norm_path(data.get("edits_path") or "/images/edits"),
    }


def _norm_path(p: str) -> str:
    p = str(p).strip()
    if not p.startswith("/"):
        p = "/" + p
    return p


def ensure_requests():
    try:
        import requests  # noqa: F401
    except ImportError as e:
        raise SystemExit("Missing dependency: pip install requests") from e
    import requests

    return requests


def file_to_b64(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise SystemExit(f"Image not found: {path}")
    raw = path.read_bytes()
    if not raw:
        raise SystemExit(f"Image is empty: {path}")
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    return base64.b64encode(raw).decode("ascii"), mime


def as_data_url(b64: str, mime: str) -> str:
    return f"data:{mime};base64,{b64}"


def extract_b64_list(payload: Any) -> list[str]:
    out: list[str] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("b64_json"), str):
            out.append(payload["b64_json"])
        if isinstance(payload.get("b64"), str):
            out.append(payload["b64"])
        # OpenAI chat-style content parts
        content = payload.get("content")
        if isinstance(content, str) and "base64" in content:
            m = re.search(r"data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)", content)
            if m:
                out.append(m.group(1))
        if isinstance(content, list):
            for part in content:
                out.extend(extract_b64_list(part))
        if isinstance(payload.get("image_url"), dict):
            url = payload["image_url"].get("url")
            if isinstance(url, str) and url.startswith("data:image"):
                out.append(url)
        if isinstance(payload.get("url"), str) and payload["url"].startswith("data:image"):
            out.append(payload["url"])
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                out.extend(extract_b64_list(item))
        images = payload.get("images")
        if isinstance(images, list):
            for item in images:
                out.extend(extract_b64_list(item))
        choices = payload.get("choices")
        if isinstance(choices, list):
            for item in choices:
                out.extend(extract_b64_list(item))
        msg = payload.get("message")
        if isinstance(msg, dict):
            out.extend(extract_b64_list(msg))
    elif isinstance(payload, list):
        for item in payload:
            out.extend(extract_b64_list(item))
    elif isinstance(payload, str) and len(payload) > 64:
        out.append(payload)
    return out


def strip_data_url(b64: str) -> str:
    m = re.match(r"^data:image/[^;]+;base64,(.+)$", b64, re.DOTALL)
    return m.group(1) if m else b64


def decode_image(b64: str) -> bytes:
    cleaned = strip_data_url(b64.strip())
    cleaned = re.sub(r"\s+", "", cleaned)
    try:
        return base64.b64decode(cleaned, validate=False)
    except Exception as e:
        raise SystemExit(f"Failed to decode base64 image: {e}") from e


def sniff_ext(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return ".png"


def resolve_out_path(out: str | None, index: int, n: int, data: bytes) -> Path:
    ext = sniff_ext(data)
    if out:
        p = Path(out)
        if n > 1:
            if p.suffix:
                p = p.with_name(f"{p.stem}_{index + 1}{p.suffix}")
            else:
                p = Path(f"{p}_{index + 1}{ext}")
        elif not p.suffix:
            p = Path(str(p) + ext)
        return p.resolve()
    return Path.cwd().resolve() / f"grok-imagine-{index + 1}{ext}"


def post_json(url: str, api_key: str, body: dict[str, Any], timeout: int) -> Any:
    requests = ensure_requests()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.exceptions.Timeout as e:
        raise SystemExit(f"Request timed out after {timeout}s: {url}") from e
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Request failed: {e}") from e

    text = resp.text
    if resp.status_code >= 400:
        raise SystemExit(f"HTTP {resp.status_code} from {url}\n{text[:2000]}")

    try:
        return resp.json()
    except Exception:
        if text.strip():
            return {"b64_json": text.strip()}
        raise SystemExit(f"Non-JSON empty response from {url}")


def post_multipart(
    url: str,
    api_key: str,
    fields: dict[str, str],
    image_path: Path,
    mime: str,
    timeout: int,
) -> Any:
    requests = ensure_requests()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    files = {
        "image": (image_path.name, image_path.read_bytes(), mime),
    }
    try:
        resp = requests.post(url, headers=headers, data=fields, files=files, timeout=timeout)
    except requests.exceptions.Timeout as e:
        raise SystemExit(f"Request timed out after {timeout}s: {url}") from e
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Request failed: {e}") from e

    text = resp.text
    if resp.status_code >= 400:
        raise SystemExit(f"HTTP {resp.status_code} from {url}\n{text[:2000]}")
    try:
        return resp.json()
    except Exception:
        if text.strip():
            return {"b64_json": text.strip()}
        raise SystemExit(f"Non-JSON empty response from {url}")


def save_from_payload(payload: Any, out: str | None, n: int) -> list[Path]:
    b64_list = extract_b64_list(payload)
    if not b64_list:
        raise SystemExit(
            "No base64 image found in response. "
            "Expected data[].b64_json. Response snippet:\n"
            + json.dumps(payload, ensure_ascii=False)[:1500]
        )

    saved: list[Path] = []
    for i, b64 in enumerate(b64_list[:n]):
        raw = decode_image(b64)
        path = resolve_out_path(out, i, min(n, len(b64_list)), raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        saved.append(path)
    return saved


def generate_text(
    prompt: str,
    *,
    out: str | None,
    size: str | None,
    n: int,
    cfg: dict[str, Any],
) -> list[Path]:
    size = size or cfg["default_size"]
    n = max(1, int(n))
    body: dict[str, Any] = {
        "model": cfg["model"],
        "prompt": prompt,
        "n": n,
        "size": size,
        "response_format": "b64_json",
    }
    url = cfg["base_url"] + cfg["generations_path"]
    payload = post_json(url, cfg["api_key"], body, cfg["timeout_sec"])
    return save_from_payload(payload, out, n)


def edit_image(
    prompt: str,
    image: Path,
    *,
    out: str | None,
    size: str | None,
    n: int,
    cfg: dict[str, Any],
) -> list[Path]:
    """Edit image. Try grok-imagine-edit, then generations+image fallbacks."""
    size = size or cfg["default_size"]
    n = max(1, int(n))
    b64, mime = file_to_b64(image)
    data_url = as_data_url(b64, mime)
    edit_model = cfg["edit_model"]
    gen_model = cfg["model"]
    edits_url = cfg["base_url"] + cfg["edits_path"]
    gens_url = cfg["base_url"] + cfg["generations_path"]
    timeout = cfg["timeout_sec"]
    errors: list[str] = []

    def try_json(url: str, body: dict[str, Any], label: str) -> list[Path] | None:
        try:
            payload = post_json(url, cfg["api_key"], body, timeout)
            return save_from_payload(payload, out, n)
        except SystemExit as e:
            errors.append(f"{label}: {e}")
            return None

    # 1) dedicated edits endpoint + edit model (preferred when available)
    for image_val, label in (
        (b64, "edits+edit_model+b64"),
        (data_url, "edits+edit_model+data_url"),
    ):
        body = {
            "model": edit_model,
            "prompt": prompt,
            "image": image_val,
            "n": n,
            "size": size,
            "response_format": "b64_json",
        }
        got = try_json(edits_url, body, label)
        if got:
            return got

    # 2) multipart edits
    fields = {
        "model": edit_model,
        "prompt": prompt,
        "n": str(n),
        "size": size,
        "response_format": "b64_json",
    }
    try:
        payload = post_multipart(edits_url, cfg["api_key"], fields, image, mime, timeout)
        return save_from_payload(payload, out, n)
    except SystemExit as e:
        errors.append(f"edits+multipart: {e}")

    # 3) generations endpoint with image field (works on many OpenAI-compatible gateways)
    for model, image_val, label in (
        (edit_model, b64, "generations+edit_model+b64"),
        (edit_model, data_url, "generations+edit_model+data_url"),
        (gen_model, b64, "generations+gen_model+b64"),
        (gen_model, data_url, "generations+gen_model+data_url"),
    ):
        body = {
            "model": model,
            "prompt": prompt,
            "image": image_val,
            "n": n,
            "size": size,
            "response_format": "b64_json",
        }
        got = try_json(gens_url, body, label)
        if got:
            return got

    raise SystemExit("Image edit failed.\n" + "\n".join(errors))


def generate(
    prompt: str,
    *,
    image: Path | None,
    out: str | None,
    size: str | None,
    n: int,
    config_path: Path | None,
) -> list[Path]:
    cfg = load_config(config_path)
    if image:
        return edit_image(prompt, image, out=out, size=size, n=n, cfg=cfg)
    return generate_text(prompt, out=out, size=size, n=n, cfg=cfg)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate (grok-imagine-image) or edit (grok-imagine-edit) images, b64_json."
    )
    p.add_argument("--prompt", "-p", required=True, help="Text prompt")
    p.add_argument("--image", "-i", help="Local reference image for edit mode (grok-imagine-edit)")
    p.add_argument("--out", "-o", help="Output path (default: ./grok-imagine-1.png)")
    p.add_argument("--size", "-s", help="e.g. 1024x1024")
    p.add_argument("--n", type=int, default=1, help="Number of images (default 1)")
    p.add_argument(
        "--config",
        "-c",
        help="Path to config.json (default: skill dir config.json)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    image = Path(args.image).expanduser().resolve() if args.image else None
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    paths = generate(
        args.prompt,
        image=image,
        out=args.out,
        size=args.size,
        n=args.n,
        config_path=config_path,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
