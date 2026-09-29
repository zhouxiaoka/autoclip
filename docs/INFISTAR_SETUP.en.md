# Use Infistar with AutoClip

[简体中文](INFISTAR_SETUP.md) · [Back to README](../README-EN.md)

Infistar sponsors AutoClip and can be configured through the existing OpenAI-compatible API option.

## Register and create an API key

Register through the [AutoClip referral link](https://www.infistar.cc/register?aff=XLK3BCM6&ref_source=link), then create an API key in the Infistar console. The partner's promotion offers $5 in trial credit; eligibility and changes to the offer are governed by its promotion page.

## Configure AutoClip

### Version 1.4.1 and later: pick Infistar directly

1. Open Settings → Model and choose **Infistar**. The base URL `https://infistar.cc/v1` is preset.
2. No account yet? Click "Sign up & claim credit" to register through the referral link, then create an API key in the console.
3. Paste the key. The model list fills in with the models available to your account; pick one.
4. Test the connection and save.

CLI / MCP: `autoclip run video.mp4 --provider infistar --api-key sk-… --model <model id>`, or set `INFISTAR_API_KEY`.

### Older versions: configure as an OpenAI-compatible API

Open Settings → Model and enter:

| Field | Value |
| --- | --- |
| Provider | OpenAI / compatible API |
| Base URL | `https://infistar.cc/v1` |
| API key | Your Infistar API key |
| Model | An exact model ID available to your account that supports Chat Completions |

Include `/v1` only once and do not append `/chat/completions`. International networks can also use `https://infistar.ai/v1`; see the [official gateway documentation](https://doc.infistar.cc/integration-guides/gateway-config).

Choose a model from the list or enter its exact ID, test the connection, and save. Do not assume the default OpenAI model is available: access depends on your Infistar account and its model catalog.

Try a short video or an existing transcript first. Check the generated highlights, titles, and timestamps before processing long videos in batches. A successful connection test verifies only the test request, not the full processing workflow.

## Troubleshooting

- **401 / authentication failure**: Check that the key is valid, belongs to Infistar, and has no extra whitespace.
- **404 / endpoint not found**: Use the `/v1` base URL above without duplicating path segments.
- **Model unavailable or endpoint unsupported**: Check the exact model ID, account permissions, and Chat Completions support. Models may support different endpoints and parameters; see the [official compatibility guide](https://infistar.cc/openai-compatible-api).

Model requests send the content needed for analysis to your selected provider, which bills usage to your account. Enter your API key only in Settings; keep it out of screenshots, public documents, and issue reports.
