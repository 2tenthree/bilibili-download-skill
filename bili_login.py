"""Bilibili QR-code login -> Netscape cookies.txt (for yt-dlp).

Flow: generate qrcode_key -> render PNG -> poll until scanned/confirmed ->
dump session cookies in Netscape format.
"""
import json
import os
import sys
import time

sys.path.insert(0, r"D:\bin\WorkSpace\DSH\tools\py")

import requests
import segno

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
ROOT = r"D:\bin\WorkSpace\DSH\tools"
OUT_COOKIES = os.path.join(ROOT, "cookies", "bili-login.txt")
QR_PNG = os.path.join(ROOT, "bili-qr.png")

H = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}


def main() -> int:
    os.makedirs(os.path.dirname(OUT_COOKIES), exist_ok=True)
    s = requests.Session()
    s.headers.update(H)

    gen = s.get(
        "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
        timeout=30,
    ).json()
    if gen.get("code") != 0:
        print("GEN_FAIL", json.dumps(gen, ensure_ascii=False)[:300])
        return 1
    data = gen["data"]
    key = data["qrcode_key"]
    url = data["url"]
    segno.make(url, error="m").save(QR_PNG, scale=6, border=3)
    print("QR_READY", QR_PNG, flush=True)
    print("QR_URL", url, flush=True)

    deadline = time.time() + 300
    state = None
    while time.time() < deadline:
        try:
            r = s.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                params={"qrcode_key": key, "source": "main-fe-header"},
                timeout=30,
            )
            j = r.json()
        except Exception as exc:  # transient network hiccup
            print("POLL_ERR", type(exc).__name__, str(exc)[:120], flush=True)
            time.sleep(2)
            continue

        code = (j.get("data") or {}).get("code")
        msg = (j.get("data") or {}).get("message")
        if code != state:
            print(f"POLL_STATE code={code} message={msg}", flush=True)
            state = code
        if code == 0:
            # cookies may be on the response or embedded in the crossDomain URL
            if j["data"].get("url"):
                from urllib.parse import parse_qsl, urlparse

                qs = dict(parse_qsl(urlparse(j["data"]["url"]).query))
                for name in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5"):
                    if qs.get(name):
                        s.cookies.set(name, qs[name], domain=".bilibili.com", path="/")
            break
        if code == 86038:  # expired
            print("QR_EXPIRED", flush=True)
            return 2
        time.sleep(2)
    else:
        print("TIMEOUT", flush=True)
        return 3

    # make sure we have a buvid pair (helps risk control)
    if "buvid3" not in s.cookies:
        try:
            spi = s.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=20).json()
            d = spi.get("data") or {}
            if d.get("b_3"):
                s.cookies.set("buvid3", d["b_3"], domain=".bilibili.com", path="/")
                s.cookies.set("buvid4", d["b_4"], domain=".bilibili.com", path="/")
        except Exception:
            pass

    now = int(time.time())
    lines = ["# Netscape HTTP Cookie File"]
    n = 0
    for c in s.cookies:
        if "bilibili" not in (c.domain or ""):
            continue
        domain = c.domain if c.domain.startswith(".") else "." + c.domain
        exp = int(c.expires) if c.expires else now + 365 * 86400
        lines.append(
            "\t".join(
                [
                    domain,
                    "TRUE",
                    c.path or "/",
                    "TRUE" if c.secure else "FALSE",
                    str(exp),
                    c.name,
                    c.value,
                ]
            )
        )
        n += 1
    with open(OUT_COOKIES, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    have = {c.name for c in s.cookies}
    print(
        "LOGIN_OK",
        OUT_COOKIES,
        "cookies=%d" % n,
        "SESSDATA=%s" % ("yes" if "SESSDATA" in have else "no"),
        "DedeUserID=%s" % (have and next((c.value for c in s.cookies if c.name == "DedeUserID"), "?"),),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
