#!/usr/bin/env python3
"""스킬 트리 이미지에서 스킬별 아이콘(96x96 PNG)을 잘라내는 스크립트.

입력: d2planner(GPL-3) 저장소의 1.14D 스킬 트리 이미지 (640x864 JPG, 클래스당 3장)
  https://github.com/d2planner/d2planner
출력: assets/skills/<class>/<skill_id>.png

주의: 잘라낸 아이콘 이미지의 저작권은 Blizzard Entertainment에 있다.
비상업적 팬 콘텐츠 용도로만 사용할 것 (NOTICE.md 참고).

사용법:
  python3 scripts/extract_icons.py \
      --images <d2planner>/d2planner/src/assets/1.14D/game_images \
      --data ./data/skills --out ./assets/skills
"""
import argparse
import json
from pathlib import Path

from PIL import Image

# d2planner Skill.css의 그리드 좌표 (이미지 크기 대비 %)
ROW_TOP = [3.3, 18.7, 34.3, 49.8, 65.4, 81.0]
COL_LEFT = [4.82, 26.3, 47.9]
ICON_SIZE = 96  # 640x864 이미지는 원본 48px 아이콘의 2배 스케일


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="class_tree_N.jpg 디렉토리")
    ap.add_argument("--data", required=True, help="data/skills 디렉토리")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    images = Path(args.images)
    data = Path(args.data)
    out = Path(args.out)

    index = json.load(open(data / "index.json", encoding="utf-8"))
    total = 0
    for cls in index["classes"]:
        slug = cls["slug"]
        payload = json.load(open(data / cls["file"], encoding="utf-8"))
        (out / slug).mkdir(parents=True, exist_ok=True)
        trees = {}
        for s in payload["skills"]:
            page = s["tree"]["page"]
            if page not in trees:
                trees[page] = Image.open(images / f"{slug}_tree_{page}.jpg")
            img = trees[page]
            W, H = img.size
            r, c = s["position"]["row"], s["position"]["col"]
            x = round(COL_LEFT[c - 1] / 100 * W)
            y = round(ROW_TOP[r - 1] / 100 * H)
            icon = img.crop((x, y, x + ICON_SIZE + 1, y + ICON_SIZE))
            icon = icon.resize((ICON_SIZE, ICON_SIZE))
            icon.save(out / slug / f"{s['id']}.png")
            total += 1
        print(f"{slug}: {len(payload['skills'])} icons")
    print(f"done: {total} icons -> {out}")


if __name__ == "__main__":
    main()
