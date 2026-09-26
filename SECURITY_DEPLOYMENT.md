# Authentication and usage limits

Web deployments must set `AUTOCLIP_AUTH_TOKEN` to a randomly generated secret of at least 32 characters. The browser login stores only an HttpOnly, SameSite=Strict session cookie (eight-hour lifetime). Serve web traffic through HTTPS; terminate TLS at a trusted proxy that preserves the original scheme and Host. Configure `AUTOCLIP_ALLOWED_HOSTS` as comma-separated hostnames (without ports); defaults permit localhost and loopback only. Set `AUTOCLIP_ALLOWED_ORIGINS` only when a separate trusted browser origin is required. Unconfigured authentication fails closed. `/health` is the sole public health endpoint.

Desktop launches generate a new OS-random capability, passed to the child backend and frontend through the native bridge. It is not saved in browser storage. Native media elements use path-scoped, read-only 60-second tickets; do not publish ticket URLs or log query strings. The frontend refreshes tickets while starting/seeking playback.

## Single-host shared accounting

API, scheduler and all workers MUST use the same local `AUTOCLIP_SECURITY_DIR`, outside the served data directory. Its default is `~/.autoclip-security`; Docker Compose mounts `./security-state` into API and workers. Give the application user ownership of that directory. The directory and SQLite database are restricted to owner access. Do not expose it through a web server, move/delete it to reset a limit, or use a network filesystem. Back it up with application state.

SQLite transactions serialize admission across processes on **one host**. Multi-host deployments are unsupported: `AUTOCLIP_DEPLOYMENT_HOSTS` must remain `1`; any other value denies admission. Scaling to multiple hosts requires a shared transactional accounting service before deployment. Merely pointing separate instances at separate directories does not provide a shared budget.

Defaults (server environment only):

| Variable prefix `AUTOCLIP_` | Default |
| --- | --- |
| `HTTP_PER_MINUTE` | 120 global and per operator |
| `EXPENSIVE_PER_MINUTE` | 10 mutating requests global and per operator |
| `DAILY_PAID_REQUESTS` | 100 attempts per UTC day |
| `CONCURRENT_PAID` | 2 paid calls or known pending async image jobs |
| `OUTPUT_TOKENS` | 8192 per text call |
| `DAILY_OUTPUT_TOKENS` | 819200 reserved output tokens |
| `PAID_INPUT_BYTES` | 262144 text bytes per call |
| `MEDIA_INPUT_BYTES` | 16777216 bytes per media call |
| `DAILY_INPUT_BYTES` | 16777216 aggregate submitted bytes |
| `AUDIO_SECONDS` | 600 seconds per cloud audio file |
| `OUTSTANDING_TASKS` | 20 queued/running tasks |
| `JSON_REQUEST_BYTES` / `REQUEST_BYTES` | 1 MiB JSON / 512 MiB multipart |

Reservations remain charged after failures/timeouts: the upstream service may have billed the request. The pinned DashScope native SDK can retry one connection failure, so both possible attempts are reserved in advance. OpenAI and Gemini SDK retries are disabled. Application retries reserve again. Changing model, key or client address does not reset accounting. Storage failure denies new operations.

These are operation, byte and reserved output-token limits, **not currency budgets or exact input-token accounting**. Model pricing, image dimensions and audio billing vary; provider-side account limits remain useful additional protection. Async image jobs retain a concurrency lease until the provider confirms completion or failure. Cancellation, unknown status and polling timeout retain the lease because remote work may still continue; reconcile it only after confirming the provider job ended.

Queue and outbound leases deliberately do not expire automatically: expiry during a long-running operation could exceed concurrency limits. Normal completion/failure releases them. A process crash, broker delivery uncertainty or revoked queued task may leave an orphan. Stop API/scheduler/workers and verify no upstream/local operation remains active before an administrator removes only confirmed orphan rows from `usage.sqlite3`'s `leases` table. Never delete counters to clear leases. This conservative recovery favors bounded usage over availability.

Saved API credentials are masked by the settings API. The mask preserves the existing secret on settings updates; to remove a secret submit an empty value. Saved secrets may only be reused at their configured provider endpoint. Supply a separate credential when testing a different endpoint.
