# Grok Imagine Skill

[English](#english) | [中文](#中文)

OpenCode / Claude Code skill for **Grok Imagine** media generation (image, image edit, video).

---

<a id="english"></a>

## English

### Overview

| Capability | Model | Script |
| --- | --- | --- |
| Text → image | `grok-imagine-image` | `scripts/generate_image.py` |
| Image edit | `grok-imagine-edit` | `scripts/generate_image.py --image ...` |
| Text → video | `grok-imagine-video` | `scripts/generate_video.py` |

Works with any **OpenAI-compatible** gateway that exposes these models.  
Fill `base_url` and `api_key` in a local `config.json` (never committed).

### Features

- **Image generate**: `POST /images/generations`, `b64_json` → save file
- **Image edit**: base64 source image, multi-path fallback
- **Video generate**: async submit → poll → download/save MP4
- Portable skill layout (`SKILL.md` + scripts + references)

### Repository layout

```
grok-imagine-skill/
├── SKILL.md
├── README.md
├── LICENSE
├── requirements.txt
├── config.example.json
├── .gitignore
├── scripts/
│   ├── generate_image.py
│   └── generate_video.py
└── references/
    └── api.md
```

### Requirements

- Python 3.10+
- `requests`

```bash
pip install -r requirements.txt
```

### Quick start

```bash
cp config.example.json config.json
# edit base_url + api_key

python scripts/generate_image.py --prompt "an orange cat on a windowsill" --out orange-cat.png

python scripts/generate_image.py \
  --prompt "turn the cat into a puppy, keep everything else" \
  --image orange-cat.png \
  --out orange-dog.png

python scripts/generate_video.py \
  --prompt "camera slowly moves through rainy futuristic Shanghai" \
  --duration 6 --aspect-ratio "16:9" --resolution "720p" \
  --out shanghai-rain.mp4
```

> **Security:** `config.json` is gitignored. Do not commit API keys.

### CLI

**`generate_image.py`**: `--prompt`, `--image`, `--out`, `--size`, `--n`, `--config`  
**`generate_video.py`**: `--prompt`, `--out`, `--duration`, `--aspect-ratio`, `--resolution`, `--model`, `--poll-interval`, `--max-wait`, `--config`

Stdout prints the saved path. Video progress goes to stderr.

### Install as a skill

**OpenCode**

```bash
# Windows PowerShell
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.config\opencode\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.config/opencode/skills/grok-imagine-image
```

**Claude Code**

```bash
# Windows
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.claude\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.claude/skills/grok-imagine-image
```

Then create `config.json` from `config.example.json` inside the installed directory.

### API overview

Details: [`references/api.md`](references/api.md)

- Image: `POST {base_url}/images/generations` · model `grok-imagine-image` · `response_format: b64_json`
- Edit: `POST {base_url}/images/edits` · model `grok-imagine-edit` · `image` as base64
- Video: `POST {base_url}/videos/generations` → poll `GET {base_url}/videos/{request_id}` · model `grok-imagine-video`

### Config fields

| Field | Default | Notes |
| --- | --- | --- |
| `base_url` | — | e.g. `https://host/v1` |
| `api_key` | — | Bearer token |
| `model` | `grok-imagine-image` | Image generate |
| `edit_model` | `grok-imagine-edit` | Image edit |
| `video_model` | `grok-imagine-video` | Video generate |
| `video_default_duration` | `6` | seconds |
| `video_default_aspect_ratio` | `16:9` | |
| `video_default_resolution` | `720p` | |
| `video_poll_interval_sec` | `3` | |
| `video_timeout_sec` | `600` | total poll wait |

### Troubleshooting

| Symptom | What to try |
| --- | --- |
| Missing config | Copy `config.example.json` → `config.json` |
| 401 | Check `api_key` |
| 404 | Check `base_url` / paths |
| Video `done` but download fails | CDN may be blocked; open `video.url` in browser or use a proxy; script may write `*.mp4.url.json` sidecars |

### License

MIT — see [LICENSE](LICENSE).

### Disclaimer

Integration skill for third-party Grok Imagine–compatible APIs. You are responsible for keys, quotas, content policy, and gateway ToS.

---

<a id="中文"></a>

## 中文

### 简介

面向 **OpenCode / Claude Code** 的 Grok Imagine 媒体生成 Skill，支持：

| 能力 | 模型 | 脚本 |
| --- | --- | --- |
| 文生图 | `grok-imagine-image` | `scripts/generate_image.py` |
| 图编辑 / 图生图 | `grok-imagine-edit` | `scripts/generate_image.py --image ...` |
| 文生视频 | `grok-imagine-video` | `scripts/generate_video.py` |

兼容任意提供上述模型的 **OpenAI 风格网关**。  
在本地 `config.json` 中填写 `base_url` 与 `api_key`（**切勿提交到仓库**）。

### 功能特性

- **文生图**：`POST /images/generations`，`b64_json` 解码落盘
- **图编辑**：源图 base64 上传，多路径回退（edits JSON → multipart → generations+image）
- **文生视频**：异步提交 → 轮询状态 → 下载/保存 MP4
- 标准 Skill 结构：`SKILL.md` + scripts + references

### 目录结构

```
grok-imagine-skill/
├── SKILL.md                 # Agent 技能说明
├── README.md
├── LICENSE
├── requirements.txt
├── config.example.json      # 复制为 config.json
├── .gitignore               # 忽略密钥与生成媒体
├── scripts/
│   ├── generate_image.py    # 生图 / 改图
│   └── generate_video.py    # 生视频
└── references/
    └── api.md               # 接口说明
```

### 环境要求

- Python 3.10+
- `requests`

```bash
pip install -r requirements.txt
```

### 快速开始

#### 1. 配置

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "base_url": "https://your-gateway.example/v1",
  "api_key": "sk-...",
  "model": "grok-imagine-image",
  "edit_model": "grok-imagine-edit",
  "video_model": "grok-imagine-video"
}
```

> **安全提示：** `config.json` 已被 `.gitignore` 忽略，请勿提交 API Key。

#### 2. 文生图

```bash
python scripts/generate_image.py --prompt "一只橘猫坐在窗台上，温暖阳光" --out orange-cat.png
```

#### 3. 图编辑

```bash
python scripts/generate_image.py \
  --prompt "把猫变成小狗，其余保持不变" \
  --image orange-cat.png \
  --out orange-dog.png
```

#### 4. 文生视频

```bash
python scripts/generate_video.py \
  --prompt "镜头缓慢穿过雨夜中的未来上海" \
  --duration 6 \
  --aspect-ratio "16:9" \
  --resolution "720p" \
  --out shanghai-rain.mp4
```

标准输出打印保存路径；视频任务的 `request_id` / 状态打印在 stderr。

### 命令行参数

#### `generate_image.py`

| 参数 | 说明 |
| --- | --- |
| `--prompt` / `-p` | 提示词（必填） |
| `--image` / `-i` | 源图路径（传入则进入编辑模式） |
| `--out` / `-o` | 输出路径 |
| `--size` / `-s` | 尺寸，如 `1024x1024` |
| `--n` | 生成数量 |
| `--config` / `-c` | 指定 `config.json` 路径 |

#### `generate_video.py`

| 参数 | 说明 |
| --- | --- |
| `--prompt` / `-p` | 提示词（必填） |
| `--out` / `-o` | 输出路径（默认 `./grok-imagine-video.mp4`） |
| `--duration` / `-d` | 时长（秒，默认 `6`） |
| `--aspect-ratio` / `-a` | 画幅，如 `16:9` |
| `--resolution` / `-r` | 分辨率，如 `720p` |
| `--model` / `-m` | 覆盖视频模型名 |
| `--poll-interval` | 轮询间隔（秒） |
| `--max-wait` | 最长等待（默认 `600`） |
| `--config` / `-c` | 指定 `config.json` 路径 |

### 安装为 Skill

#### OpenCode

```bash
# Windows PowerShell
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.config\opencode\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.config/opencode/skills/grok-imagine-image
```

#### Claude Code

```bash
# Windows
Copy-Item -Recurse .\grok-imagine-skill "$env:USERPROFILE\.claude\skills\grok-imagine-image"

# macOS / Linux
cp -R grok-imagine-skill ~/.claude/skills/grok-imagine-image
```

安装后在该目录复制 `config.example.json` → `config.json` 并填写密钥。  
之后在对话里说「画图 / 改图 / 生视频」等，Agent 会按 `SKILL.md` 调用本技能。

### 接口概览

完整说明见 [`references/api.md`](references/api.md)。

**文生图**

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

**图编辑**

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

**文生视频**

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

然后轮询：

```http
GET {base_url}/videos/{request_id}
```

当 `status` 为 `done` / `completed` 时，下载 `video.url`（或解码 base64）。

### 配置项

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `base_url` | — | 如 `https://host/v1` |
| `api_key` | — | Bearer Token |
| `model` | `grok-imagine-image` | 文生图模型 |
| `edit_model` | `grok-imagine-edit` | 图编辑模型 |
| `video_model` | `grok-imagine-video` | 生视频模型 |
| `generations_path` | `/images/generations` | 生图路径 |
| `edits_path` | `/images/edits` | 编辑路径 |
| `video_generations_path` | `/videos/generations` | 生视频路径 |
| `video_status_path` | `/videos/{request_id}` | 状态查询 |
| `video_default_duration` | `6` | 默认时长（秒） |
| `video_default_aspect_ratio` | `16:9` | 默认画幅 |
| `video_default_resolution` | `720p` | 默认分辨率 |
| `video_poll_interval_sec` | `3` | 轮询间隔 |
| `video_timeout_sec` | `600` | 总等待时间 |
| `timeout_sec` | `120` | 单次 HTTP 超时 |

### 常见问题

| 现象 | 处理建议 |
| --- | --- |
| 缺少 config | 复制 `config.example.json` 为 `config.json` |
| 401 | 检查 `api_key` |
| 404 | 检查 `base_url` 与路径配置 |
| 图编辑 503 | 脚本会回退到 `/images/generations` + `image` |
| 视频任务成功但下载失败 | CDN 可能被墙/不可达；浏览器打开 `video.url`，或配置代理；脚本可能写出 `*.mp4.url.json` 旁路文件 |
| 轮询超时 | 增大 `video_timeout_sec` / `--max-wait` |

### 开发检查

```bash
python -m py_compile scripts/generate_image.py scripts/generate_video.py
python scripts/generate_image.py --help
python scripts/generate_video.py --help
```

### 许可证

MIT — 见 [LICENSE](LICENSE)。

### 免责声明

本项目为第三方 Grok Imagine 兼容 API 的集成 Skill。API 密钥、用量配额、内容合规及网关服务条款由使用者自行负责。
