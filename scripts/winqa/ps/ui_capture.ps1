# Runs INSIDE the interactive session (via scheduled task): list visible top-level windows and take a screenshot.
param([string]$Label = 'ui')
$out = 'C:\winqa\out'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$wins = Get-Process | Where-Object { $_.MainWindowTitle } | ForEach-Object { [pscustomobject]@{ pid = $_.Id; name = $_.ProcessName; title = $_.MainWindowTitle; responding = $_.Responding } }
$shot = $null
try {
  $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
  $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Left, $b.Top, 0, 0, $bmp.Size)
  $shot = Join-Path $out "ui-$Label.png"
  $bmp.Save($shot, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
} catch { $shot = "screenshot failed: $($_.Exception.Message)" }
$obj = [pscustomobject]@{ label = $Label; captured_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz'); session = (Get-Process -Id $PID).SessionId; windows = @($wins); screenshot = $shot }
[IO.File]::WriteAllText((Join-Path $out "ui-$Label.json"), ($obj | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))
