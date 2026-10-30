# bilibili-download · DSH 技能

批量下载 B 站视频的 [DSH](https://github.com/deepseek-ai) 技能：给一个 UP 主空间链接，把 TA 的**全部投稿**拉下来；也支持合集、收藏夹、单个视频、纯音频。

工具链是 [yt-dlp](https://github.com/yt-dlp/yt-dlp) + ffmpeg，本仓库只包含技能说明和几个薄封装脚本，不打包任何二进制。

## 它解决什么

- 「把这个 UP 的视频都下了」→ 一条命令，断点续传、跳过已下载、按发布日期命名
- 扫码登录一次性搞定，cookie 复用（支持从别的下载器里捡现成的 cookie）
- 踩过的坑都写进 `SKILL.md`：ffmpeg 写权限边界、`--paths` 与绝对 `--output` 互斥、未登录 412、非大会员画质上限

## 安装

1. 把 `SKILL.md` 和三个脚本放进 DSH 技能目录（Windows 默认）：

   ```
   %USERPROFILE%\.dsh\skills\bilibili-download\
   ```

2. 准备运行时（任意 Python 3.10+ 环境）：

   ```powershell
   pip install yt-dlp requests segno imageio-ffmpeg
   ```

3. 按需修改脚本顶部的 `$pyDir` / `$cookies` / `$ffmpeg` 路径，或在命令里用参数覆盖。

## 用法

```powershell
# UP 主全部视频
powershell -NoProfile -ExecutionPolicy Bypass -File .\bili-up.ps1 `
  -Up "https://space.bilibili.com/546195/video" -Out "D:\Bilibili"

# 只下最新 20 个 / 只要音频 / 只列清单
.\bili-up.ps1 -Up 546195 -Out "D:\Bilibili" -Limit 20
.\bili-up.ps1 -Up 546195 -Out "D:\Bilibili" -AudioOnly
.\bili-up.ps1 -Up 546195 -Out "D:\Bilibili" -ListOnly
```

未登录时空间接口会返回 412，先扫码：

```powershell
python .\bili_login_server.py      # 浏览器打开 http://127.0.0.1:8899/ ，二维码自动刷新
```

## 关键注意事项

1. **ffmpeg 的写入范围**：在受限沙箱（如 DSH）里 `ffmpeg.exe` 只能写工作区内的路径，所以要 `-P temp:<工作区暂存>` + `-P home:<目标目录>`，让 yt-dlp 自己完成最后的移动。`--output` 必须是相对模板，写成绝对路径会让 `--paths` 失效。
2. **执行策略**：Windows 默认 Restricted，`.ps1` 需要用 `-ExecutionPolicy Bypass` 启动。
3. **画质**：非大会员没有 1080P 高码率 / 4K，日志出现 `Format(s) 1080P 高码率 are missing` 属正常。
4. **cookie 即凭据**：本仓库不包含任何 cookie，`.gitignore` 已排除 `cookies/`。

## 文件

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 技能主体：触发场景、命令、坑位、校验方法 |
| `bili-up.ps1` | 批量下载（mid / 空间链接 → 全量投稿） |
| `bili_login.py` | 终端扫码登录，写 cookie |
| `bili_login_server.py` | 本地网页扫码登录（二维码自动刷新） |

## License

MIT © wgdlyz
