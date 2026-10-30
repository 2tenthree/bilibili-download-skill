---
name: bilibili-download
description: "批量下载 B 站（bilibili）视频：单个视频/BV 号/UP 主空间全部投稿/合集，用本机 yt-dlp + ffmpeg 工具链。用户要下 B 站视频、扒 UP 主所有视频、只要音频时使用。"
---

# B 站视频批量下载

本机已搭好 yt-dlp + ffmpeg 工具链，不需要联网安装，直接调用即可。

## 何时用

- 「把某个 UP 主的视频都下载下来」「下载这个 B 站视频」「只要音频」
- 输入可能是：空间链接 `https://space.bilibili.com/<mid>/video`（或 `/upload/video`）、合集/收藏夹链接、单个 `https://www.bilibili.com/video/BVxxxx` 或裸 BV 号。

## 随附脚本（本技能目录内备份）

`C:\Users\wgdly\.dsh\skills\bilibili-download\` 下也存了一份 `bili-up.ps1`、`bili_login.py`、`bili_login_server.py`。若 `D:\bin\WorkSpace\DSH\tools\` 被清理，把它们复制回去（脚本里的路径指向 tools\ 下的 Python 运行时与 cookie，不复制运行时会失效）。

## 环境事实（已就绪，不要重新装）

- Python 运行时：`D:\bin\WorkSpace\DSH\tools\py`（通过 `$env:PYTHONPATH` 注入，含 yt-dlp、requests、segno、imageio-ffmpeg）
- ffmpeg：`D:\bin\WorkSpace\DSH\tools\py\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe`
- 登录 cookie：`D:\bin\WorkSpace\DSH\tools\cookies\omni-bili.txt`（从 OmniGet 复用：`%APPDATA%\wtf.tonho.omniget\cookies\bilibili.com\_default-session.txt`，含 SESSDATA；未登录时空间 API 直接 412）
- 暂存目录：`D:\bin\WorkSpace\DSH\tools\dl-tmp`（合并必须在这里，见下）

## 首选：跑现成脚本

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\bin\WorkSpace\DSH\tools\bili-up.ps1" `
  -Up "https://space.bilibili.com/<mid>/video" -Out "D:\Bilibili"
```

参数：`-Limit N` 只下最新 N 个、`-Start N`、`-AudioOnly`、`-ListOnly`（只列清单）、`-Quality`、`-Sleep`。

> 本机 PowerShell 执行策略是 Restricted，`.ps1` **必须**用 `-ExecutionPolicy Bypass` 启动；`-File` 方式传参时中文路径也安全。

## 备选：内联命令（脚本体系不可用时）

```powershell
$env:PYTHONPATH="D:\bin\WorkSpace\DSH\tools\py"; $env:PYTHONIOENCODING="utf-8"
$env:TMP="D:\bin\WorkSpace\DSH\tools\tmp"; $env:TEMP=$env:TMP
$ff = (Get-ChildItem "D:\bin\WorkSpace\DSH\tools\py\imageio_ffmpeg\binaries\ffmpeg-win-x86_64*.exe" | Select-Object -First 1).FullName
& python -m yt_dlp --cookies "D:\bin\WorkSpace\DSH\tools\cookies\omni-bili.txt" --ffmpeg-location "$ff" `
  --no-warnings --ignore-config --format "bv*[height<=1080]+ba/b" --merge-output-format mp4 --embed-metadata `
  --paths "home:D:\Bilibili" --paths "temp:D:\bin\WorkSpace\DSH\tools\dl-tmp" `
  --output "%(uploader)s\%(upload_date>%Y-%m-%d)s %(title).120B [%(id)s].%(ext)s" `
  --download-archive "D:\Bilibili\.downloaded.txt" --concurrent-fragments 4 --newline `
  --sleep-interval 2 --max-sleep-interval 5 "<URL>"
```

- 输出目录在工作区之外时，命令必须申请 `danger-full-access`（沙箱写权限）。
- 长任务用后台 job 跑；进度可直接数目标目录里的 `.mp4` 数量，或读 `.downloaded.txt` 行数（yt-dlp 的 stdout 经管道过滤会被缓冲，别指望实时输出）。

## 三个必须知道的坑

1. **ffmpeg 只能写工作区内的路径。** 即使命令提升了 `danger-full-access`，`ffmpeg.exe` 往 `D:\Bilibili`、`E:\...`、`C:\Users\...` 写文件都会 `Error opening output files: Permission denied`，但在 `D:\bin\WorkSpace\DSH\` 下正常。因此必须用 `-P temp:<工作区内暂存>` + `-P home:<目标目录>`：分片与合并都在暂存区完成，最后 yt-dlp（python 进程，有权限）自己把成品移过去。
   - 如果 `--output` 写成绝对路径，yt-dlp 会**忽略 `--paths`**（帮助里写明 "This option is ignored if --output is an absolute path"）——`--output` 必须是相对模板。
   - 失败残留：最终目录里会出现 `*.f30077.mp4`、`*.f30280.m4a` 之类分片，合并失败时手工删掉重跑即可。
2. **没登录就 412。** 空间列表接口要 SESSDATA；cookie 文件缺失时用扫码脚本补：
   `python D:\bin\WorkSpace\DSH\tools\bili_login_server.py` → 浏览器开 `http://127.0.0.1:8899/`（二维码自动刷新），登录后自动写 cookie。
3. **画质上限由账号决定。** 非大会员没有「1080P 高码率 / 4K」，`--format "bv*[height<=1080]+ba/b"` 会退到 1080P 普通码率（format 30077/30080 等）或 720P（100026）。日志里 `Format(s) 1080P 高码率 are missing` 是正常提示，不是错误。

## 完成后校验（建议每次都做）

```powershell
$dir = "D:\Bilibili\<UP名>"
$ff="D:\bin\WorkSpace\DSH\tools\py\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
Get-ChildItem $dir -Filter *.mp4 | ForEach-Object {
  $o = (& $ff -hide_banner -i $_.FullName 2>&1 | Out-String)
  if (-not (($o -match 'Video:') -and ($o -match 'Audio:'))) { "异常: " + $_.Name }
}
(Get-Content (Join-Path (Split-Path $dir) ".downloaded.txt")) | Measure-Object   # 归档条数应等于视频数
```

## 扩展（按需追加参数）

- 封面：`--write-thumbnail --convert-thumbnails jpg`
- 字幕（含 AI 字幕）：`--write-subs --sub-langs "zh-CN,ai-zh" --write-auto-subs`
- 只要音频：`-f ba/b -x --audio-format m4a`
- 弹幕需要额外工具（本机未装），若要请先确认。
