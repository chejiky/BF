#!/usr/bin/env python3
"""D2R .sprite(SpA1) 스킬 아이콘 시트에서 스킬별 PNG를 추출한다.

SpA1 포맷: magic(4) + version(u16@4) + ?(u16@6) + width(u32@8) + height(u32@12)
           + ?(u32@16) + frames(u32@20) + ... + RGBA8888 픽셀 데이터(@40)
프레임은 가로로 나열되며, skilldesc의 IconCel이 프레임 인덱스(짝수=활성)다.

사용법:
  python3 scripts/extract_sprite_icons.py --sprite waskillicon.sprite \
      --data data/skills/warlock.json --out assets/skills/warlock
"""
import argparse
import json
import struct
from pathlib import Path

from PIL import Image

ICON_SIZE = 96


def load_sprite(path):
    b = open(path, "rb").read()
    assert b[:4] == b"SpA1", f"unexpected magic {b[:4]!r}"
    width = struct.unpack_from("<I", b, 8)[0]
    height = struct.unpack_from("<I", b, 12)[0]
    frames = struct.unpack_from("<I", b, 20)[0]
    data = b[40:40 + width * height * 4]
    img = Image.frombytes("RGBA", (width, height), data)
    return img, frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprite", required=True)
    ap.add_argument("--data", required=True, help="클래스 스킬 JSON (icon_cel 포함)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sheet, frames = load_sprite(args.sprite)
    fw = sheet.width // frames
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    payload = json.load(open(args.data, encoding="utf-8"))
    for s in payload["skills"]:
        cel = s.get("icon_cel")
        if cel is None or cel >= frames:
            print("skip", s["id"], cel)
            continue
        frame = sheet.crop((cel * fw, 0, (cel + 1) * fw, sheet.height))
        # 아이콘을 정사각형으로: 투명 여백 제거 후 중앙 배치
        bbox = frame.getbbox()
        if bbox:
            frame = frame.crop(bbox)
        side = max(frame.width, frame.height)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(frame, ((side - frame.width) // 2, (side - frame.height) // 2))
        sq.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS).save(out / f"{s['id']}.png")
    print(f"done -> {out}")


if __name__ == "__main__":
    main()
