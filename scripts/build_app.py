#!/usr/bin/env python3
"""app/template.html에 스킬 데이터를 주입해 app/index.html을 생성한다.

사용법: python3 scripts/build_app.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    data = {}
    skills_dir = ROOT / "data" / "skills"
    index = json.load(open(skills_dir / "index.json", encoding="utf-8"))
    for cls in index["classes"]:
        data[cls["slug"]] = json.load(open(skills_dir / cls["file"], encoding="utf-8"))
    def minify(obj):
        # </script> 류 시퀀스가 JSON 문자열에 있어도 안전하도록 이스케이프
        return json.dumps(obj, ensure_ascii=False,
                          separators=(",", ":")).replace("</", "<\\/")

    items = json.load(open(ROOT / "data" / "items" / "uniques.json",
                           encoding="utf-8"))["items"]
    tpl = (ROOT / "app" / "template.html").read_text(encoding="utf-8")
    out = tpl.replace("__SKILL_DATA__", minify(data))
    out = out.replace("__ITEM_DATA__", minify(items))
    (ROOT / "app" / "index.html").write_text(out, encoding="utf-8")
    print(f"app/index.html: {len(out):,} bytes")


if __name__ == "__main__":
    main()
