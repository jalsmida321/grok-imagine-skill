---
name: grok-imagine-image
description: Generate images with grok-imagine-image, edit images with grok-imagine-edit, and generate videos with grok-imagine-video via a user-configured API. Images use base64 (b64_json); videos use async submit+poll. Use when the user asks to draw, edit images, generate video, text-to-video, 生视频, or mentions grok-imagine-image / grok-imagine-edit / grok-imagine-video.
---

# Grok Imagine (Image + Video)

User-configured API for Grok Imagine media:

| Mode | Model | Script |
| --- | --- | --- |
| Text-to-image | `grok-imagine-image` | `scripts/generate_image.py` |
| Image edit / 图生图 | `grok-imagine-edit` | `scripts/generate_image.py --image ...` |
| Text-to-video / 生视频 | `grok-imagine-video` | `scripts/generate_video.py` |

Images: `response_format: b64_json`. Videos: `POST /videos/generations` then poll `GET /videos/{request_id}`.

## Setup (once)

1. Copy `config.example.json` to `config.json` in this skill directory.
2. Fill `base_url` and `api_key` (user-provided; never invent or commit secrets).
3. Models:
   - `model`: `grok-imagine-image`
   - `edit_model`: `grok-imagine-edit`
   - `video_model`: `grok-imagine-video`
4. Optional video defaults: `video_default_duration`, `video_default_aspect_ratio`, `video_default_resolution`, `video_timeout_sec`, `video_poll_interval_sec`.
5. Install dependency: `pip install -r requirements.txt`

Do not print the full `api_key` in chat. Do not commit `config.json`.

## When to use

- Draw / generate / 画图 → image generate
- Edit / 图生图 / “把 X 变成 Y” with source image → image edit
- 生视频 / generate video / text-to-video / `grok-imagine-video` → video generate

## Workflow

1. Confirm skill config exists.
2. Build a clear prompt from user intent.
3. Pick script by modality (image vs video).
4. Prefer absolute paths for `--image` / `--out`.
5. Return saved file path(s). On failure, show script error and check `references/api.md`.

## Commands

Replace `<SKILL_DIR>` with this skill directory path.

### Text-to-image

```bash
python "<SKILL_DIR>/scripts/generate_image.py" --prompt "一只橘猫坐在窗台上" --out "orange-cat.png"
```

### Image edit

```bash
python "<SKILL_DIR>/scripts/generate_image.py" --prompt "把猫变成小狗，其余保持不变" --image "/path/to/orange-cat.png" --out "dog.png"
```

### Text-to-video

```bash
python "<SKILL_DIR>/scripts/generate_video.py" --prompt "镜头缓慢穿过雨夜中的未来上海" --duration 6 --aspect-ratio "16:9" --resolution "720p" --out "shanghai-rain.mp4"
```

### Video options

| Flag | Meaning |
| --- | --- |
| `--prompt` / `-p` | Required text prompt |
| `--out` / `-o` | Output path (default `./grok-imagine-video.mp4`) |
| `--duration` / `-d` | Seconds (default 6) |
| `--aspect-ratio` / `-a` | e.g. `16:9` |
| `--resolution` / `-r` | e.g. `720p` |
| `--model` / `-m` | Override `video_model` |
| `--poll-interval` | Seconds between polls |
| `--max-wait` | Max wait seconds (default 600) |
| `--config` / `-c` | Alternate config.json |

Stdout: final media path. Video progress (`request_id`, `status`) goes to stderr.

## Rules

- Image generate → `grok-imagine-image`; image edit → `grok-imagine-edit`; video → `grok-imagine-video`.
- Video flow: submit → poll until completed → download/decode → save file.
- Never hardcode base_url or api_key.
- Prefer bundled scripts over ad-hoc curl.
- Path overrides only via `config.json`.

## Resources

- `scripts/generate_image.py` — image generate + edit
- `scripts/generate_video.py` — video submit + poll + save
- `config.example.json` — credential/template defaults
- `references/api.md` — API shapes and troubleshooting
