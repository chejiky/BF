#!/usr/bin/env python3
"""iPhone 홈 화면용 PWA 배포 폴더(docs/) 생성.

- app/template.html + 데이터를 합쳐 독립 실행 HTML(docs/index.html) 생성
- 앱이 실제로 참조하는 이미지(스킬 시트, 아이템, 룬)만 docs/assets/로 복사
- 홈 화면 아이콘, manifest, 오프라인 캐시용 서비스워커(sw.js) 생성

사용법: python3 scripts/build_pwa.py
GitHub Pages 등 정적 호스팅에 docs/ 폴더를 그대로 올리면 된다.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_app  # noqa: E402

OUT = ROOT / "docs"
APP_NAME = "D2R 스킬·아이템 사전"
SHORT_NAME = "D2R 사전"
BG = "#0c0907"


def referenced_assets():
    """앱이 화면에서 실제로 쓰는 이미지 경로 집합."""
    need = set()
    items = json.load(open(ROOT / "data/items/uniques.json", encoding="utf-8"))["items"]
    for e in items:
        if e.get("image_src"):
            need.add("assets/items/" + e["image_src"])
    sets = json.load(open(ROOT / "data/items/sets.json", encoding="utf-8"))["sets"]
    for s in sets:
        for i in s["items"]:
            if i.get("image_src"):
                need.add("assets/items/" + i["image_src"])
    rws = json.load(open(ROOT / "data/items/runewords.json", encoding="utf-8"))["runewords"]
    for r in rws:
        for x in r["runes"]:
            need.add(f"assets/runes/{x['code']}.png")
    for p in (ROOT / "assets/skills/sheets").glob("*.png"):
        need.add(f"assets/skills/sheets/{p.name}")
    for p in (ROOT / "assets/auras").glob("*.jpg"):  # 오라 인게임 이펙트 캡처
        need.add(f"assets/auras/{p.name}")
    return sorted(need)


def make_icon(size):
    """블리자드 로고를 쓰지 않는 자체 제작 아이콘(어두운 바탕 + 금색 링 + 'D2R')."""
    S = 1024
    img = Image.new("RGB", (S, S), BG)
    px = img.load()
    for y in range(S):  # 위에서 아래로 어두워지는 그라데이션
        t = y / S
        c = (int(34 - 22 * t), int(24 - 15 * t), int(16 - 10 * t))
        for x in range(S):
            px[x, y] = c
    d = ImageDraw.Draw(img)
    gold, dim = (212, 175, 94), (138, 114, 57)
    m = 150
    d.ellipse((m, m, S - m, S - m), outline=gold, width=26)
    d.ellipse((m + 46, m + 46, S - m - 46, S - m - 46), outline=dim, width=8)
    # 룬 느낌의 다이아몬드 장식(상하)
    cx = S // 2
    for cy, dy in ((m - 4, -1), (S - m + 4, 1)):
        d.polygon([(cx, cy - 34), (cx + 34, cy), (cx, cy + 34), (cx - 34, cy)], fill=gold)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 215)
    text = "D2R"
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((cx - tw // 2 - box[0], S // 2 - th // 2 - box[1] - 10), text, font=font, fill=gold)
    return img.resize((size, size), Image.LANCZOS)


def extract_head_parts(fragment):
    """템플릿 조각에서 <title>과 폰트 <link>를 꺼낸다(조각의 나머지는 body용)."""
    title = re.search(r"<title>.*?</title>", fragment, re.S).group(0)
    links = re.findall(r"<link rel=\"stylesheet\"[^>]*>", fragment)
    body = fragment.replace(title, "", 1)
    for l in links:
        body = body.replace(l, "", 1)
    return title, "\n".join(links), body.strip()


def main():
    build_app.main()  # app/index.html 갱신
    fragment = (ROOT / "app/index.html").read_text(encoding="utf-8")
    title, links, body = extract_head_parts(fragment)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "icons").mkdir(parents=True)

    # 아이콘
    for name, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192),
                       ("icon-512.png", 512)]:
        make_icon(size).save(OUT / "icons" / name)

    # 이미지 복사
    assets = referenced_assets()
    for rel in assets:
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dst)

    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
{title}
<meta name="theme-color" content="{BG}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{SHORT_NAME}">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="icon" type="image/png" href="icons/icon-192.png">
{links}
<style>
html{{background:{BG}}}
body{{margin:0}}
img{{max-width:100%}}
[hidden]{{display:none!important}}
/* 홈 화면 실행 시 상태바 영역까지 헤더가 채우도록 */
.hdr{{top:0!important;padding-top:calc(env(safe-area-inset-top,0px) + .55rem)!important}}
</style>
</head>
<body>
{body}
<script>
if("serviceWorker" in navigator){{
  window.addEventListener("load", function(){{
    navigator.serviceWorker.register("sw.js").catch(function(){{}});
  }});
}}
</script>
</body>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")

    manifest = {
        "name": APP_NAME, "short_name": SHORT_NAME,
        "description": "디아블로 2 레저렉션 스킬·유니크·세트·룬워드·부적·큐브 레시피 사전 (비공식 팬 프로젝트)",
        "start_url": "./", "scope": "./", "display": "standalone",
        "orientation": "portrait", "lang": "ko",
        "background_color": BG, "theme_color": BG,
        "icons": [
            {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }
    (OUT / "manifest.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # 서비스워커: 내용 해시를 캐시 이름에 넣어 업데이트 시 자동 교체
    core = ["./", "index.html", "manifest.webmanifest",
            "icons/apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png"]
    h = hashlib.sha256()
    for rel in core[1:] + assets:
        h.update((OUT / rel).read_bytes())
    version = "d2r-" + h.hexdigest()[:12]
    sw = f"""const VERSION = "{version}";
const CORE = {json.dumps(core)};
const ASSETS = {json.dumps(assets)};

self.addEventListener("install", (event) => {{
  event.waitUntil((async () => {{
    const cache = await caches.open(VERSION);
    // HTTP 캐시를 우회({{cache:"reload"}})해 항상 이번 배포의 최신 파일을 담는다
    await cache.addAll(CORE.map((u) => new Request(u, {{ cache: "reload" }})));
    // 이미지는 개별 실패를 허용하며 전부 미리 담아 오프라인에서도 열리게 한다
    await Promise.all(ASSETS.map((u) =>
      cache.add(new Request(u, {{ cache: "reload" }})).catch(() => {{}})));
    await self.skipWaiting();
  }})());
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil((async () => {{
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)));
    await self.clients.claim();
  }})());
}});

self.addEventListener("fetch", (event) => {{
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // 구글 폰트 등은 네트워크에 맡김
  // 페이지(HTML)는 네트워크 우선 — 온라인이면 항상 최신 버전을 보여준다
  const isDoc = req.mode === "navigate" || req.destination === "document";
  event.respondWith((async () => {{
    if (isDoc) {{
      try {{
        // GitHub Pages는 캐시 헤더를 못 바꾸므로 HTTP 캐시를 우회해 항상 최신 HTML을 받는다
        const res = await fetch(req.url, {{ cache: "no-cache", credentials: "same-origin" }});
        if (res.ok) (await caches.open(VERSION)).put("index.html", res.clone());
        return res;
      }} catch (e) {{
        return (await caches.match(req, {{ ignoreSearch: true }}))
            || (await caches.match("index.html"));
      }}
    }}
    // 이미지·폰트 등 정적 자원은 캐시 우선(빠르고 오프라인 지원)
    const cached = await caches.match(req, {{ ignoreSearch: true }});
    if (cached) return cached;
    try {{
      const res = await fetch(req);
      if (res.ok) (await caches.open(VERSION)).put(req, res.clone());
      return res;
    }} catch (e) {{
      throw e;
    }}
  }})());
}});
"""
    (OUT / "sw.js").write_text(sw, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    total = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"docs/ 생성: {len(assets)}개 이미지, 총 {total/1e6:.1f}MB, 캐시 버전 {version}")


if __name__ == "__main__":
    main()
