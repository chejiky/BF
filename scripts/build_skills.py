#!/usr/bin/env python3
"""D2R 클래스별 스킬 데이터 생성 스크립트.

입력: @blizzhackers/d2data npm 패키지의 json 파일들
  (skills.json, skilldesc.json, localestrings-kor.json, localestrings-eng.json)
출력: data/skills/<class>.json (7개 클래스) + data/skills/index.json

사용법:
  npm pack @blizzhackers/d2data && tar xzf blizzhackers-d2data-*.tgz
  python3 scripts/build_skills.py --d2data ./package/json --out ./data/skills
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

CLASSES = {
    "ama": {"en": "Amazon", "slug": "amazon"},
    "ass": {"en": "Assassin", "slug": "assassin"},
    "bar": {"en": "Barbarian", "slug": "barbarian"},
    "dru": {"en": "Druid", "slug": "druid"},
    "nec": {"en": "Necromancer", "slug": "necromancer"},
    "pal": {"en": "Paladin", "slug": "paladin"},
    "sor": {"en": "Sorceress", "slug": "sorceress"},
}

CLASS_TAB_KEY = {
    "ama": "Am", "ass": "As", "bar": "Ba", "dru": "Dr",
    "nec": "Ne", "pal": "Pa", "sor": "So",
}

SYNERGY_RE = re.compile(r"skill\('([^']+)'\.blvl\)")


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fix_lines(text: str) -> str:
    """D2 문자열은 줄이 아래→위 순서로 저장되므로 자연스러운 순서로 뒤집는다."""
    if not text:
        return ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return " ".join(reversed(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d2data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src = Path(args.d2data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    skills_raw = json.load(open(src / "skills.json", encoding="utf-8"))
    # skills.json은 인덱스 키이므로 내부 스킬명('skill' 필드)으로 재색인
    skills = {v["skill"]: v for v in skills_raw.values() if "skill" in v}
    skilldesc = json.load(open(src / "skilldesc.json", encoding="utf-8"))
    kor = json.load(open(src / "localestrings-kor.json", encoding="utf-8"))
    eng = json.load(open(src / "localestrings-eng.json", encoding="utf-8"))

    # skilldesc는 인덱스 키 → 엔트리. 'skilldesc' 필드명으로 역색인.
    desc_by_name = {v["skilldesc"]: v for v in skilldesc.values() if "skilldesc" in v}

    # 트리 탭 한국어 이름: StrSklTabItemN의 "+%d ..." 접두어를 떼고,
    # 영문 SkillCategory 이름과 매칭한다.
    def norm_tab(s):
        s = re.sub(r"^\+%d( to)? ", "", s)
        s = re.sub(r" (Skills?|Spells?)$", "", s)
        return s.replace(" and ", " & ").lower()

    tab_ko_by_en = {}
    for k, v_en in eng.items():
        if k.startswith("StrSklTabItem") and k in kor:
            v_ko = re.sub(r"^\+%d\s*", "", kor[k]).strip()
            tab_ko_by_en[norm_tab(v_en)] = v_ko

    def tab_ko(tree_en):
        n = norm_tab(tree_en)
        if n in tab_ko_by_en:
            return tab_ko_by_en[n]
        # 부분 일치 (예: "Combat Masteries" ↔ "+%d to Masteries")
        for key, v in tab_ko_by_en.items():
            if n.endswith(key) or key.endswith(n):
                return v
        return tree_en

    def ko_str(key):
        """한국어 로케일은 확장팩 설명이 skillxld 대신 구버전 skillld 키에 있다."""
        v = kor.get(key, "")
        if not v.strip() and key.startswith("skillxld"):
            v = kor.get(key.replace("skillxld", "skillld"), "")
        return v

    # 내부 스킬 키 → (영문명, 한글명, slug) 매핑 (선행스킬/시너지 표기용)
    name_cache = {}

    def display_names(skill_key):
        if skill_key in name_cache:
            return name_cache[skill_key]
        s = skills.get(skill_key)
        res = None
        if s:
            d = desc_by_name.get(s.get("skilldesc", ""))
            if d:
                nk = d.get("str name", "")
                en_name = eng.get(nk, skill_key).strip()
                ko_name = kor.get(nk, en_name).strip()
                res = {"id": slugify(en_name), "name_en": en_name, "name_ko": ko_name}
        if res is None:
            res = {"id": slugify(skill_key), "name_en": skill_key, "name_ko": skill_key}
        name_cache[skill_key] = res
        return res

    index = {"classes": []}

    for code, meta in CLASSES.items():
        cls_skills = []
        for skill_key, s in skills.items():
            if s.get("charclass") != code:
                continue
            d = desc_by_name.get(s.get("skilldesc", ""))
            if not d or not d.get("SkillPage"):
                continue

            nk, sk = d.get("str name", ""), d.get("str short", "")
            lk = d.get("str long", sk)
            page = d["SkillPage"]
            # SkillPage(1~3)와 SkillCategory 번호는 서로 역순이다
            # (예: 소서리스 page 3 = Cold = SkillCategorySo1)
            cat_key = f"SkillCategory{CLASS_TAB_KEY[code]}{4 - page}"
            tree_en = eng.get(cat_key, f"Tree {page}")
            tree_ko = tab_ko(tree_en)

            # 시너지: 수식 필드 내 skill('X'.blvl) 패턴 (블리자드의 시너지 표준 표기)
            syn = []
            for fk, fv in s.items():
                if isinstance(fv, str):
                    for m in SYNERGY_RE.findall(fv):
                        if m != skill_key and m not in syn:
                            syn.append(m)

            prereqs = [s[f"reqskill{i}"] for i in (1, 2, 3) if s.get(f"reqskill{i}")]

            en_name = eng.get(nk, skill_key).strip()
            entry = {
                "id": slugify(en_name),
                "name_en": en_name,
                "name_ko": kor.get(nk, en_name).strip(),
                "tree": {"page": page, "name_en": tree_en, "name_ko": tree_ko},
                "position": {"row": d.get("SkillRow"), "col": d.get("SkillColumn")},
                "icon_cel": d.get("IconCel"),
                "required_level": s.get("reqlevel", 1),
                "max_level": s.get("maxlvl", 20),
                "mana_cost": s.get("mana"),
                "mana_per_level": s.get("lvlmana"),
                "element": s.get("EType"),
                "prerequisites": [display_names(p) for p in prereqs],
                "synergies": [display_names(x) for x in syn],
                "description_ko": fix_lines(ko_str(sk)),
                "description_en": fix_lines(eng.get(sk, "")),
            }
            lk_ko = fix_lines(ko_str(lk))
            if lk != sk and lk_ko and lk_ko != entry["description_ko"]:
                entry["description_long_ko"] = lk_ko
            cls_skills.append(entry)

        cls_skills.sort(key=lambda e: (e["tree"]["page"], e["required_level"],
                                       e["position"]["row"] or 0, e["position"]["col"] or 0))
        payload = {
            "class": meta["slug"],
            "class_name_en": meta["en"],
            "class_name_ko": kor.get(meta["en"], meta["en"]),
            "skill_count": len(cls_skills),
            "skills": cls_skills,
        }
        (out / f"{meta['slug']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        index["classes"].append({
            "slug": meta["slug"],
            "name_en": meta["en"],
            "name_ko": payload["class_name_ko"],
            "skill_count": len(cls_skills),
            "file": f"{meta['slug']}.json",
        })
        print(f"{meta['slug']}: {len(cls_skills)} skills")

    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done ->", out)


if __name__ == "__main__":
    main()
