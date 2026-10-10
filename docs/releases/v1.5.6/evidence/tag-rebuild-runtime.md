# v1.5.6 tag rebuild: runtime/package identity

- Tag v1.5.6 -> 80bf1d6c41b97b45aa965d670f6f955299d5899c (same commit as internal acceptance run 37964412362, internal Desktop Build 37937536440).
- Tag Desktop Build 37964501522: push event on v1.5.6, conclusion success, updated_at 2026-10-09T17:41:00Z; all required jobs incl. build-macos-arm64, build-windows-x64, smoke-windows-x64 (CI clean-VM install/upgrade/runtime smoke on the tag package), real-transcription x3 passed.
- Package hashes differ from the internal build because the tag build re-packages (timestamps/signatures); source is identical (empty diff).

| asset | internal build 37937536440 | tag build 37964501522 |
|---|---|---|
| AutoClip Desktop_1.5.6_aarch64.dmg | 3af84c6240592f8feecd4d36a6c3b88720a6eb55766c699b967aa08ab2653533 | a39b0c1c9c5ccb521b842aabeb713a5df7b425263edcbd20beb96df975f0f317 |
| AutoClip Desktop_1.5.6_x64-setup.exe | aa03dd906296bb964ce7d4adc0bec6504de938f92d592a1ba6b9ca5a41467143 | 6dab9b99114ea0205d506739a974fe999a4cddef0e6e549f6810159a43e836a5 |
| AutoClip Desktop_1.5.6_x64-setup.exe.sig | 1a36c938289d144e7ac4a8423be74e4715128fa30a887f34deb62a344f8b6c7e | 424d88ad7c871ba2606d33f9b640621fbd8fd97bd62cf82563ac40062c631f14 |
| AutoClip.Desktop_1.5.6_aarch64.app.tar.gz | e3c1fe0c29d42b2f52678df7bfdad1cbc6c09a6131b20d5b133bb2e66bfd5604 | 40e1927b619d0f5f8885635668119f3ac49b2dfe921f8fe58c58e602e2efece7 |
| AutoClip.Desktop_1.5.6_aarch64.app.tar.gz.sig | f3570906f7ac6a9a71d72f237bf48a5843e7431d642819705e69f9f9a5199da2 | e82323d187a4f3698e2b344fdaefde9089624f994c9c5b64e2b1015c938dbadb |
| autoclip-1.5.6-cli-mcp.zip | (not in internal build) | 5a4e2911b6505be331c773ce088cff31584a667ee877cc535c930f028c8828a8 |
| autoclip-1.5.6-py3-none-any.whl | (not in internal build) | 12d42b2daf424a6417c94b89fb30ab8ae5103e0860ac6794369b64e6bb416a38 |
| latest.json | (not in internal build) | f3454d26f2554131b8eb10e4da70c9d988e9b19ac2e3ee9e132af23c1e27a6fc |
| python-release-sha256.txt | (not in internal build) | fb367ff944bdcb9180f69c61400ba3995e6d901ae76793196ca2c909a286bc1c |

Limitation: no manual Mac/Windows matrix run was executed on the tag-build binaries themselves; matrix rows are inherited from the internal package under impact-inheritance/v1 (zero source diff). The tag CI smoke-windows-x64 job is the only execution on the tag package.
