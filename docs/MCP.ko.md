# AutoClip MCP 및 AI 에이전트 연동 가이드

[English](MCP.en.md) · [简体中文](CLI_AND_MCP.md) · [日本語](MCP.ja.md) · **한국어** · [Español](MCP.es.md) · [Deutsch](MCP.de.md)

Claude Code, Cursor, Windsurf, OpenCode 등 MCP 호환 AI 에이전트에서 AutoClip을 바로 호출해 팟캐스트·인터뷰·방송 녹화본을 숏폼 클립으로 자동 제작할 수 있습니다. 데스크톱 앱과 동일한 로컬 파이프라인을 공유하므로 구독료·워터마크 없이 100% 로컬에서 렌더링됩니다.

---

## 한 줄 설치

### Claude Code
```bash
claude mcp add autoclip -- uvx autoclip-mcp
```

### 에이전트 스킬 추가
```bash
npx skills add zhouxiaoka/autoclip
```

### Cursor / Windsurf / 일반 MCP 클라이언트 (`mcp.json`)
```json
{
  "mcpServers": {
    "autoclip": {
      "command": "uvx",
      "args": ["autoclip-mcp"]
    }
  }
}
```

> **요구 사항:** Python 3.10+ (3.11 권장), `uv` (`uvx`), `ffmpeg`. 설치된 버전은 `autoclip --version` 또는 MCP `get_version`으로 확인하세요.

---

## 주요 MCP 도구

| 도구 | 설명 |
| :--- | :--- |
| `get_version` | 설치된 AutoClip 버전 조회 |
| `list_styles` | 사용 가능한 편집 스타일(`editorial`, `street`, `news`, `cinema`, `classic` 등) 조회 |
| `start_quick_output` | 비동기 클립 추출·자막·커버 제작 작업 시작 |
| `get_quick_output_status` | 진행률(`progress` / `stage` / `eta`) 조회 및 완성 파일 경로 반환 |
| `cancel_job` | 실행 중인 작업을 안전하게 중단 (이미 완료된 클립은 유지) |

### `start_quick_output` 요청 예시
```json
{
  "source": "/absolute/path/talk.mp4",
  "platforms": ["youtube_shorts", "tiktok"],
  "portrait_style": "podcast",
  "template": "editorial"
}
```

- **보안:** API 키는 MCP 도구 인자로 전달하지 않으며, 데스크톱 저장 설정이나 `AUTOCLIP_API_KEY` 환경 변수를 사용합니다. Ollama / LM Studio + 로컬 Whisper로 완전 오프라인 실행도 가능합니다.
- 전체 가이드는 [English Guide](MCP.en.md) 또는 [CLI & MCP 문서 (ZH)](CLI_AND_MCP.md)를 참고하세요.
