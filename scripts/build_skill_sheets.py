#!/usr/bin/env python3
"""클래스별 스킬 아이콘 96px PNG들을 6×5 스프라이트 시트로 합친다.

셀 순서는 data/skills/<class>.json의 skills 배열 순서와 동일하다
(앱이 배열 인덱스로 배경 위치를 계산한다).

사용법: python3 scripts/build_skill_sheets.py
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
COLS, ROWS, CELL = 6, 5, 96


def main():
    out_dir = ROOT / "assets" / "skills" / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    index = json.load(open(ROOT / "data" / "skills" / "index.json", encoding="utf-8"))
    for cls in index["classes"]:
        slug = cls["slug"]
        payload = json.load(open(ROOT / "data" / "skills" / cls["file"],
                                 encoding="utf-8"))
        sheet = Image.new("RGBA", (COLS * CELL, ROWS * CELL), (0, 0, 0, 0))
        for i, s in enumerate(payload["skills"]):
            p = ROOT / "assets" / "skills" / slug / f"{s['id']}.png"
            icon = Image.open(p).convert("RGBA").resize((CELL, CELL))
            sheet.paste(icon, ((i % COLS) * CELL, (i // COLS) * CELL))
        sheet.save(out_dir / f"{slug}.png")
        print(slug, "sheet ok")


if __name__ == "__main__":
    main()
