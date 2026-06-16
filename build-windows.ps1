param(
    [string]$Version = $env:GITHUB_REF_NAME
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Set-Location $PSScriptRoot

$IsRunningOnWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows
)

if (-not $IsRunningOnWindows) {
    throw "This build script must be run on Windows."
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "dev"
}

$CacheDir = Join-Path $PSScriptRoot ".build-cache"
$FfmpegZip = Join-Path $CacheDir "ffmpeg-release-essentials.zip"
$FfmpegDir = Join-Path $CacheDir "ffmpeg"
$BunVersion = "1.3.14"
$BgutilRef = "1.3.1"
$BunDir = Join-Path $CacheDir "bun-v$BunVersion"
$BunExe = Join-Path $BunDir "bun.exe"
$BgutilSrc = Join-Path $CacheDir "bgutil-ytdlp-pot-provider"
$BgutilBundle = Join-Path $BgutilSrc "server\build-bundled\generate_once.js"

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git was not found."
}

$FfmpegExe = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
$FfprobeExe = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source

if (-not $FfmpegExe -or -not $FfprobeExe) {
    if (-not (Test-Path $FfmpegZip)) {
        Invoke-WebRequest `
            -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" `
            -OutFile $FfmpegZip
    }

    Remove-Item -Recurse -Force $FfmpegDir -ErrorAction SilentlyContinue
    Expand-Archive -Force $FfmpegZip $FfmpegDir

    $FfmpegExe = (Get-ChildItem $FfmpegDir -Recurse -Filter ffmpeg.exe | Select-Object -First 1).FullName
    $FfprobeExe = (Get-ChildItem $FfmpegDir -Recurse -Filter ffprobe.exe | Select-Object -First 1).FullName
}

if (-not $FfmpegExe -or -not $FfprobeExe) {
    throw "ffmpeg.exe and ffprobe.exe are required."
}

if (-not (Test-Path $BunExe)) {
    $BunZip = Join-Path $CacheDir "bun.zip"
    Invoke-WebRequest `
        -Uri "https://github.com/oven-sh/bun/releases/download/bun-v$BunVersion/bun-windows-x64.zip" `
        -OutFile $BunZip
    Remove-Item -Recurse -Force $BunDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $BunDir | Out-Null
    Expand-Archive -Force $BunZip $BunDir
    Move-Item (Join-Path $BunDir "bun-windows-x64\bun.exe") $BunExe
    Remove-Item $BunZip
}

if (-not (Test-Path $BgutilSrc)) {
    git clone --depth 1 --branch $BgutilRef `
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git $BgutilSrc
}

if (-not (Test-Path $BgutilBundle)) {
    Push-Location (Join-Path $BgutilSrc "server")
    & $BunExe install --silent
    & $BunExe remove canvas --silent
    Remove-Item -Recurse -Force "node_modules\canvas" -ErrorAction SilentlyContinue
    Remove-Item -Force "types\commander.d.ts" -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path "build-bundled" | Out-Null
    & $BunExe build "src\generate_once.ts" --target=bun --minify --outdir=build-bundled
    Pop-Location
}

if (-not (Test-Path "venv")) {
    python -m venv venv
}

& ".\venv\Scripts\python.exe" -m pip install -q --upgrade pip
& ".\venv\Scripts\python.exe" -m pip install -q -r requirements.txt -r requirements-build.txt

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Remove-Item -Force ReClip.spec -ErrorAction SilentlyContinue

$PyinstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "ReClip",
    "--add-data", "templates;templates",
    "--add-data", "static;static",
    "--add-binary", "$FfmpegExe;bin",
    "--add-binary", "$FfprobeExe;bin",
    "--collect-all", "yt_dlp",
    "--collect-all", "yt_dlp_plugins",
    "--collect-all", "yt_dlp_ejs",
    "--collect-all", "bgutil_ytdlp_pot_provider",
    "--collect-all", "webview",
    "--collect-data", "certifi",
    "--hidden-import", "webview",
    "--exclude-module", "tkinter",
    "--exclude-module", "_tkinter",
    "--exclude-module", "turtle",
    "--exclude-module", "turtledemo",
    "--exclude-module", "test",
    "--exclude-module", "unittest",
    "--exclude-module", "pydoc_data",
    "--exclude-module", "lib2to3",
    "--exclude-module", "xmlrpc",
    "native.py"
)

& ".\venv\Scripts\python.exe" -m PyInstaller @PyinstallerArgs

$InternalDir = Join-Path $PSScriptRoot "dist\ReClip\_internal"
$BgutilDest = Join-Path $InternalDir "bgutil-server"
Remove-Item -Recurse -Force $BgutilDest -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path (Join-Path $BgutilDest "build") | Out-Null
Copy-Item $BunExe (Join-Path $BgutilDest "bun.exe")
Copy-Item $BgutilBundle (Join-Path $BgutilDest "build\generate_once.js")

@'
@echo off
if "%1"=="--version" (
  echo v22.0.0
  exit /b 0
)
"%~dp0bun.exe" %*
'@ | Set-Content -Encoding ASCII (Join-Path $BgutilDest "node.cmd")

New-Item -ItemType Directory -Force -Path "release" | Out-Null
$ZipPath = Join-Path $PSScriptRoot "release\ReClip-$Version-Windows.zip"
Remove-Item -Force $ZipPath, "$ZipPath.sha256" -ErrorAction SilentlyContinue
Compress-Archive -Force -Path "dist\ReClip" -DestinationPath $ZipPath

$Hash = Get-FileHash -Algorithm SHA256 $ZipPath
"$($Hash.Hash.ToLowerInvariant())  $(Split-Path -Leaf $ZipPath)" |
    Set-Content -Encoding ASCII "$ZipPath.sha256"

Write-Host ""
Write-Host "Windows release assets:"
Write-Host "  $ZipPath"
Write-Host "  $ZipPath.sha256"
