# Grok Imagine API Reference

Base URL and key live in skill-local `config.json`.

## Auth

```
Authorization: Bearer <api_key>
Content-Type: application/json
```

## Text-to-image

Model: `grok-imagine-image` (`config.model`)

`POST {base_url}{generations_path}`

Default path: `/images/generations`

```json
{
  "model": "grok-imagine-image",
  "prompt": "an orange cat sitting on a windowsill",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

Response (expected):

```json
{
  "data": [
    {
      "b64_json": "<base64-encoded-image-bytes>"
    }
  ]
}
```

## Image edit

Model: `grok-imagine-edit` (`config.edit_model`)

`POST {base_url}{edits_path}` (preferred) or fallback `POST {base_url}{generations_path}` with `image` field.

```json
{
  "model": "grok-imagine-edit",
  "prompt": "turn the cat into a puppy, keep composition and lighting",
  "image": "<base64-encoded-source-image>",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

Script fallbacks: edits JSON → edits multipart → generations + image (edit/gen model).

## Text-to-video

Model: `grok-imagine-video` (`config.video_model`)

### Submit

`POST {base_url}{video_generations_path}`

Default path: `/videos/generations`

```json
{
  "model": "grok-imagine-video",
  "prompt": "镜头缓慢穿过雨夜中的未来上海",
  "duration": 6,
  "aspect_ratio": "16:9",
  "resolution": "720p"
}
```

Submit response should include a request id, e.g.:

```json
{
  "request_id": "vid_xxx"
}
```

Also accepted keys: `id`, `task_id`, `job_id`, nested under `data` / `task`.

### Poll

`GET {base_url}/videos/{request_id}`

Config template: `video_status_path` default `/videos/{request_id}`

Poll until status is completed/success, then extract video from:

- `url` / `video_url` / `download_url` (download with Bearer auth)
- `b64_json` / `video_b64` / data URL `data:video/...;base64,...`

Typical statuses:

| Status | Action |
| --- | --- |
| `queued` / `pending` / `processing` / `running` | keep polling |
| `succeeded` / `completed` / `ready` | save video |
| `failed` / `error` / `cancelled` | abort |

## Config fields

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `base_url` | yes | — | e.g. `https://host/v1` |
| `api_key` | yes | — | Never commit |
| `model` | no | `grok-imagine-image` | Image generate |
| `edit_model` | no | `grok-imagine-edit` | Image edit |
| `video_model` | no | `grok-imagine-video` | Video generate |
| `default_size` | no | `1024x1024` | Image size |
| `timeout_sec` | no | `120` | Per HTTP request |
| `generations_path` | no | `/images/generations` | |
| `edits_path` | no | `/images/edits` | |
| `video_generations_path` | no | `/videos/generations` | |
| `video_status_path` | no | `/videos/{request_id}` | Must include `{request_id}` or path prefix |
| `video_default_duration` | no | `6` | seconds |
| `video_default_aspect_ratio` | no | `16:9` | |
| `video_default_resolution` | no | `720p` | |
| `video_poll_interval_sec` | no | `3` | |
| `video_timeout_sec` | no | `600` | total wait |

## Errors

| Symptom | Likely cause |
| --- | --- |
| config missing | Copy `config.example.json` → `config.json` |
| 401 | Bad api_key |
| 404 | Wrong path |
| no request_id | Unexpected submit payload shape |
| poll timeout | Raise `video_timeout_sec` or check job status in dashboard |
| completed but no video | Response missing url/b64 fields |
