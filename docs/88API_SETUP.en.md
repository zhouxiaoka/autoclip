# Use 88API with AutoClip

[简体中文](88API_SETUP.md) · [Back to README](../README-EN.md)

88API Token Platform sponsors AutoClip and provides OpenAI-compatible APIs for analysis, cover images and transcription.

## Register and create an API key

Register through the [AutoClip referral link](https://88api.ai/sign-up?aff=2PIc), then create an API key in the console. New users can receive trial credit; the amount, eligibility and terms are set by the platform. Live support is available on the platform. The referral link includes commission that supports project maintenance.

## Configure AutoClip

### New versions: select 88API directly

1. Open **Settings → AI Models → AI service** and select **88API** in the recommended group. You can also configure it during first-run setup.
2. Enter your 88API key. The preset base URL is `https://88api.ai/v1`.
3. Wait for your account's model list and choose an analysis model. For visual analysis, select a multimodal model that accepts images.
4. Test the connection and save. Verify the result with a short video before larger jobs.

No default text model or account allowlist is assumed. Use exact model IDs available to your account. Image and audio previews shown without a key are reference catalogs, not proof of account access.

- **Covers** can reuse the AI service key with supported OpenAI Images models such as account-listed `gpt-image-1` or `dall-e-3`. Other image models depend on their actual API and returned capability metadata.
- **Transcription** supports account-listed `whisper-1` through the OpenAI audio API with timestamps.
- The platform also offers video generation and TTS; these are not corresponding AutoClip features.

### Older versions: use the OpenAI-compatible provider

If 88API is not listed, select the custom OpenAI-compatible provider:

| Setting | Value |
| --- | --- |
| Provider | Custom OpenAI-compatible API |
| Base URL | `https://88api.ai/v1` |
| API key | The API key created in the 88API console |
| Model | An exact account model ID supporting Chat Completions |

Include `/v1` only once and do not append `/chat/completions`. Select the model, test the connection and save.

## CLI / MCP

```bash
export API88_API_KEY="your API key"
autoclip run video.mp4 --provider api88 --model "exact account model ID"
```

`API_API88_API_KEY` and `--api-key` are also supported. Use `provider="api88"` with MCP.

## Troubleshooting and references

- 401: Check the key, token status, balance and surrounding whitespace.
- 404: Check the base URL and exact model ID, and ensure the model supports the requested API.
- Empty or failed model list: Check account permissions, refresh or enter the exact ID shown in the console.
- A connection test does not validate every API. Verify actual analysis, cover generation or transcription separately.

[Official setup](https://88api.ai/zh/docs/apps/) · [Image API](https://88api.ai/zh/docs/api/image/openai-image/) · [Audio API and timestamps](https://88api.ai/zh/docs/api/audio/openai-audio/)

Required content is sent to the selected service and billed to your platform account. Keep API keys out of screenshots and public reports.

[Back to README](../README-EN.md)
