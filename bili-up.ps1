# 批量下载 B 站 UP 主全部视频（基于 yt-dlp + 本机已装的 Python/ffmpeg）
#
# 用法：
#   .\tools\bili-up.ps1 -Up "https://space.bilibili.com/546195/video" -Out "D:\Bilibili\老番茄"
#   .\tools\bili-up.ps1 -Up 546195 -Out "D:\Bilibili\老番茄" -Limit 20
#   .\tools\bili-up.ps1 -Up 546195 -Out "D:\Bilibili\老番茄" -ListOnly   # 只列清单不下载
#
# 特性：断点续传（--download-archive 记录已下）、跳过已下载、按发布日期命名、并发温和。

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Up,
    [string]$Out = "D:\Bilibili",
    [int]$Limit = 0,            # 0 = 全部；>0 只下最新 N 个
    [int]$Start = 0,            # 从第几个开始（1 起）
    [string]$Quality = "bv*[height<=1080]+ba/b",
    [switch]$ListOnly,
    [switch]$AudioOnly,
    [int]$Sleep = 2             # 每个视频之间的间隔秒数（防风控）
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pyDir = Join-Path $root "tools\py"
$cookies = Join-Path $root "tools\cookies\omni-bili.txt"
if (-not (Test-Path $cookies)) { $cookies = Join-Path $root "tools\cookies\bili-login.txt" }
$ffmpeg = (Get-ChildItem (Join-Path $pyDir "imageio_ffmpeg\binaries\ffmpeg-win-x86_64*.exe") | Select-Object -First 1).FullName

if (-not (Test-Path $cookies)) { throw "缺少登录 cookie：$cookies（先运行 python tools\bili_login.py 扫码）" }

# 接受 mid 或完整空间链接
if ($Up -match '^\d+$') { $spaceUrl = "https://space.bilibili.com/$Up/video" }
elseif ($Up -match 'space\.bilibili\.com/(\d+)') { $spaceUrl = "https://space.bilibili.com/$($Matches[1])/video" }
else { throw "无法识别的 UP 主：$Up（给 mid 或空间链接）" }

$env:PYTHONPATH = $pyDir
$env:PYTHONIOENCODING = "utf-8"
$env:TMP = Join-Path $root "tools\tmp"
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP, $Out | Out-Null

$archive = Join-Path $Out ".downloaded.txt"
$args = @(
    "-m", "yt_dlp",
    "--cookies", $cookies,
    "--ffmpeg-location", $ffmpeg,
    "--no-warnings",
    "--ignore-config",
    "--playlist-end", "$(if ($Limit -gt 0) { $Start + $Limit - 1 } else { 9999 })",
    "--sleep-requests", "1",
    "--format", $(if ($AudioOnly) { "ba/b" } else { $Quality }),
    "--merge-output-format", "mp4",
    "--embed-metadata",
    # 关键：合并必须发生在工作区内的暂存目录（ffmpeg 写不到工作区之外），
    # 再由 yt-dlp 自己（python 进程，有权限）把成品移动到 -P home。
    "--paths", "home:$Out",
    "--paths", "temp:$(Join-Path $root 'tools\dl-tmp')",
    "--output", "%(uploader)s\%(upload_date>%Y-%m-%d)s %(title).120B [%(id)s].%(ext)s"
)

if ($ListOnly) {
    $args += @("--flat-playlist", "--print", "%(id)s`t%(title)s")
} else {
    $args += @("--download-archive", $archive, "--concurrent-fragments", "4", "--newline")
    if ($Start -gt 1) { $args += @("--playlist-start", "$Start") }
    if ($Sleep -gt 0) { $args += @("--sleep-interval", "$Sleep", "--max-sleep-interval", "$($Sleep + 3)") }
}

$args += $spaceUrl
& python @args
exit $LASTEXITCODE
