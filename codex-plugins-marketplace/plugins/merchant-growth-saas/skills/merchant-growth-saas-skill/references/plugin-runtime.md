# Plugin Runtime Model

The SaaS plugin marketplace is not the Codex plugin marketplace. It is an in-product module registry that tells the operator what is available, configured, missing, and safe to run.

## Status Model

Use these fields for each module:

```json
{
  "id": "videocut-skills",
  "name": "口播剪辑 Skills",
  "role": "剪口播、生成字幕、分镜预览、时间线预览和竖屏成片导出。",
  "runtime": "local",
  "status": "needs_config",
  "configured": false,
  "actions": ["剪口播", "口播成片", "分镜审核", "导出 MP4"],
  "required_env": ["VOLCENGINE_API_KEY"],
  "next_action": "Install FFmpeg and configure VOLCENGINE_API_KEY."
}
```

Valid `runtime` values:

- `local`: installed on the same machine, usually skills/scripts/CLI.
- `server`: backend worker or rendering service.
- `external_api`: third-party API provider.
- `manual`: documented human-in-the-loop action.

Valid `status` values:

- `ready`: works in the current app without extra configuration.
- `configured`: dependency is detected and usable.
- `needs_config`: installed or planned, but missing keys, binaries, or accounts.
- `planned`: visible roadmap item, not runnable yet.

## Recommended Integrations

### AI客服成交助手

Built into the app. Should always be available. Do not hide it behind media-generation features.

### Customer Need API

Core external entry point. Any form/webhook/source should map into `/api/intake/customer-need`.

### API2D / OpenAI-Compatible Images

Required environment variables:

```text
IMAGE_API_KEY
IMAGE_BASE_URL
IMAGE_MODEL
```

Fallback behavior: return a usable prompt if image generation fails.

### HyperFrames

Use for HTML/GSAP showreels and render plans. Treat HTML preview as proof, MP4 export as the next worker step.

### Remotion

Use for server-side parameterized video rendering. Before commercial SaaS use, check license requirements.

Required environment variable:

```text
REMOTION_RENDER_URL
```

### HeyGen

Use for digital-human videos only when it improves trust. It is not required for the MVP.

Required environment variables:

```text
HEYGEN_API_KEY
HEYGEN_AVATAR_ID
```

### 口播剪辑 Skills

Installed as a Codex Skill package, not as a SaaS backend plugin.

Expected install path:

```text
~/.codex/skills/chengfeng-videocut-skills
```

Runtime requirements:

```text
ffmpeg
VOLCENGINE_API_KEY
```

The SaaS should display it as installed/needs_config/configured, but real use happens through Codex Skill execution or a future backend wrapper.

## Guardrails

- Do not auto-send messages.
- Do not auto-publish to Douyin or other platforms without final confirmation.
- Do not store real keys in repo files.
- Show missing config clearly instead of silently failing.
