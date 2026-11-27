# Code Signing Policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

## Scope

This policy applies to all officially published Windows installers and executable artifacts of **AutoClip Desktop** released through the [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip) GitHub repository.

## Team Roles

| Role | Members |
| --- | --- |
| **Committers** | `@zhouxiaoka` (Project Maintainer) |
| **Reviewers** | `@zhouxiaoka` (Project Maintainer) |
| **Approvers** | `@zhouxiaoka` (Project Maintainer) |

All release artifacts are built reproducibly on GitHub Actions ([`.github/workflows/desktop-build.yml`](.github/workflows/desktop-build.yml)) from annotated release tags in `zhouxiaoka/autoclip` and verified with `build-provenance.json` SHA-256 hashes before release approval.

## Privacy Policy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

Specifically:
- Video cutting, reframing, caption burning, and rendering run locally on the user's machine; source videos are never uploaded to any AutoClip server.
- Model API keys are stored locally and sent only to the model provider endpoint explicitly configured by the user.
- Optional anonymous crash reporting and usage analytics are clearly documented in [Privacy Policy](docs/PRIVACY.en.md) and can be disabled at any time in **Settings**.

## Verification & Support

For SHA-256 verification steps and unsigned-build guidance on other platforms, see [CODE_SIGNING.md](CODE_SIGNING.md). Security and signing inquiries can be directed to [GitHub Issues](https://github.com/zhouxiaoka/autoclip/issues) or `christine_zhouye@163.com`.
