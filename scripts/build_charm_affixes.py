#!/usr/bin/env python3
"""매직 부적(참) 접두/접미사 전체 티어 표 생성.

magicprefix.json / magicsuffix.json에서 부적(scha/mcha/lcha)에 등장 가능한
접사(spawnable=1)를 크기별·계열별로 정리한다. 스킬러(+1 스킬 탭) 접두어는
클래스별 요약으로 별도 수록.

사용법:
  python3 scripts/build_charm_affixes.py --d2data <json dir> \
      --supplement data/raw/items-strings.json --d2r data/raw/d2r-strings.json \
      --skills-dir data/skills --out data/items/charm_affixes.json
"""
import argparse
import json
import re
from pathlib import Path

from build_uniques import Renderer, strip_color, CLASS_EN

SIZES = [("scha", "작은 부적"), ("mcha", "큰 부적"), ("lcha", "거대 부적")]

# mod1code → 계열 라벨 (표시 순서 포함)
CATEGORY = [
    (r"^hp$|^hp/lvl$", "생명력"),
    (r"^mana$", "마나"),
    (r"^regen$", "생명력 회복"),
    (r"^ac$", "방어력"),
    (r"^att$", "공격 등급"),
    (r"^dmg-max$", "최대 데미지"),
    (r"^dmg-min$", "최소 데미지"),
    (r"^dmg-fire$", "화염 데미지"),
    (r"^dmg-ltng$", "번개 데미지"),
    (r"^dmg-cold$", "냉기 데미지"),
    (r"^dmg-pois$", "독 데미지"),
    (r"^res-all$", "모든 저항"),
    (r"^res-fire", "화염 저항"),
    (r"^res-ltng", "번개 저항"),
    (r"^res-cold", "냉기 저항"),
    (r"^res-pois", "독 저항"),
    (r"^balance", "타격 회복 속도"),
    (r"^move|^frw", "달리기/걷기 속도"),
    (r"^mag%$", "마법 아이템 발견"),
    (r"^gold%$", "골드 획득"),
    (r"^str$", "힘"),
    (r"^dex$", "민첩"),
    (r"^light$", "빛 반경"),
    (r"^stam$", "지구력"),
]


def category_of(code):
    for pat, label in CATEGORY:
        if re.search(pat, code or ""):
            return label
    return "기타"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d2data", required=True)
    ap.add_argument("--supplement", required=True)
    ap.add_argument("--d2r", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src = Path(args.d2data)

    def load(name):
        return json.load(open(src / f"{name}.json", encoding="utf-8"))

    d2 = {n: load(n) for n in
          ["magicprefix", "magicsuffix", "itemstatcost", "properties",
           "skills", "skilldesc"]}
    kor = load("localestrings-kor")
    eng = load("localestrings-eng")
    supp = json.load(open(args.supplement, encoding="utf-8"))
    d2r = json.load(open(args.d2r, encoding="utf-8"))

    def ko_classic(key):
        v = kor.get(key, "").strip()
        return strip_color(v) if v else ""

    def ko(key, default=""):
        d = d2r.get(key)
        if d and d["ko"].strip():
            return strip_color(d["ko"])
        v = ko_classic(key)
        if v:
            return v
        s = supp.get(key)
        return strip_color(s["ko"]) if s and s["ko"] else default

    def en(key, default=""):
        v = eng.get(key, "").strip()
        if v:
            return strip_color(v)
        s = supp.get(key)
        if s and s["en"]:
            return strip_color(s["en"])
        d = d2r.get(key)
        return strip_color(d["en"]) if d and d["en"] else default

    # 렌더러 (스킬탭 표기를 위해 스킬/트리 참조 구성)
    skill_names = {}
    for cc, enname in CLASS_EN.items():
        skill_names["class:" + cc] = ko(enname, enname)
    tree_names = {}
    for cls_file in Path(args.skills_dir).glob("*.json"):
        if cls_file.name == "index.json":
            continue
        payload = json.load(open(cls_file, encoding="utf-8"))
        code = [c for c, m in CLASS_EN.items()
                if m.lower() == payload["class_name_en"].lower()]
        if not code:
            continue
        for s in payload["skills"]:
            tree_names[(code[0], s["tree"]["page"])] = s["tree"]["name_ko"]
    rend = Renderer(d2, ko, en, tree_names, skill_names)

    def affix_rows(table, size):
        out = []
        for v in table.values():
            if not v.get("spawnable") or not v.get("Name"):
                continue
            its = [v.get(f"itype{i}") for i in range(1, 8)]
            if not any(t in (size, "char") for t in its if t):
                continue
            out.append(v)
        return out

    def render_mods(v):
        lines = []
        for i in (1, 2, 3):
            c = v.get(f"mod{i}code")
            if not c:
                continue
            lines += rend.render(c, v.get(f"mod{i}param"), v.get(f"mod{i}min"),
                                 v.get(f"mod{i}max"), v)
        return [t for _, t in sorted(lines, key=lambda x: -x[0])]

    def affix_entry(v):
        name = v["Name"]
        e = en(name, name)
        k = ko(name, e)
        classic = ko_classic(name)
        if classic == k:
            classic = ""
        return {
            "name_en": e, "name_ko": k,
            **({"name_ko_classic": classic} if classic else {}),
            "alvl": v.get("level", 1),
            **({"max_alvl": v["maxlevel"]} if v.get("maxlevel") else {}),
            "levelreq": v.get("levelreq", 1),
            "mods_ko": render_mods(v),
        }

    sizes_out = []
    skillers = {}
    for size, size_ko in SIZES:
        size_entry = {"code": size, "name_ko": size_ko, "prefixes": [], "suffixes": []}
        for kind, table in [("prefixes", d2["magicprefix"]),
                            ("suffixes", d2["magicsuffix"])]:
            cats = {}
            for v in affix_rows(table, size):
                if v.get("mod1code") in ("skilltab", "skilltab-war"):
                    # 스킬러: 클래스별 요약으로 별도 수록 (거대 부적 전용)
                    cc = v.get("classspecific")
                    if cc:
                        t = int(v.get("mod1param") or 0)
                        page = (t % 3) + 1
                        cls = "war" if v.get("mod1code") == "skilltab-war" else cc
                        name = v["Name"]
                        skillers.setdefault(cls, []).append({
                            "prefix_ko": ko(name, name),
                            "prefix_classic": ko_classic(name),
                            "tree_ko": tree_names.get((cls, page), f"탭{page}"),
                            "alvl": v.get("level", 1),
                            "levelreq": v.get("levelreq", 1),
                        })
                    continue
                entry = affix_entry(v)
                cat = category_of(v.get("mod1code"))
                cats.setdefault(cat, []).append(entry)
            order = [label for _, label in CATEGORY] + ["기타"]
            for cat in order:
                if cat in cats:
                    cats[cat].sort(key=lambda a: a["alvl"])
                    size_entry[kind].append({"label": cat, "affixes": cats[cat]})
        sizes_out.append(size_entry)

    skillers_out = []
    for cc in CLASS_EN:
        if cc in skillers:
            rows = skillers[cc]
            rows.sort(key=lambda r: r["tree_ko"])
            skillers_out.append({"class_ko": skill_names["class:" + cc],
                                 "class_en": CLASS_EN[cc], "tabs": rows})

    out = {"sizes": sizes_out, "skillers": skillers_out,
           "note": "매직 부적은 접두어 1개 + 접미어 1개까지 붙는다. "
                   "alvl은 해당 접사가 등장하기 시작하는 아이템 레벨."}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(len(c["affixes"]) for s in sizes_out
                for k in ("prefixes", "suffixes") for c in s[k])
    print(f"affixes: {total} | skiller classes: {len(skillers_out)}")
    print("unknown props:", sorted(rend.unknown))


if __name__ == "__main__":
    main()
