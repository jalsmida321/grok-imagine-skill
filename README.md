# Grok Imagine Skill

OpenCode / Claude Code skill for **Grok Imagine** media generation:

| Capability | Model | Script |
| --- | --- | --- |
| Text → image | `grok-imagine-image` | `scripts/generate_image.py` |
| Image edit / 图生图 | `grok-imagine-edit` | `scripts/generate_image.py --image ...` |
| Text → video / 生视频 | `grok-imagine-video` | `scripts/generate_video.py` |

Works with any **OpenAI-compatible** gateway that exposes these models.  
`base_url` and `api_key` are filled by you in a local `config.json` (never committed).

## Features

- **Image generate**: `POST /images/generations`, response `b64_json` → save PNG/JPEG
- **Image edit**: base64 source image, multi-path fallback (edits JSON → multipart → generations+image)
- **Video generate**: async `POST /videos/generations` → poll `GET /videos/{request_id}` → download/save MP4
- Portable skill layout (`SKILL.md` + scripts + references)

## Repository layout

```
grok-imagine-skill/
├── SKILL.md                 # Agent skill instructions
├── README.md
├── LICENSE
├── requirements.txt
├── config.example.json      # Copy → config.json
├── .gitignore               # Ignores config.json + media outputs
├── scripts/
│   ├── generate_image.py
│   └── generate_video.py
└── references/
    └── api.md               # Request/response reference
```

## Requirements

- Python 3.10+
- `requests`

```bash
pip install -r requirements.txt
```

## Quick start

### 1. Configure

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "base_url": "https://your-gateway.example/v1",
  "api_key": "sk-...",
  "model": "grok-imagine-image",
  "edit_model": "grok-imagine-edit",
  "video_model": "grok-imagine-video"
}
```

> **Security:** `config.json` is gitignored. Do not commit API keys.

### 2. Generate an image

```bash
python scripts/generate_image.py --prompt "一只橘猫坐在窗台上，温暖阳光" --out orange-cat.png
```

### 3. Edit an image

```bash
python scripts/generate_image.py \
  --prompt "把猫变成小狗，其余保持不变" \
  --image orange-cat.png \
  --out orange-dog.png
```

### 4. Generate a video

```bash
python scripts/generate_video.py \
  --prompt "镜头缓慢穿过雨夜中的未来上海" \
  --duration 6 \
  --aspect-ratio "16:9" \
  --resolution "720p" \
  --out shanghai-rain.mp4
```

Stdout prints the saved file path. Video jobs log `request_id` / status on stderr.

## CLI reference

### `generate_image.py`

| Flag | Description |
| --- | --- |
| `--prompt` / `-p` | Text prompt (required) |
| `--image` / `-i` | Source image → edit mode |
| `--out` / `-o` | Output path |
| `--size` / `-s` | e.g. `1024x1024` |
| `--n` | Number of images |
| `--config` / `-c` | Path to `config.json` |

### `generate_video.py`

| Flag | Description |
| --- | --- |
| `--prompt` / `-p` | Text prompt (required) |
| `--out` / `-o` | Output path (default `./grok-imagine-video.mp4`) |
| `--duration` / `-d` | Seconds (default `6`) |
| `--aspect-ratio` / `-a` | e.g. `16:9` |
| `--resolution` / `-r` | e.g. `720p` |
| `--model` / `-m` | Override video model |
| `--poll-interval` | Poll interval seconds |
| `--max-wait` | Max wait for job (default `600`) |
| `--config` / `-c` | Path to `config.json` |

## Install as an OpenCode / Claude skill

### OpenCode

Copy (or symlink) this folder into your skills directory:

```bash
# Windows (PowerShell)
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.config\opencode\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.config/opencode/skills/grok-imagine-image
```

Then create `config.json` inside the installed skill dir (from `config.example.json`).

### Claude Code

```bash
# Windows
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.claude\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.claude/skills/grok-imagine-image
```

After install, the agent should pick up `SKILL.md` when you ask to draw / edit / generate video with Grok Imagine.

## API overview

Full details: [`references/api.md`](references/api.md)

**Image generate**

```http
POST {base_url}/images/generations
```

```json
{
  "model": "grok-imagine-image",
  "prompt": "...",
  "response_format": "b64_json"
}
```

**Image edit** (preferred)

```http
POST {base_url}/images/edits
```

```json
{
  "model": "grok-imagine-edit",
  "prompt": "...",
  "image": "<base64>",
  "response_format": "b64_json"
}
```

**Video generate**

```http
POST {base_url}/videos/generations
```

```json
{
  "model": "grok-imagine-video",
  "prompt": "...",
  "duration": 6,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

Then poll:

```http
GET {base_url}/videos/{request_id}
```

When `status` is `done` / `completed`, download `video.url` (or decode base64 if provided).

## Config fields

| Field | Default | Notes |
| --- | --- | --- |
| `base_url` | — | e.g. `https://host/v1` |
| `api_key` | — | Bearer token |
| `model` | `grok-imagine-image` | Image generate |
| `edit_model` | `grok-imagine-edit` | Image edit |
| `video_model` | `grok-imagine-video` | Video generate |
| `generations_path` | `/images/generations` | |
| `edits_path` | `/images/edits` | |
| `video_generations_path` | `/videos/generations` | |
| `video_status_path` | `/videos/{request_id}` | |
| `video_default_duration` | `6` | |
| `video_default_aspect_ratio` | `16:9` | |
| `video_default_resolution` | `720p` | |
| `video_poll_interval_sec` | `3` | |
| `video_timeout_sec` | `600` | Total poll wait |
| `timeout_sec` | `120` | Per HTTP request |

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Missing config | Copy `config.example.json` → `config.json` |
| 401 | Check `api_key` |
| 404 | Check `base_url` and path fields |
| Image edit 503 / unavailable | Script falls back to `/images/generations` + `image` |
| Video job `done` but download fails | CDN host may be blocked; open `video.url` in browser or use a proxy; script also writes `*.mp4.url.json` / `*.mp4.url` sidecars |
| Poll timeout | Increase `video_timeout_sec` / `--max-wait` |

## Development

```bash
# syntax check
python -m py_compile scripts/generate_image.py scripts/generate_video.py

# help
python scripts/generate_image.py --help
python scripts/generate_video.py --help
```

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This project is an integration skill for third-party Grok Imagine–compatible APIs. You are responsible for API keys, usage quotas, content policy compliance, and gateway terms of service.
