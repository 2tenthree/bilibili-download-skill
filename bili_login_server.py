"""Bilibili QR login helper: local page with auto-refreshing QR code.

Serves on http://127.0.0.1:8899
  /          HTML page (QR refreshes automatically, shows state)
  /qr.png    current QR image
  /state     JSON state

On successful scan it writes Netscape cookies.txt for yt-dlp.
"""
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlparse

sys.path.insert(0, r"D:\bin\WorkSpace\DSH\tools\py")

import requests
import segno

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
ROOT = r"D:\bin\WorkSpace\DSH\tools"
OUT_COOKIES = os.path.join(ROOT, "cookies", "bili-login.txt")
PORT = int(os.environ.get("BILI_LOGIN_PORT", "8899"))

H = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}

STATE = {
    "phase": "init",      # init | waiting | scanned | ok | expired | error
    "message": "",
    "code": None,
    "key": None,
    "url": None,
    "png": None,          # bytes
    "issued_at": 0.0,
    "cookies": 0,
    "sessdata": False,
}
LOCK = threading.Lock()
SESSION = requests.Session()
SESSION.headers.update(H)


def _log(*a):
    print(*a, flush=True)


def _set(**kw):
    with LOCK:
        STATE.update(kw)


def make_qr():
    gen = SESSION.get(
        "https://passport.bilibili.com/x/passport-login/web/qrcode/generate", timeout=30
    ).json()
    if gen.get("code") != 0:
        raise RuntimeError(str(gen)[:200])
    data = gen["data"]
    png = io.BytesIO()
    segno.make(data["url"], error="m").save(png, kind="png", scale=6, border=3)
    _set(
        phase="waiting",
        message="等待扫码",
        key=data["qrcode_key"],
        url=data["url"],
        png=png.getvalue(),
        issued_at=time.time(),
        code=None,
    )
    _log("QR_READY", data["qrcode_key"])


def save_cookies():
    if "buvid3" not in SESSION.cookies:
        try:
            d = SESSION.get(
                "https://api.bilibili.com/x/frontend/finger/spi", timeout=20
            ).json().get("data") or {}
            if d.get("b_3"):
                SESSION.cookies.set("buvid3", d["b_3"], domain=".bilibili.com", path="/")
                SESSION.cookies.set("buvid4", d["b_4"], domain=".bilibili.com", path="/")
        except Exception:
            pass
    now = int(time.time())
    lines = ["# Netscape HTTP Cookie File"]
    n = 0
    for c in SESSION.cookies:
        if "bilibili" not in (c.domain or ""):
            continue
        domain = c.domain if c.domain.startswith(".") else "." + c.domain
        exp = int(c.expires) if c.expires else now + 30 * 86400
        lines.append(
            "\t".join(
                [domain, "TRUE", c.path or "/", "TRUE" if c.secure else "FALSE",
                 str(exp), c.name, c.value]
            )
        )
        n += 1
    os.makedirs(os.path.dirname(OUT_COOKIES), exist_ok=True)
    with open(OUT_COOKIES, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    have = {c.name for c in SESSION.cookies}
    _set(phase="ok", message="登录成功，cookie 已保存", cookies=n,
         sessdata="SESSDATA" in have)
    _log("LOGIN_OK cookies=%d SESSDATA=%s" % (n, "SESSDATA" in have))
    return n


def worker():
    while True:
        try:
            if STATE["phase"] in ("init", "expired"):
                make_qr()
            age = time.time() - STATE["issued_at"]
            if age > 170 and STATE["phase"] == "waiting":
                _set(phase="expired", message="二维码过期，正在刷新")
                continue
            if STATE["phase"] == "waiting":
                r = SESSION.get(
                    "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                    params={"qrcode_key": STATE["key"], "source": "main-fe-header"},
                    timeout=25,
                )
                j = r.json()
                d = j.get("data") or {}
                code, msg = d.get("code"), d.get("message") or ""
                if code != STATE["code"]:
                    _set(code=code, message=msg or STATE["message"])
                    _log("POLL_STATE", code, msg)
                if code == 0:
                    if d.get("url"):
                        qs = dict(parse_qsl(urlparse(d["url"]).query))
                        for name in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5"):
                            if qs.get(name):
                                SESSION.cookies.set(name, qs[name], domain=".bilibili.com", path="/")
                    save_cookies()
                elif code == 86090:
                    _set(phase="scanned", message="已扫码，请在手机上确认登录")
                elif code == 86038:
                    _set(phase="expired", message="二维码已过期，正在刷新")
                else:
                    _set(phase="waiting", message=msg or "等待扫码")
            if STATE["phase"] == "ok":
                time.sleep(3600)  # keep serving the success page
                continue
        except Exception as exc:
            _set(phase="error", message="%s: %s" % (type(exc).__name__, str(exc)[:120]))
            _log("WORKER_ERR", type(exc).__name__, str(exc)[:160])
            time.sleep(2)
        time.sleep(1.5)


PAGE = """<!doctype html><meta charset=utf-8><title>B站扫码登录</title>
<style>
body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#14161a;color:#e6e6e6;
display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#1d2026;padding:28px 34px;border-radius:14px;box-shadow:0 8px 30px #0006;text-align:center}
h2{margin:0 0 6px;font-size:19px;font-weight:600}
#state{color:#8ab4f8;font-size:14px;margin-bottom:16px;min-height:20px}
img{width:280px;height:280px;background:#fff;padding:8px;border-radius:10px}
.ok{color:#5bd67a !important}
.tip{color:#8b93a1;font-size:12px;margin-top:14px}
</style>
<div class=card>
  <h2>用 B 站 App 扫码登录</h2>
  <div id=state>加载中…</div>
  <img id=qr src="/qr.png?t=0" alt="二维码">
  <div class=tip>二维码会自动刷新，无需手动操作</div>
</div>
<script>
let last = "";
async function tick(){
  try{
    const s = await (await fetch("/state", {cache:"no-store"})).json();
    const txt = s.message || s.phase;
    if (txt !== last){ document.getElementById("state").textContent = txt; last = txt; }
    const now = Date.now();
    if (now - +(new URL(document.getElementById("qr").src).searchParams.get("t")||0) > 4000){
      document.getElementById("qr").src = "/qr.png?t=" + now;
    }
    if (s.phase === "ok"){
      document.getElementById("state").className = "ok";
      document.getElementById("state").textContent =
        "✓ 登录成功，已保存 cookie（" + s.cookies + " 项）" + (s.sessdata ? "" : "，但缺少 SESSDATA");
      return;
    }
  }catch(e){}
  setTimeout(tick, 1200);
}
tick();
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            return self._send(200, PAGE)
        if path == "/qr.png":
            with LOCK:
                png = STATE["png"]
            if not png:
                return self._send(503, b"no qr yet", "text/plain")
            return self._send(200, png, "image/png")
        if path == "/state":
            with LOCK:
                slim = {k: v for k, v in STATE.items() if k not in ("png", "url", "key")}
            return self._send(200, json.dumps(slim, ensure_ascii=False), "application/json")
        return self._send(404, "not found", "text/plain")


def main():
    threading.Thread(target=worker, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    _log("LISTEN http://127.0.0.1:%d/" % PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
