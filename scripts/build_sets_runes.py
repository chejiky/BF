#!/usr/bin/env python3
"""D2R 세트 아이템 / 룬워드 / 부적 데이터 생성.

build_uniques.py의 렌더러를 재사용한다.

사용법:
  python3 scripts/build_sets_runes.py --d2data ./package/json \
      --supplement data/raw/items-strings.json --d2r data/raw/d2r-strings.json \
      --skills-dir data/skills \
      --archives <d2archives>/src/common/config/uniqueAndSetData.json \
      --out-dir data/items
"""
import argparse
import json
import re
from pathlib import Path

from build_uniques import (Renderer, slugify, strip_color, rng,
                           CLASS_EN, ELEM_KO)

ITYPE_KO = {
    "weap": "모든 무기", "mele": "근접 무기", "miss": "원거리 무기(활·석궁)",
    "tors": "갑옷", "shld": "방패", "helm": "투구", "shie": "방패",
    "swor": "검", "axe": "도끼", "mace": "메이스", "club": "곤봉",
    "hamm": "망치", "scep": "셉터", "wand": "완드", "staf": "지팡이",
    "knif": "단검", "spea": "창", "pole": "폴암", "bow": "활",
    "xbow": "석궁", "orb": "오브", "h2h": "클로", "ashd": "팔라딘 방패",
    "head": "네크로맨서 두개골", "pelt": "드루이드 투구", "phlm": "바바리안 투구",
    "grim": "마도서(그리무아르)", "circ": "서클릿", "belt": "벨트",
    "boot": "신발", "glov": "장갑", "jave": "투창", "wlbw": "악마술사 무기",
}

AFFIX_RE = re.compile(r".+-Affix\d$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d2data", required=True)
    ap.add_argument("--supplement", required=True)
    ap.add_argument("--d2r", required=True)
    ap.add_argument("--skills-dir", required=True)
    ap.add_argument("--archives", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    src = Path(args.d2data)
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    def load(name):
        return json.load(open(src / f"{name}.json", encoding="utf-8"))

    d2 = {n: load(n) for n in
          ["uniqueitems", "setitems", "sets", "runes", "weapons", "armor",
           "misc", "itemtypes", "itemstatcost", "properties", "skills",
           "skilldesc"]}
    kor = load("localestrings-kor")
    eng = load("localestrings-eng")
    supp = json.load(open(args.supplement, encoding="utf-8"))
    d2r = json.load(open(args.d2r, encoding="utf-8"))

    d2r_norm = {}
    for k, v in d2r.items():
        if v["ko"].strip():
            d2r_norm.setdefault(re.sub(r"[^a-z0-9]", "", k.lower()), v)

    def d2r_get(*keys):
        for k in keys:
            if not k:
                continue
            d = d2r.get(k)
            if d and d["ko"].strip():
                return d
            d = d2r_norm.get(re.sub(r"[^a-z0-9]", "", str(k).lower()))
            if d:
                return d
        return None

    def ko_classic(key, default=""):
        v = kor.get(key, "").strip()
        return strip_color(v) if v else default

    def ko(key, default=""):
        if not key:
            return default
        d = d2r.get(key)
        if d and d["ko"].strip():
            return strip_color(d["ko"])
        v = kor.get(key, "").strip()
        if v:
            return strip_color(v)
        s = supp.get(key)
        return strip_color(s["ko"]) if s and s["ko"] else default

    def en(key, default=""):
        if not key:
            return default
        v = eng.get(key, "").strip()
        if v:
            return strip_color(v)
        s = supp.get(key)
        if s and s["en"]:
            return strip_color(s["en"])
        d = d2r.get(key)
        return strip_color(d["en"]) if d and d["en"] else default

    def names_of(key, fallback):
        """(en, ko, ko_classic)"""
        e = en(key, fallback)
        d = d2r_get(key, e)
        classic = ko_classic(key)
        k = strip_color(d["ko"]) if d else (classic or e)
        if classic == k:
            classic = ""
        return e, k, classic

    # ── 스킬/트리 참조 (build_uniques와 동일 요령) ──
    skills_by_key = {v["skill"]: v for v in d2["skills"].values() if v.get("skill")}
    sdesc_by_name = {v["skilldesc"]: v for v in d2["skilldesc"].values()
                     if "skilldesc" in v}
    skill_names = {}
    for key, s in skills_by_key.items():
        d = sdesc_by_name.get(s.get("skilldesc", ""), {})
        nm = ko(d.get("str name", ""), key) or key
        skill_names[key] = nm
        if "*Id" in s:
            skill_names[str(s["*Id"])] = nm
        cc = s.get("charclass")
        if cc:
            cls_ko = ko(CLASS_EN[cc], CLASS_EN[cc])
            skill_names["skillclass:" + key] = cls_ko
            if "*Id" in s:
                skill_names["skillclass:" + str(s["*Id"])] = cls_ko
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

    def render_props(row, prefix="prop", par="par", mn="min", mx="max", n=12):
        lines = []
        affix = False
        for i in range(1, n + 1):
            p = row.get(f"{prefix}{i}")
            if not p or str(p).startswith("*"):
                continue
            if AFFIX_RE.fullmatch(str(p)):
                affix = True
                continue
            lines += rend.render(p, row.get(f"{par}{i}"), row.get(f"{mn}{i}"),
                                 row.get(f"{mx}{i}"), row)
        lines.sort(key=lambda t: -t[0])
        texts = [t for _, t in lines]
        if affix:
            texts.append("무작위 추가 속성 (제작 보너스)")
        return texts

    base = {}
    for kind in ["weapons", "armor", "misc"]:
        for v in d2[kind].values():
            if v.get("code"):
                v["_kind"] = kind
                base[v["code"]] = v

    arch = json.load(open(args.archives, encoding="utf-8"))["content"]
    arch_sets = {}
    for nm, v in arch["setItems"].items():
        arch_sets[re.sub(r"[^a-z0-9]", "", nm.lower())] = v

    # ══ 1) 세트 ══
    set_rows = [v for v in d2["sets"].values() if v.get("index") and v.get("name")]
    items_by_set = {}
    for v in d2["setitems"].values():
        if v.get("index") and v.get("item") and v.get("set"):
            items_by_set.setdefault(v["set"], []).append(v)

    sets_out = []
    for srow in set_rows:
        sidx = srow["index"]
        rows = items_by_set.get(sidx, [])
        if not rows:
            continue
        s_en, s_ko, s_classic = names_of(sidx, sidx)
        items = []
        for r in sorted(rows, key=lambda x: x.get("lvl req", 0)):
            i_en, i_ko, i_classic = names_of(r["index"], r["index"])
            b = base.get(r["item"], {})
            bonuses = []
            # add func 2: aprop{n}a/b는 세트 n+1개 착용 시 추가
            for nth in range(1, 6):
                for ab in ("a", "b"):
                    p = r.get(f"aprop{nth}{ab}")
                    if not p:
                        continue
                    ls = rend.render(p, r.get(f"apar{nth}{ab}"),
                                     r.get(f"amin{nth}{ab}"),
                                     r.get(f"amax{nth}{ab}"), r)
                    for _, t in ls:
                        bonuses.append({"count": nth + 1, "text": t})
            a = arch_sets.get(re.sub(r"[^a-z0-9]", "", i_en.lower()))
            entry = {
                "id": slugify(i_en),
                "name_en": i_en,
                "name_ko": i_ko,
                **({"name_ko_classic": i_classic} if i_classic else {}),
                "base": {"code": r["item"], "name_en": en(r["item"], r["item"]),
                         "name_ko": ko(r["item"], r["item"])},
                "required_level": r.get("lvl req", 0),
                "props_ko": render_props(r, n=9),
                "set_bonuses": bonuses,
            }
            if a:
                entry["image_src"] = a.get("image", "").replace("/images/Items/", "")
            items.append(entry)

        partial, full = [], []
        for nth in (2, 3, 4, 5):
            for ab in ("a", "b"):
                p = srow.get(f"PCode{nth}{ab}")
                if not p:
                    continue
                for _, t in rend.render(p, srow.get(f"PParam{nth}{ab}"),
                                        srow.get(f"PMin{nth}{ab}"),
                                        srow.get(f"PMax{nth}{ab}"), srow):
                    partial.append({"count": nth, "text": t})
        for i in range(1, 9):
            p = srow.get(f"FCode{i}")
            if not p:
                continue
            for _, t in rend.render(p, srow.get(f"FParam{i}"),
                                    srow.get(f"FMin{i}"), srow.get(f"FMax{i}"),
                                    srow):
                full.append(t)
        sets_out.append({
            "id": slugify(s_en),
            "name_en": s_en,
            "name_ko": s_ko,
            **({"name_ko_classic": s_classic} if s_classic else {}),
            "item_count": len(items),
            "min_level": min((i["required_level"] for i in items), default=0),
            "items": items,
            "partial_bonuses": partial,
            "full_bonuses": full,
        })
    sets_out.sort(key=lambda s: s["min_level"])
    json.dump({"count": len(sets_out), "sets": sets_out},
              open(outdir / "sets.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ══ 2) 룬워드 ══
    rw_out = []
    for v in d2["runes"].values():
        if not v.get("complete"):
            continue
        name_internal = v.get("*Rune Name", "")
        key = v.get("Name", "")
        r_en = name_internal or en(key, key)
        d = d2r_get(key, name_internal)
        classic = ko_classic(key)
        r_ko = strip_color(d["ko"]) if d else (classic or r_en)
        if classic == r_ko:
            classic = ""
        runes = []
        req = 0
        for i in range(1, 7):
            rc = v.get(f"Rune{i}")
            if not rc:
                continue
            rb = base.get(rc, {})
            req = max(req, rb.get("levelreq", 0))
            runes.append({"code": rc,
                          "name_ko": ko(rc + "L", rc),
                          "name_en": en(rc + "L", rc)})
        bases = []
        for i in range(1, 7):
            t = v.get(f"itype{i}")
            if t:
                tt = [x for x in d2["itemtypes"].values() if x.get("Code") == t]
                bases.append(ITYPE_KO.get(t, (tt[0].get("ItemType") if tt else t)))
        rw_out.append({
            "id": slugify(r_en),
            "name_en": r_en,
            "name_ko": r_ko,
            **({"name_ko_classic": classic} if classic and classic != r_en else {}),
            "runes": runes,
            "sockets": len(runes),
            "bases_ko": bases,
            "required_level": req,
            "props_ko": render_props(v, prefix="T1Code", par="T1Param",
                                     mn="T1Min", mx="T1Max", n=7),
        })
    rw_out.sort(key=lambda r: (r["sockets"], r["required_level"]))
    json.dump({"count": len(rw_out), "runewords": rw_out},
              open(outdir / "runewords.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ══ 3) 부적 ══
    sizes = {}
    for c in ("cm1", "cm2", "cm3"):
        b = base.get(c, {})
        sizes[c] = f"{b.get('invwidth', 1)}×{b.get('invheight', 1)}"
    basics = []
    for c, note in [
        ("cm1", "인벤토리 1칸. 접두·접미 마법 속성이 1~2개 붙는다. 레벨당 효율이 가장 좋아 고급 참 자리를 차지한다."),
        ("cm2", "인벤토리 2칸. 작은 부적보다 수치 폭이 넓지만 칸 효율은 떨어진다."),
        ("cm3", "인벤토리 3칸. 스킬 탭 +1(스킬러) 접두가 붙을 수 있는 유일한 크기다."),
    ]:
        c_en, c_ko, c_classic = names_of(c, c)
        basics.append({"code": c, "name_en": c_en, "name_ko": c_ko,
                       **({"name_ko_classic": c_classic} if c_classic else {}),
                       "size": sizes[c], "note": note})

    SUNDER_ELEM = {
        "Cold Rupture": ("cold", "냉기"), "Flame Rift": ("fire", "화염"),
        "Crack of the Heavens": ("ltng", "번개"),
        "Rotting Fissure": ("pois", "독"), "Bone Break": ("phys", "물리"),
        "Black Cleft": ("mag", "마법"),
    }
    urows = {v["index"]: v for v in d2["uniqueitems"].values() if v.get("index")}
    sunder = []
    for base_idx, (el, el_ko) in SUNDER_ELEM.items():
        group = {"element": el, "element_ko": el_ko}
        for variant, prefix in [("latent", "PreCrafted "), ("crafted", "Crafted ")]:
            r = urows.get(prefix + base_idx)
            if not r:
                continue
            v_en, v_ko, _ = names_of(prefix + base_idx, prefix + base_idx)
            group[variant] = {"name_en": v_en, "name_ko": v_ko,
                              "required_level": r.get("lvl req", 0),
                              "props_ko": render_props(r)}
        sunder.append(group)

    charms = {"basics": basics,
              "unique_ids": ["annihilus", "hellfire-torch", "gheeds-fortune"],
              "sunder": sunder}
    json.dump(charms, open(outdir / "charms.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"sets: {len(sets_out)} | runewords: {len(rw_out)} | sunder groups: {len(sunder)}")
    print("unknown props:", sorted(rend.unknown))
    noimg = sum(1 for s in sets_out for i in s["items"] if "image_src" not in i)
    print("set items w/o image:", noimg)


if __name__ == "__main__":
    main()
