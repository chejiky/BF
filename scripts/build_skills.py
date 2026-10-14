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
    "war": {"en": "Warlock", "slug": "warlock"},
}

CLASS_TAB_KEY = {
    "ama": "Am", "ass": "As", "bar": "Ba", "dru": "Dr",
    "nec": "Ne", "pal": "Pa", "sor": "So", "war": "Wa",
}

SYNERGY_RE = re.compile(r"skill\('([^']+)'\.blvl\)")

# 원본 게임 데이터 퀴크: Poison Creeper(내부명 Plague Poppy)의 skilldesc가
# 워울프 문자열(Skillname223 등)을 가리킨다. 실제 이름은 UI 문자열 strUI8에 있고
# 전용 설명 문자열은 존재하지 않아 설명만 수동으로 보충한다.
OVERRIDES = {
    "Plague Poppy": {
        "name_key": "strUI8",
        "description_ko": "적을 공격하는 독성 덩굴을 소환함",
        "description_en": "summons a poisonous vine to attack your enemies",
    },
}


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
    ap.add_argument("--supplement", default=None,
                    help="워록(ROTW) 등 d2data 로케일에 없는 문자열 보충 파일 "
                         "(data/raw/warlock-strings.json)")
    ap.add_argument("--d2r", default=None,
                    help="D2R 재번역 문자열 덤프 (data/raw/d2r-strings.json). "
                         "지정 시 D2R 명칭이 기본, 구작(TBL) 명칭은 *_classic로 병기")
    args = ap.parse_args()
    src = Path(args.d2data)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 보충 문자열: 구버전 .tbl과 달리 줄 순서가 자연스러운 신규(D2R json) 문자열
    supp = {}
    if args.supplement and Path(args.supplement).exists():
        supp = json.load(open(args.supplement, encoding="utf-8"))
    d2r = {}
    if args.d2r and Path(args.d2r).exists():
        d2r = json.load(open(args.d2r, encoding="utf-8"))

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

    def natural(text):
        """신규 문자열은 역순이 아니므로 줄바꿈만 공백으로 합친다."""
        return " ".join(l.strip() for l in text.split("\n") if l.strip())

    def name_pair(key, fallback):
        """이름 문자열 (en, ko[, ko_classic]): D2R 재번역을 기본으로 하고
        구작(TBL) 명칭이 다르면 세 번째 값으로 돌려준다."""
        en_v = ko_v = classic = ""
        if key in eng or key in kor:
            en_v = eng.get(key, fallback).strip()
            classic = kor.get(key, en_v).strip()
        elif key in supp:
            en_v = supp[key]["en"] or fallback
            classic = supp[key]["ko"] or en_v
        else:
            en_v = classic = fallback
        d = d2r.get(key)
        ko_v = (d["ko"].strip() if d and d["ko"].strip() else classic)
        if ko_v == classic:
            classic = ""
        return en_v, ko_v, classic

    def desc_pair(key):
        """설명 문자열 (ko, en): D2R(자연 순서) 우선, 구 로케일은 역순 보정."""
        d = d2r.get(key)
        if d and d["ko"].strip():
            return natural(d["ko"]), natural(d["en"]) or fix_lines(eng.get(key, ""))
        if key in kor or key in eng:
            return fix_lines(ko_str(key)), fix_lines(eng.get(key, ""))
        if key in supp:
            return natural(supp[key]["ko"]), natural(supp[key]["en"])
        return "", ""

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
                ov = OVERRIDES.get(skill_key, {})
                nk = ov.get("name_key") or d.get("str name", "")
                en_name, ko_name, _ = name_pair(nk, skill_key)
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

            ov = OVERRIDES.get(skill_key, {})
            nk, sk = ov.get("name_key") or d.get("str name", ""), d.get("str short", "")
            lk = d.get("str long", sk)
            page = d["SkillPage"]
            # 기존 7클래스는 SkillPage(1~3)와 SkillCategory 번호가 역순이다
            # (예: 소서리스 page 3 = Cold = SkillCategorySo1). 워록은 정방향.
            cat_idx = page if code == "war" else 4 - page
            cat_key = f"SkillCategory{CLASS_TAB_KEY[code]}{cat_idx}"
            dc = d2r.get(cat_key)
            if dc and dc["ko"].strip():
                tree_en, tree_ko = dc["en"] or eng.get(cat_key, f"Tree {page}"), dc["ko"]
            elif cat_key in supp:
                tree_en, tree_ko = supp[cat_key]["en"], supp[cat_key]["ko"]
            else:
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

            en_name, ko_name, ko_classic = name_pair(nk, skill_key)
            entry = {
                "id": slugify(en_name),
                "name_en": en_name,
                "name_ko": ko_name,
                **({"name_ko_classic": ko_classic} if ko_classic else {}),
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
                "description_ko": ov.get("description_ko") or desc_pair(sk)[0],
                "description_en": ov.get("description_en") or desc_pair(sk)[1],
            }
            lk_ko = desc_pair(lk)[0]
            if not ov and lk != sk and lk_ko and lk_ko != entry["description_ko"]:
                entry["description_long_ko"] = lk_ko
            cls_skills.append(entry)

        cls_skills.sort(key=lambda e: (e["tree"]["page"], e["required_level"],
                                       e["position"]["row"] or 0, e["position"]["col"] or 0))
        cls_en, cls_ko, cls_classic = name_pair(meta["en"], meta["en"])
        payload = {
            "class": meta["slug"],
            "class_name_en": cls_en,
            "class_name_ko": cls_ko,
            **({"class_name_ko_classic": cls_classic} if cls_classic else {}),
            "skill_count": len(cls_skills),
            "skills": cls_skills,
        }
        (out / f"{meta['slug']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        index["classes"].append({
            "slug": meta["slug"],
            "name_en": meta["en"],
            "name_ko": payload["class_name_ko"],
            **({"name_ko_classic": cls_classic} if cls_classic else {}),
            "skill_count": len(cls_skills),
            "file": f"{meta['slug']}.json",
        })
        print(f"{meta['slug']}: {len(cls_skills)} skills")

    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done ->", out)


if __name__ == "__main__":
    main()
