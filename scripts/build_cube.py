#!/usr/bin/env python3
"""호라드림 큐브 레시피(cubemain.json) → 한국어 레시피 목록 생성.

사용법:
  python3 scripts/build_cube.py --d2data <json dir> \
      --supplement data/raw/items-strings.json --d2r data/raw/d2r-strings.json \
      --skills-dir data/skills --out data/items/cube_recipes.json
"""
import argparse
import json
import re
from pathlib import Path

from build_uniques import Renderer, strip_color, CLASS_EN

# 아이템 종류 토큰 (코드가 itemtypes에 있을 때)
TYPE_KO = {
    "weap": "모든 무기", "armo": "모든 방어구", "shld": "방패", "tors": "갑옷",
    "helm": "투구", "ring": "반지", "rin": "반지", "amul": "목걸이",
    "amu": "목걸이", "belt": "벨트", "boot": "신발", "glov": "장갑",
    "staf": "지팡이", "wand": "완드", "scep": "셉터", "swor": "검",
    "axe": "도끼", "spea": "창", "pole": "폴암", "mace": "메이스",
    "blun": "둔기류", "shie": "방패", "jew": "주얼",
    "any": "아무 아이템", "item": "아무 아이템",
    "gem0": "조각난 보석(아무거나)", "gem1": "금간 보석(아무거나)",
    "gem2": "일반 보석(아무거나)", "gem3": "흠 없는 보석(아무거나)",
    "gem4": "완전한 보석(아무거나)",
}

QUAL_KO = {
    "low": "저급", "nor": "노멀", "hiq": "상급", "mag": "매직", "rar": "레어",
    "set": "세트", "uni": "유니크", "crf": "제작", "tmp": "임시",
    "eth": "에테리얼", "noe": "비에테리얼", "nos": "소켓 없음",
    "sock": "소켓 있음", "bas": "기본 등급", "exc": "익셉셔널", "eli": "엘리트",
    "upg": "상위 등급 포함", "nru": "룬워드 아님",
}

CRAFT_KO = {"Blood": "피(블러드)", "Caster": "시전(캐스터)",
            "Hit Power": "타격(히트 파워)", "Safety": "안전(세이프티)"}

SPECIAL_OUT = {"Cow Portal": "비밀 소 레벨 포탈",
               "Pandemonium Portal": "판데모니움 포탈",
               "Red Portal": "붉은 포탈"}


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
          ["cubemain", "itemstatcost", "properties", "skills", "skilldesc",
           "itemtypes", "weapons", "armor", "misc", "uniqueitems"]}
    kor = load("localestrings-kor")
    eng = load("localestrings-eng")
    supp = json.load(open(args.supplement, encoding="utf-8"))
    d2r = json.load(open(args.d2r, encoding="utf-8"))

    def ko(key, default=""):
        d = d2r.get(key)
        if d and d["ko"].strip():
            return strip_color(d["ko"])
        v = kor.get(key, "").strip()
        if v:
            return strip_color(v)
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

    types = {v.get("Code"): v for v in d2["itemtypes"].values() if v.get("Code")}
    codes = set()
    for kind in ("weapons", "armor", "misc"):
        for v in d2[kind].values():
            if v.get("code"):
                codes.add(v["code"])
    unique_idx = {v["index"] for v in d2["uniqueitems"].values() if v.get("index")}

    skill_names = {}
    for cc, enname in CLASS_EN.items():
        skill_names["class:" + cc] = ko(enname, enname)
    sdesc_by_name = {v["skilldesc"]: v for v in d2["skilldesc"].values()
                     if "skilldesc" in v}
    for key, s in ((v["skill"], v) for v in d2["skills"].values() if v.get("skill")):
        d = sdesc_by_name.get(s.get("skilldesc", ""), {})
        nm = ko(d.get("str name", ""), key) or key
        skill_names[key] = nm
        if "*Id" in s:
            skill_names[str(s["*Id"])] = nm
    tree_names = {}
    for cls_file in Path(args.skills_dir).glob("*.json"):
        if cls_file.name == "index.json":
            continue
        payload = json.load(open(cls_file, encoding="utf-8"))
        code = [c for c, m in CLASS_EN.items()
                if m.lower() == payload["class_name_en"].lower()]
        if code:
            for s in payload["skills"]:
                tree_names[(code[0], s["tree"]["page"])] = s["tree"]["name_ko"]
    rend = Renderer(d2, ko, en, tree_names, skill_names)

    def token_ko(tok):
        """입력/출력 명세의 쉼표 토큰 하나를 번역."""
        tok = tok.strip()
        m = re.fullmatch(r"qty=(\d+)", tok)
        if m:
            return f"×{m.group(1)}"
        m = re.fullmatch(r"sock=(\d+)", tok)
        if m:
            return f"소켓 {m.group(1)}개"
        if tok in QUAL_KO:
            return QUAL_KO[tok]
        if tok in TYPE_KO:
            return TYPE_KO[tok]
        if tok in codes:
            v = ko(tok, tok).split("\n")[0]
            return re.sub(r"\s*\(#\d+\)", "", v).strip()  # 룬 번호 표기 제거
        if tok in unique_idx:
            return ko(tok, en(tok, tok))
        if tok in types:
            return types[tok].get("ItemType", tok)
        return None  # 미해석

    def spec_ko(spec):
        """'\"fhl,mag,upg\"' 같은 명세 → (한국어, 미해석여부)"""
        spec = str(spec).strip().strip('"')
        toks = spec.split(",")
        parts, unknown = [], False
        qty = ""
        quals = []
        name = None
        for t in toks:
            v = token_ko(t)
            if v is None:
                unknown = True
                parts.append(t)
            elif v.startswith("×"):
                qty = v
            elif t in QUAL_KO:
                quals.append(v)
            else:
                name = v
        label = name or " ".join(parts) or spec
        if quals:
            label = f"{' '.join(quals)} {label}"
        if qty:
            label = f"{label} {qty}"
        return label, unknown

    def output_ko(r):
        out = str(r.get("output", "")).strip().strip('"')
        if out in SPECIAL_OUT:
            return SPECIAL_OUT[out]
        toks = out.split(",")
        if toks[0] == "useitem":
            if "exc" in toks:
                return "같은 아이템 → 익셉셔널 등급으로 업그레이드"
            if "eli" in toks:
                return "같은 아이템 → 엘리트 등급으로 업그레이드"
            if "rep" in toks:
                return "같은 아이템 (수리·충전)"
            if "uns" in toks:
                return "같은 아이템 — 소켓 비우기 (박힌 룬·보석 파괴)"
            m = [t for t in toks if t.startswith("sock=")]
            if m:
                return f"같은 아이템에 소켓 {m[0].split('=')[1]}개 추가"
            return "같은 아이템 (속성 변경)"
        if toks[0] == "usetype":
            if "crf" in toks:
                return "같은 부위의 제작(크래프트) 아이템"
            if "mag" in toks:
                return "같은 종류의 매직 아이템 (리롤)"
            if "rar" in toks:
                return "같은 종류의 레어 아이템 (리롤)"
            return "같은 종류의 아이템"
        label, _ = spec_ko(out)
        return label

    def mods_of(r):
        lines = []
        for i in range(1, 6):
            c = r.get(f"mod {i}")
            if not c:
                continue
            lines += rend.render(c, r.get(f"mod {i} param"),
                                 r.get(f"mod {i} min"), r.get(f"mod {i} max"), r)
        return [t.replace("item_levelreq", "착용 레벨")
                for _, t in sorted(lines, key=lambda x: -x[0])]

    def category_of(r, desc, out):
        d = desc.lower()
        o = str(r.get("output", ""))
        if any(w in desc for w in ("Latent", "Rupture", "Cleft", "Rift",
                                   "Fissure", "Bone Break", "Crack of the Heavens")):
            return "분쇄 부적 제작"
        if "crf" in o:
            return "크래프팅"
        ins = " ".join(str(r.get(f"input {i}", "")) for i in range(1, 8))
        if re.search(r"\br\d\d\b", ins) and re.fullmatch(r"r\d\d", o.strip('"')):
            return "룬 업그레이드"
        if re.search(r"g[a-z]g|g[a-z]v|g[a-z]w|g[a-z]b|g[a-z]y|g[a-z]r|sku|gem\d", ins) \
                and (re.fullmatch(r"[a-z]{3}", o.strip('"')) and o.strip('"').startswith(("g", "sk"))):
            return "보석 업그레이드"
        if "mod 1" in r and r.get("mod 1") == "sock":
            return "소켓"
        if "exc" in o or "eli" in o:
            return "등급 업그레이드"
        if "mag" in o or "rar" in o:
            return "리롤"
        if any(q in ins for q in ("msf", "vip", "qf1", "leg", "tbk", "bet",
                                  "bey", "beo", "mbr", "dhn", "bks", "bkd",
                                  "hst", "xa1", "xa2", "xa3")) \
                or out in SPECIAL_OUT.values():
            return "퀘스트·특수"
        if re.search(r"ps\b|potion|rejuv|hp\d|mp\d|rv[sl]", d + " " + ins):
            return "물약"
        return "기타"

    cats = {}
    unresolved = []
    for r in d2["cubemain"].values():
        if not r.get("enabled") or not r.get("output"):
            continue
        desc = r.get("description", "")
        inputs = []
        bad = False
        for i in range(1, (r.get("numinputs") or 7) + 1):
            spec = r.get(f"input {i}")
            if not spec:
                continue
            label, unknown = spec_ko(spec)
            bad = bad or unknown
            inputs.append(label)
        out = output_ko(r)
        # 크래프트 유형명 한국어화
        m = re.search(r"-> (Blood|Caster|Hit Power|Safety) (\w+)", desc)
        if m:
            out = f"{CRAFT_KO[m.group(1)]} 크래프트 {spec_ko(str(r.get('input 1','')))[0].split()[-1]}"
            out = re.sub(r"×\d+$", "", out).strip()
        entry = {
            "inputs_ko": inputs,
            "output_ko": out,
            "desc_en": desc,
        }
        mods = mods_of(r)
        if mods:
            entry["output_mods_ko"] = mods
        if bad:
            unresolved.append(desc)
        cat = category_of(r, desc, out)
        cats.setdefault(cat, []).append(entry)

    order = ["룬 업그레이드", "보석 업그레이드", "소켓", "등급 업그레이드",
             "크래프팅", "리롤", "분쇄 부적 제작", "물약", "퀘스트·특수", "기타"]
    out_cats = [{"label": c, "recipes": cats[c]} for c in order if c in cats]
    for c in cats:
        if c not in order:
            out_cats.append({"label": c, "recipes": cats[c]})

    data = {"categories": out_cats,
            "note": "모든 재료를 호라드림 큐브에 넣고 변환 버튼을 누르면 완성됩니다."}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(len(c["recipes"]) for c in out_cats)
    print(f"recipes: {total} | categories: {[(c['label'], len(c['recipes'])) for c in out_cats]}")
    print("unresolved tokens in:", len(unresolved), unresolved[:6])
    print("unknown props:", sorted(rend.unknown))


if __name__ == "__main__":
    main()
