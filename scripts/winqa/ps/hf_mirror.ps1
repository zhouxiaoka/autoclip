# Workaround switch for networks where huggingface.co is unreachable: user-level HF_ENDPOINT (+ disable the Xet
# transfer backend, whose CAS host bypasses HF_ENDPOINT and returns 401 via the mirror) for the NEXT app launch.
# The app itself has no mirror setting (finding); -Off removes both again. clean.ps1 also removes them.
param([switch]$On, [switch]$Off, [string]$Url = 'https://hf-mirror.com')
if ($On) { [Environment]::SetEnvironmentVariable('HF_ENDPOINT', $Url, 'User'); [Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET', '1', 'User') }
if ($Off) { [Environment]::SetEnvironmentVariable('HF_ENDPOINT', $null, 'User'); [Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET', $null, 'User') }
'HF_ENDPOINT(User)=' + [Environment]::GetEnvironmentVariable('HF_ENDPOINT', 'User') + ' HF_HUB_DISABLE_XET(User)=' + [Environment]::GetEnvironmentVariable('HF_HUB_DISABLE_XET', 'User')
