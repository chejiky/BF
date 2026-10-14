#!/usr/bin/env python3
"""스킬 툴팁 수식(skilldesc) 해석 → 레벨별 수치·시너지 문구 생성.

data/skills/<class>.json의 각 스킬에 "tooltip" 필드를 추가한다:
  per_level: [{"fmt": "냉기 피해: %d-%d", "v": [[40,45], ...레벨 1~MAXLVL]}]
  static:    ["시전 지연 시간: 1초", ...]      (레벨과 무관한 줄)
  synergies: ["얼음살: 레벨당 냉기 피해 +2%", ...]

수식 규칙은 블리자드 skills.txt 관례와 d2data의 docs/skills.js 구현을 따른다
(레벨 구간별 증가치: 2~8 / 9~16 / 17~22 / 23~28 / 29+, 마나 = (mana+lvlmana*(lvl-1))<<manashift /256,
 ln12 = par1+(lvl-1)*par2, dm12 = 체감 공식). 시너지 스킬 레벨은 0으로 두고(기본 수치) 계산한다.

사용법:
  python3 scripts/build_skill_tooltips.py --d2data <json dir> --d2r data/raw/d2r-strings.json \
      --supplement data/raw/warlock-strings.json --skills-dir data/skills
"""
import argparse
import json
import re
from pathlib import Path

from build_uniques import strip_color

MAXLVL = 20
MISSILES = {}


class Unsupported(Exception):
    pass


# ───────────── 수식 파서/평가기 ─────────────
TOKEN_RE = re.compile(r"\s*(?:(\d+\.?\d*)|([A-Za-z_][A-Za-z0-9_]*)|('[^']*')|(\.)|([()+\-*/,]))")


class Calc:
    def __init__(self, env):
        self.env = env  # 식별자/함수 해석 콜백

    def parse(self, src):
        self.toks = []
        pos = 0
        src = src.strip().strip('"')
        while pos < len(src):
            m = TOKEN_RE.match(src, pos)
            if not m or m.end() == pos:
                raise Unsupported(f"tokenize: {src!r}")
            num, ident, s, dot, op = m.groups()
            if num:
                self.toks.append(("num", float(num)))
            elif ident:
                self.toks.append(("id", ident))
            elif s:
                self.toks.append(("str", s[1:-1]))
            elif dot:
                self.toks.append(("op", "."))
            elif op:
                self.toks.append(("op", op))
            pos = m.end()
        self.i = 0
        v = self.expr()
        if self.i != len(self.toks):
            raise Unsupported(f"trailing: {src!r}")
        return v

    def peek(self, kind=None, val=None):
        if self.i >= len(self.toks):
            return None
        t = self.toks[self.i]
        if kind and t[0] != kind:
            return None
        if val is not None and t[1] != val:
            return None
        return t

    def eat(self, kind=None, val=None):
        t = self.peek(kind, val)
        if t is None:
            raise Unsupported(f"expected {kind} {val}")
        self.i += 1
        return t

    def expr(self):
        v = self.term()
        while self.peek("op", "+") or self.peek("op", "-"):
            op = self.eat()[1]
            r = self.term()
            v = v + r if op == "+" else v - r
        return v

    def term(self):
        v = self.factor()
        while self.peek("op", "*") or self.peek("op", "/"):
            op = self.eat()[1]
            r = self.factor()
            if op == "*":
                v = v * r
            else:
                v = 0 if r == 0 else v / r
        return v

    def factor(self):
        if self.peek("op", "-"):
            self.eat()
            return -self.factor()
        if self.peek("op", "("):
            self.eat()
            v = self.expr()
            self.eat("op", ")")
            return v
        t = self.eat()
        if t[0] == "num":
            return t[1]
        if t[0] == "id":
            name = t[1]
            if self.peek("op", "("):
                self.eat()
                # 참조형: skill('X'.field) / miss('X'.field) / sklvl(...)
                if self.peek("str"):
                    ref = self.eat()[1]
                    fields = []
                    while self.peek("op", "."):
                        self.eat()
                        fields.append(self.eat("id")[1])
                    self.eat("op", ")")
                    return self.env.ref(name, ref, fields)
                args = [self.expr()]
                while self.peek("op", ","):
                    self.eat()
                    args.append(self.expr())
                self.eat("op", ")")
                return self.env.func(name, args)
            return self.env.ident(name)
        raise Unsupported(f"bad token {t}")


def num(x):
    """게임 데이터 값 → 숫자. 문자열 파라미터(스킬명 등)는 미지원 처리."""
    if x in (None, ""):
        return 0
    if isinstance(x, (int, float)):
        return x
    try:
        return float(x)
    except (TypeError, ValueError):
        raise Unsupported(f"non-numeric {x!r}")


def staged(lvl, base, l1, l2, l3, l4, l5):
    """레벨 구간별 증가치 누적 (skills.txt 관례)."""
    a = base or 0
    l1, l2, l3, l4, l5 = (x or 0 for x in (l1, l2, l3, l4, l5))
    if lvl > 28:
        a += l5 * (lvl - 28); lvl = 28
    if lvl > 22:
        a += l4 * (lvl - 22); lvl = 22
    if lvl > 16:
        a += l3 * (lvl - 16); lvl = 16
    if lvl > 8:
        a += l2 * (lvl - 8); lvl = 8
    a += l1 * (max(0, lvl) - 1)
    return a


def diminish(lvl, a, b):
    return int((b - a) * int(110 * lvl / (lvl + 6)) / 100 + a)


class Env:
    def __init__(self, skills_by_key, skill, lvl):
        self.skills = skills_by_key
        self.s = skill
        self.lvl = lvl

    def param(self, n):
        return num(self.s.get(f"Param{n}", 0))

    def ident(self, name):
        s, lvl = self.s, self.lvl
        if name in ("lvl", "blvl"):
            return lvl
        m = re.fullmatch(r"par(\d+)", name)
        if m:
            return self.param(int(m.group(1)))
        m = re.fullmatch(r"pa(\d\d)", name)
        if m:
            return self.param(int(m.group(1)))
        m = re.fullmatch(r"ln(\d)(\d)", name)
        if m:
            return self.param(int(m.group(1))) + (lvl - 1) * self.param(int(m.group(2)))
        m = re.fullmatch(r"dm(\d)(\d)", name)
        if m:
            return diminish(lvl, self.param(int(m.group(1))), self.param(int(m.group(2))))
        if name == "toht":
            return num(s.get("ToHit")) + (lvl - 1) * num(s.get("LevToHit"))
        if name == "usmc":
            return (num(s.get("mana")) + num(s.get("lvlmana")) * (lvl - 1)) * (2 ** num(s.get("manashift")))
        if name == "mana":
            return max(num(s.get("minmana")), self.ident("usmc") / 256)
        if name in ("enma", "edmn"):
            return self.edmg("EMin", "EMinLev")
        if name in ("exma", "edmx"):
            return self.edmg("EMax", "EMaxLev")
        if name == "pnma":
            return self.edmg("MinDam", "MinLevDam")
        if name == "pxma":
            return self.edmg("MaxDam", "MaxLevDam")
        if name == "enms":
            return self.edmg("EMin", "EMinLev", raw=True)
        if name == "exms":
            return self.edmg("EMax", "EMaxLev", raw=True)
        if name in ("edln", "len"):
            return staged(lvl, num(s.get("ELen")), num(s.get("ELevLen1")), num(s.get("ELevLen2")), num(s.get("ELevLen3")), 0, 0)
        m = re.fullmatch(r"clc(\d)", name)
        if m:
            expr = s.get(f"calc{m.group(1)}")
            if expr in (None, ""):
                return 0
            return Calc(self).parse(str(expr))
        m = re.fullmatch(r"ast(\d)", name)
        if m:
            expr = s.get(f"aurastatcalc{m.group(1)}")
            return 0 if expr in (None, "") else Calc(self).parse(str(expr))
        if name == "alen":
            expr = s.get("auralencalc")
            return 0 if expr in (None, "") else Calc(self).parse(str(expr))
        if name == "rng":
            expr = s.get("aurarangecalc")
            return 0 if expr in (None, "") else Calc(self).parse(str(expr))
        m = re.fullmatch(r"pst(\d)", name)
        if m:
            expr = s.get(f"passivecalc{m.group(1)}")
            return 0 if expr in (None, "") else Calc(self).parse(str(expr))
        raise Unsupported(f"ident {name}")

    def edmg(self, base_key, lev_prefix, raw=False):
        s = self.s
        if s.get(base_key) is None:
            raise Unsupported(f"no {base_key}")
        v = staged(self.lvl, num(s.get(base_key)), *(num(s.get(f"{lev_prefix}{i}")) for i in range(1, 6)))
        v = v * (2 ** num(s.get("HitShift")))
        return v if raw else int(v / 256)

    def func(self, name, args):
        if name == "min":
            return min(args)
        if name == "max":
            return max(args)
        raise Unsupported(f"func {name}")

    def ref(self, kind, ref, fields):
        if kind == "miss":
            ms = MISSILES.get(ref)
            if ms is None or not fields:
                raise Unsupported(f"miss {ref}")
            f = fields[0]
            col = {"rang": "Range", "rad": "Range"}.get(f)
            m = re.fullmatch(r"par(\d)", f)
            if m:
                col = f"Param{m.group(1)}"
            if col is None or ms.get(col) is None:
                raise Unsupported(f"miss field {f}")
            return num(ms.get(col))
        if kind == "skill":
            other = self.skills.get(ref)
            if other is None:
                raise Unsupported(f"skill ref {ref}")
            f = fields[0] if fields else ""
            m = re.fullmatch(r"par(\d+)", f)
            if m:
                return num(other.get(f"Param{m.group(1)}", 0))
            # 다른 스킬의 레벨 의존 값은 '투자 0' 기준 → 0
            return 0
        raise Unsupported(f"ref {kind}")


# ───────────── 문자열 포맷 ─────────────
def fmt_num(v):
    if isinstance(v, str):
        return v
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}"


def sprintf(fmt, args):
    out, i = [], 0
    pos = 0
    for m in re.finditer(r"%([+]?)(d|s|%)", fmt):
        out.append(fmt[pos:m.start()])
        if m.group(2) == "%":
            out.append("%")
        else:
            v = args[i] if i < len(args) else ""
            i += 1
            if m.group(2) == "d" and not isinstance(v, str):
                v_int = int(v) if abs(v - round(v)) > 1e-9 and False else v
                txt = fmt_num(v_int)
                if m.group(1) == "+" and not txt.startswith("-"):
                    txt = "+" + txt
                out.append(txt)
            else:
                out.append(str(v))
        pos = m.end()
    out.append(fmt[pos:])
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d2data", required=True)
    ap.add_argument("--d2r", required=True)
    ap.add_argument("--supplement", required=True)
    ap.add_argument("--skills-dir", required=True)
    args = ap.parse_args()
    src = Path(args.d2data)
    skills_raw = json.load(open(src / "skills.json", encoding="utf-8"))
    skilldesc = json.load(open(src / "skilldesc.json", encoding="utf-8"))
    kor = json.load(open(src / "localestrings-kor.json", encoding="utf-8"))
    d2r = json.load(open(args.d2r, encoding="utf-8"))
    supp = json.load(open(args.supplement, encoding="utf-8"))

    skills_by_key = {v["skill"]: v for v in skills_raw.values() if v.get("skill")}
    MISSILES.update({v["Missile"]: v for v in
                     json.load(open(src / "missiles.json", encoding="utf-8")).values()
                     if v.get("Missile")})
    desc_by_name = {v["skilldesc"]: v for v in skilldesc.values() if "skilldesc" in v}

    def ko(key):
        if not key:
            return ""
        d = d2r.get(key)
        if d and d["ko"].strip():
            return strip_color(d["ko"]).replace("\n", " ")
        v = kor.get(key, "").strip()
        if v:
            return strip_color(v).replace("\n", " ")
        s = supp.get(key)
        return strip_color(s["ko"]).replace("\n", " ") if s and s["ko"] else ""

    def skill_name(key):
        """textb가 가리키는 스킬명 문자열 키 → 한국어."""
        return ko(key) or key

    def render_line(func, ta, tb, ca, cb, env):
        """desc 함수 번호별 한 줄 렌더링 → (fmt, args) 또는 None(건너뜀)."""
        calc = Calc(env)

        def ev(x):
            if x in (None, ""):
                return None
            if isinstance(x, (int, float)):
                return float(x)
            return num(calc.parse(str(x)))

        texta, textb = ko(ta), ko(tb)
        if func in (18,):
            return (texta, []) if texta else None
        if func in (13, 74):
            v = ev(ca)
            return (texta, [v]) if texta and v is not None else None
        if func in (31, 36):
            a, b = ev(ca), ev(cb)
            if a is None:
                return None
            v = a / b if b else a
            # 단수/복수 문자열: 한국어는 동일하므로 texta 사용
            return (texta, [v]) if texta else None
        if func in (34,):
            a, b = env.ident("pnma"), env.ident("pxma")
            return (texta, [a, b]) if texta else None
        if func in (41, 75):
            a, b = ev(ca), ev(cb)
            if a is None or b is None:
                return None
            return (texta, [a, b]) if texta else None
        if func == 40:
            return (texta, [skill_name(tb)]) if texta else None
        if func == 76:
            v = ev(ca)
            return (texta, [skill_name(tb), v]) if texta and v is not None else None
        if func == 77:
            a, b = ev(ca), ev(cb)
            return (texta, [skill_name(tb), a, b]) if texta and a is not None else None
        if func == 78:
            return (texta, [textb]) if texta else None
        if func == 79:
            a, b = ev(ca), ev(cb)
            if a is None:
                return None
            v = a / b if b else a
            return (texta, [skill_name(tb), v]) if texta else None
        raise Unsupported(f"func {func}")

    stats = {"lines": 0, "dropped": 0, "skills": 0}
    dropped_examples = []

    for cls_file in sorted(Path(args.skills_dir).glob("*.json")):
        if cls_file.name == "index.json":
            continue
        payload = json.load(open(cls_file, encoding="utf-8"))
        # 영문명 → 내부 스킬키 매핑 (skilldesc.str name으로 역추적)
        for entry in payload["skills"]:
            # 내부 키 찾기: 같은 클래스 스킬 중 아이콘/위치가 같은 것
            s = None
            for key, row in skills_by_key.items():
                d = desc_by_name.get(row.get("skilldesc", ""))
                if d and row.get("charclass") and d.get("SkillPage") == entry["tree"]["page"] \
                        and d.get("SkillRow") == entry["position"]["row"] \
                        and d.get("SkillColumn") == entry["position"]["col"] \
                        and row.get("charclass") == payload["class"][:3].replace("war", "war"):
                    pass
            # 더 단순하게: icon_cel + class 로 매칭
            cand = [row for key, row in skills_by_key.items()
                    if row.get("charclass") and desc_by_name.get(row.get("skilldesc", ""), {}).get("IconCel") == entry["icon_cel"]
                    and desc_by_name.get(row.get("skilldesc", ""), {}).get("SkillPage") == entry["tree"]["page"]
                    and CLASS_CODE[payload["class"]] == row.get("charclass")]
            if not cand:
                continue
            s = cand[0]
            d = desc_by_name[s["skilldesc"]]
            per_level, static, synergies = [], [], []
            lines_spec = []
            for pre in ("desc", "dsc2"):
                for i in range(1, 8):
                    f = d.get(f"{pre}line{i}")
                    if f:
                        lines_spec.append((f, d.get(f"{pre}texta{i}"), d.get(f"{pre}textb{i}"),
                                           d.get(f"{pre}calca{i}"), d.get(f"{pre}calcb{i}")))
            for spec in lines_spec:
                try:
                    results = []
                    for lvl in range(1, MAXLVL + 1):
                        r = render_line(*spec, Env(skills_by_key, s, lvl))
                        results.append(r)
                    if results[0] is None:
                        continue
                    fmt = results[0][0]
                    vals = [r[1] for r in results]
                    stats["lines"] += 1
                    if all(v == vals[0] for v in vals):
                        static.append(sprintf(fmt, vals[0]))
                    else:
                        per_level.append({"fmt": fmt, "v": [[round(x, 2) if isinstance(x, float) else x for x in v] for v in vals]})
                except Unsupported as e:
                    stats["dropped"] += 1
                    if len(dropped_examples) < 12:
                        dropped_examples.append((entry["name_en"], spec[1], spec[3], str(e)))
            for i in range(1, 8):
                f = d.get(f"dsc3line{i}")
                if not f:
                    continue
                try:
                    r = render_line(f, d.get(f"dsc3texta{i}"), d.get(f"dsc3textb{i}"),
                                    d.get(f"dsc3calca{i}"), d.get(f"dsc3calcb{i}"),
                                    Env(skills_by_key, s, 1))
                    if r:
                        synergies.append(sprintf(r[0], r[1]))
                except Unsupported as e:
                    stats["dropped"] += 1
            entry["tooltip"] = {"per_level": per_level, "static": static, "synergies": synergies}
            stats["skills"] += 1
        json.dump(payload, open(cls_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(stats)
    for ex in dropped_examples:
        print("  dropped:", ex)


CLASS_CODE = {"amazon": "ama", "assassin": "ass", "barbarian": "bar", "druid": "dru",
              "necromancer": "nec", "paladin": "pal", "sorceress": "sor", "warlock": "war"}

if __name__ == "__main__":
    main()
