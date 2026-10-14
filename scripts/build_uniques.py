#!/usr/bin/env python3
"""D2R 유니크 아이템 데이터 생성 스크립트.

uniqueitems.json의 속성(prop/par/min/max)을 공식 한국어 라벨로 렌더링해
data/items/uniques.json을 생성한다.

사용법:
  python3 scripts/build_uniques.py --d2data ./package/json \
      --supplement data/raw/items-strings.json \
      --archives <d2archives>/src/common/config/uniqueAndSetData.json \
      --out data/items/uniques.json
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

# d2archives 매핑이 없거나 틀린 아이템의 이미지 파일 직접 지정
IMAGE_OVERRIDES = {
    "Windforce": "windforce.png",          # d2archives json이 blastbark로 잘못 연결
    "Gimmershred": "gimmershred.png",
    "Rainbow Facet": "jewel05.png",        # 주얼 공용 그래픽 (대체 이미지)
    "Hellfire Torch": "hellfiretorch.png",  # d2archives json은 .jpg로 잘못 표기
}

# 퀘스트 전용 아이템(장비 유니크가 아님)
QUEST_INDEXES = {
    "Amulet of the Viper", "Staff of Kings", "Horadric Staff",
    "Hell Forge Hammer", "KhalimFlail", "SuperKhalimFlail",
}

CLASS_ORDER = ["ama", "sor", "nec", "pal", "bar", "dru", "ass", "war"]
CLASS_EN = {"ama": "Amazon", "sor": "Sorceress", "nec": "Necromancer",
            "pal": "Paladin", "bar": "Barbarian", "dru": "Druid",
            "ass": "Assassin", "war": "Warlock"}

ELEM_KO = {"fire": "화염", "ltng": "번개", "cold": "냉기",
           "pois": "독", "mag": "마법", "phys": "물리"}

# 값이 %로 표시되는 스탯
PERCENT_STATS = {
    "item_fasterattackrate", "item_fastercastrate", "item_fastergethitrate",
    "item_fasterblockrate", "item_fastermovevelocity", "item_magicbonus",
    "item_goldbonus", "item_damagepercent", "item_armorpercent",
    "item_tohit_percent", "fireresist", "lightresist", "coldresist",
    "poisonresist", "magicresist", "maxfireresist", "maxlightresist",
    "maxcoldresist", "maxpoisonresist", "lifedrainmindam", "manadrainmindam",
    "item_reducedprices", "item_fastexp", "item_crushingblow",
    "item_openwounds", "item_deadlystrike", "item_slow", "damageresist",
    "item_howl", "item_stupidity", "item_damagetomana", "item_ignoretargetac",
    "item_fractionaltargetac", "item_preventheal", "item_halffreezeduration",
    "item_pierce", "item_demondamage_percent", "item_undeaddamage_percent",
    "item_absorbfirepercent", "item_absorblightpercent",
    "item_absorbmagicpercent", "item_absorbcoldpercent",
    "item_staminadrainpct", "maxdamage_percent",
    "item_maxdamage_percent", "item_chancetoblock",
    "item_armor_percent", "item_maxmana_percent", "item_maxhp_percent",
    "staminarecoverybonus", "manarecoverybonus", "toblock",
    "item_extrablood", "item_deepwounds", "passive_fire_mastery",
    "passive_ltng_mastery", "passive_cold_mastery", "passive_pois_mastery",
    "passive_mag_mastery", "passive_fire_pierce", "passive_ltng_pierce",
    "passive_cold_pierce", "passive_pois_pierce", "passive_mag_pierce",
}

# 라벨 없이/특수 포맷으로 렌더링하는 속성
# 함수는 (min, max, par, ctx) → 문구 또는 None


def slugify(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "item"


def strip_color(s):
    s = re.sub(r"ÿc[0-9a-zA-Z;:/<]?", "", s or "")
    s = re.sub(r"[¹²³⁴⁵]", "", s)  # 게임 내 티어 구분 첨자 제거
    return s.strip().strip("*").strip()  # 색 코드 사이 장식 문자 제거


# 발동(proc) 레벨이 0인 아이템: 아이템/착용자 레벨에 비례하는 특수 케이스.
# 게임 내 표시 범위는 공식/DB(diablowiki, vhpg, rankedboost 등 D2R 자료)에서 확인한 값.
# 키: (uniqueitems index, 스킬 par 문자열)
PROC_LEVEL0_RANGES = {
    ("Lightsabre", "53"): "14~20",        # 연쇄 번개
    ("Snowclash", "59"): "7~19",          # 눈보라
    ("The Rising Sun", "56"): "13~19",    # 운석 낙하
    ("Stormrider", "38"): "13~20",        # 번개 줄기
    ("Boneslayer Blade", "101"): "12~20", # 신성한 빛줄기
    ("Hellslayer", "47"): "16~20",        # 화염구
    ("Stormspire", "38"): "20",           # 번개 줄기 (고정 20으로 표시됨)
}


def rng(mn, mx, pct=False, sign=True):
    unit = "%" if pct else ""
    if mn is None and mx is None:
        return ""
    if mn is None: mn = mx
    if mx is None: mx = mn
    if mn == mx:
        v = mn
        s = f"{v:+d}" if sign else f"{v}"
        return f"{s}{unit}"
    pre = "+" if sign and mn >= 0 else ""
    return f"{pre}{mn}~{mx}{unit}"


class Renderer:
    def __init__(self, d2, ko, en, tree_names, skill_names):
        self.props = {r["code"]: r for r in d2["properties"].values() if r.get("code")}
        self.isc = {r["Stat"]: r for r in d2["itemstatcost"].values() if r.get("Stat")}
        self.ko, self.en = ko, en
        self.tree_names = tree_names    # (class_code, page) -> ko
        self.skill_names = skill_names  # 내부 스킬키/ID -> ko
        self.unknown = set()

    def label(self, stat):
        r = self.isc.get(stat)
        if not r:
            return None, 0
        key = r.get("descstrpos", "")
        return self.ko(key) or self.en(key) or stat, r.get("descpriority", 0) or 0

    def skill_ko(self, par):
        return self.skill_names.get(str(par), str(par))

    def render(self, prop, par, mn, mx, item):
        p = prop
        E = ELEM_KO
        out = []

        def add(text, prio=50):
            out.append((prio, text))

        # ── 레벨 비례 속성 ──
        if p.endswith("/lvl"):
            base = p[:-4]
            # 레벨당 증가치(1/8 단위)는 보통 par에 있지만, 일부 행은 min/max에 있고 범위일 수도 있음
            # (예: 인내 hp/lvl min8 max12 → 레벨당 생명력 +1~1.5, 잎새 ac/lvl min16 → +2)
            per = (par or 0) / 8
            per_hi = per
            if not par and (mn or mx):
                per = (mn if mn is not None else mx) / 8
                per_hi = (mx if mx is not None else mn) / 8
            label_map = {
                "dmg%": "증가된 데미지(%)", "dmg": "최대 데미지",
                "hp": "생명력", "mana": "마나",
                "ac": "방어력", "att": "공격 등급", "str": "힘", "dex": "민첩",
                "vit": "활력", "stam": "지구력", "gold%": "골드 획득량(%)",
                "mag%": "마법 아이템 발견 확률(%)", "thorns": "공격자가 받는 데미지",
                "dmg-und": "언데드에게 추가 데미지(%)", "att-und": "언데드 상대 공격력",
                "dmg-dem": "악마에게 추가 데미지(%)", "att-dem": "악마 상대 공격력",
                "res-ltng": "번개 저항(%)", "abs-cold": "냉기 흡수",
                "abs-fire": "화염 흡수", "deadly": "치명타 확률(%)",
                "att%": "명중률(%)", "regen-stam": "지구력 회복 속도",
                "dmg-fire": "화염 데미지", "dmg-cold": "냉기 데미지",
                "dmg-ltng": "번개 데미지", "dmg-pois": "독 데미지",
            }
            lbl = label_map.get(base, base)
            unit = ""
            if lbl.endswith("(%)"):  # "확률(%) +1"처럼 읽히지 않게 %를 값에 붙임
                lbl, unit = lbl[:-3], "%"
            fmt1 = lambda x: f"{x:g}"
            per_s = fmt1(per) if per == per_hi else f"{fmt1(per)}~{fmt1(per_hi)}"
            # 99레벨 기준 최대치 병기 (게임은 레벨×증가치를 내림)
            mx99 = int(99 * per)
            mx99_hi = int(99 * per_hi)
            mx_s = f"{mx99}" if mx99 == mx99_hi else f"{mx99}~{mx99_hi}"
            add(f"캐릭터 레벨당 {lbl} +{per_s}{unit} (99레벨 기준 +{mx_s}{unit})", 5)
            return out

        # ── 데미지/방어 계열 ──
        if p == "dmg%":
            add(f"증가된 데미지 {rng(mn,mx,pct=True)}", 141); return out
        if p == "dmg-norm" or p == "dmg":
            add(f"데미지 +{mn}~{mx}" if mn != mx else f"데미지 +{mn}", 126); return out
        if p == "dmg-min":
            add(f"최소 데미지 {rng(mn,mx)}", 125); return out
        if p == "dmg-max":
            add(f"최대 데미지 {rng(mn,mx)}", 124); return out
        if p in ("dmg-fire", "dmg-ltng", "dmg-cold", "dmg-mag", "dmg-pois"):
            el = E[p.split("-")[1]]
            if p == "dmg-pois":
                sec = f" ({(par or 50)//25}초)" if par else ""
                add(f"독 데미지 +{mn}~{mx}{sec}", 120)
            else:
                add(f"{el} 데미지 +{mn}~{mx}" if mn != mx else f"{el} 데미지 +{mn}", 120)
            return out
        if re.fullmatch(r"(fire|ltng|cold|pois)-(min|max|len)", p):
            el, part = p.split("-")
            if part == "len":
                return out  # 지속시간은 min/max 라인에 포함돼 별도 표기 생략
            add(f"{'최소' if part=='min' else '최대'} {E[el]} 데미지 {rng(mn,mx)}", 119)
            return out
        if p == "dmg-elem":
            add(f"원소 데미지 +{mn}~{mx}", 119); return out
        if p == "dmg-ac":
            add(f"명중 시 대상 방어력 -{mx or mn}", 40); return out

        # ── 스킬 계열 ──
        if p in CLASS_EN:  # ama/sor/.../war
            cls_ko = self.skill_names.get("class:" + p, CLASS_EN[p])
            add(f"{cls_ko} 스킬 레벨 {rng(mn,mx)}", 150); return out
        if p == "allskills":
            add(f"모든 스킬 레벨 {rng(mn,mx)}", 155); return out
        if p == "fireskill":
            add(f"화염 스킬 레벨 {rng(mn,mx)}", 149); return out
        if p in ("skilltab", "skilltab-war"):
            t = int(par or 0)
            cls = "war" if p == "skilltab-war" else CLASS_ORDER[t // 3]
            page = (t % 3) + 1
            cls_ko = self.skill_names.get("class:" + cls, cls)
            tree = re.sub(r"\s*스킬$", "", self.tree_names.get((cls, page), f"탭{page}"))
            add(f"{tree} 스킬 레벨 {rng(mn,mx)} ({cls_ko} 전용)", 148); return out
        if p in ("skill", "oskill"):
            nm = self.skill_ko(par)
            suffix = "" if p == "oskill" else self._skill_class_suffix(par)
            add(f"{nm} {rng(mn,mx)}{suffix}", 90); return out
        if p == "skill-rand":
            add(f"무작위 소서리스 스킬 {rng(mn,mx)}", 90); return out
        if p == "randclassskill":
            # properties.txt: val1=3 고정(스킬 레벨 수), min/max는 무작위 클래스 ID 범위
            add("무작위 클래스 스킬 레벨 +3", 150); return out
        if p == "charged":
            add(f"충전됨: 레벨 {mx} {self.skill_ko(par)} ({mn}회 충전)", 10); return out
        if p in ("hit-skill", "att-skill", "gethit-skill", "death-skill",
                 "kill-skill", "levelup-skill"):
            when = {"hit-skill": "적중 시", "att-skill": "공격 시",
                    "gethit-skill": "피격 시", "death-skill": "사망 시",
                    "kill-skill": "적 처치 시", "levelup-skill": "레벨 상승 시"}[p]
            lvl = str(mx)
            if not mx:  # 레벨 0 = 아이템/착용자 레벨 비례 — 게임 DB에 기록된 표시 범위 사용
                key = ((item or {}).get("index", ""), str(par))
                lvl = PROC_LEVEL0_RANGES.get(key, "?")
            add(f"{when} {mn}% 확률로 레벨 {lvl} {self.skill_ko(par)} 시전", 157)
            return out
        if p == "aura":
            add(f"장착 시 레벨 {rng(mn,mx,sign=False)} {self.skill_ko(par)} 오라", 158)
            return out
        if p == "reanimate":
            add(f"{rng(mn,mx,pct=True,sign=False)} 확률로 처치한 적 되살림: {par}", 40)
            return out
        if p == "explosivearrow":
            add(f"폭발 화살/볼트 발사 (레벨 {rng(mn,mx,sign=False)})", 40); return out
        if p == "magicarrow":
            add(f"매직 애로우 발사 (레벨 {rng(mn,mx,sign=False)})", 40); return out

        # ── 저항/능력치 묶음 ──
        if p == "res-all":
            add(f"모든 저항 {rng(mn,mx,pct=True)}", 35); return out
        if p == "res-all-max":
            add(f"모든 최대 저항 {rng(mn,mx,pct=True)}", 35); return out
        if p == "all-stats":
            add(f"모든 능력치 {rng(mn,mx)}", 70); return out

        # ── 소켓/내구/특수 플래그 ──
        if p == "sock":
            add(f"소켓 ({par or mx or mn})", 2); return out
        if p == "indestruct":
            add("파괴되지 않음", 4); return out
        if p == "ethereal":
            add("에테리얼 (복구 불가)", 3); return out
        if p == "knock":
            add("넉백", 40); return out
        if p == "nofreeze":
            add("빙결되지 않음", 30); return out
        if p == "half-freeze":
            add("빙결 지속시간 절반", 30); return out
        if p == "noheal":
            add("몬스터 회복 방지", 41); return out
        if p == "ignore-ac":
            add("대상 방어력 무시", 112); return out
        if p == "reduce-ac":
            add(f"대상 방어력 {rng(mn,mx,pct=True,sign=False)} 감소", 111); return out
        if p == "freeze":
            add(f"적중 시 대상 빙결 +{mx or mn}", 30); return out
        if p == "rip":
            add("시체를 남기지 않고 소멸", 20); return out
        if p == "bloody":
            add("적중 시 출혈", 20); return out
        if p == "stack":
            add(f"최대 보유 수량 {rng(mn,mx)}", 2); return out
        if p == "rep-quant":
            add("수량 자동 보충", 2); return out
        if p in ("magdam-rand", "roguesbow-affix1"):
            return out  # 전용 문자열이 없는 ROTW 특수 플래그 (README 한계 참고)
        if p == "rep-dur":
            per = par or (mx or mn) or 1
            add(f"내구도 자동 수리 (초당 1/{per})" if False else "내구도 자동 수리", 2)
            return out
        if p == "ease":
            v = mn if mn is not None else mx
            add(f"요구 사항 {v}%", 1); return out
        if p == "cheap":
            add(f"판매 가격 감소 {rng(mn,mx,pct=True,sign=False)}", 1); return out
        if p == "addxp":
            add(f"경험치 획득 {rng(mn,mx,pct=True)}", 15); return out
        if p in ("thorns", "light-thorns"):
            el = " 번개" if p == "light-thorns" else ""
            add(f"공격자가{el} 데미지 {rng(mn,mx,sign=False)}를 받음", 25); return out
        if p == "howl":
            add(f"적중 시 몬스터 도주 {rng(mn,mx,pct=True,sign=False)}", 40); return out
        if p == "stupidity":
            add(f"적중 시 대상 실명 +{mx or mn}", 40); return out
        if p == "slow":
            add(f"대상 둔화 {rng(mn,mx,pct=True,sign=False)}", 40); return out
        if p == "pierce":
            add(f"관통 공격 {rng(mn,mx,pct=True)}", 40); return out
        if p == "mana-kill":
            add(f"적 처치 시 마나 {rng(mn,mx)}", 45); return out
        if p == "heal-kill":
            add(f"적 처치 시 생명력 {rng(mn,mx)}", 45); return out
        if p == "demon-heal":
            add(f"악마 처치 시 생명력 {rng(mn,mx)}", 45); return out
        if p == "dmg-to-mana":
            add(f"받은 데미지의 {rng(mn,mx,pct=True,sign=False)}가 마나로 전환", 44)
            return out
        if p in ("att-undead", "dmg-undead", "att-demon", "dmg-demon"):
            tgt = "언데드" if "undead" in p else "악마"
            if p.startswith("att"):
                add(f"{tgt} 상대 공격력 {rng(mn,mx)}", 115)
            else:
                add(f"{tgt}에게 추가 데미지 {rng(mn,mx,pct=True)}", 122)
            return out
        if re.fullmatch(r"extra-(fire|ltng|cold|pois|mag)", p):
            el = E[p.split("-")[1]]
            add(f"{el} 스킬 데미지 {rng(mn,mx,pct=True)}", 145); return out
        if re.fullmatch(r"pierce-(fire|ltng|cold|pois|mag)", p):
            el = E[p.split("-")[1]]
            add(f"적 {el} 저항 -{mx or mn}%", 143); return out
        if p.startswith("pierce-immunity-"):
            el = {"cold": "냉기", "fire": "화염", "light": "번개",
                  "poison": "독", "damage": "물리", "magic": "마법"}[p.rsplit("-", 1)[1]]
            add(f"{el} 면역 관통 {rng(mn,mx,pct=True)}", 142); return out
        if re.fullmatch(r"res-(fire|ltng|cold|pois)-max", p):
            el = E[p.split("-")[1]]
            add(f"최대 {el} 저항 {rng(mn,mx,pct=True)}", 33); return out
        if p == "res-pois-len":
            add(f"중독 지속시간 {rng(mn,mx,pct=True,sign=False)} 감소", 32); return out
        if re.fullmatch(r"abs-(fire|ltng|cold|mag)%?", p):
            el = E[p.replace("%", "").split("-")[1]]
            pct = p.endswith("%")
            add(f"{el} 흡수 {rng(mn,mx,pct=pct)}", 31); return out

        # ── 일반 경로: properties.json → itemstatcost 라벨 ──
        pr = self.props.get(p)
        if not pr:
            self.unknown.add(p)
            return out
        stats = [pr.get(f"stat{i}") for i in range(1, 8) if pr.get(f"stat{i}")]
        if not stats:
            self.unknown.add(p)
            return out
        # 같은 속성의 보조 스탯(min/max 짝 등)은 첫 스탯 라벨로 묶는다
        stat = stats[0]
        lbl, prio = self.label(stat)
        if lbl is None:
            self.unknown.add(p)
            return out
        pct = stat in PERCENT_STATS
        lbl = lbl.strip().rstrip(":")
        if any(ph in lbl for ph in ("%+d", "%d", "%i")):
            # 라벨에 printf 플레이스홀더가 포함된 경우 값을 치환
            val = rng(mn, mx, pct=False, sign="%+d" in lbl)
            lbl = lbl.replace("%+d", val).replace("%d", val).replace("%i", val)
            add(lbl.replace("%%", "%"), prio)
        else:
            add(f"{lbl} {rng(mn,mx,pct=pct)}", prio)
        return out

    def _skill_class_suffix(self, par):
        cls = self.skill_names.get("skillclass:" + str(par))
        return f" ({cls} 전용)" if cls else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d2data", required=True)
    ap.add_argument("--supplement", required=True)
    ap.add_argument("--skills-dir", required=True, help="data/skills (트리명/스킬명 참조)")
    ap.add_argument("--archives", default=None, help="d2archives uniqueAndSetData.json (이미지 매핑)")
    ap.add_argument("--d2r", default=None,
                    help="D2R 재번역 문자열 덤프 — 지정 시 D2R 명칭·라벨이 기본, "
                         "구작(TBL) 명칭은 name_ko_classic으로 병기")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    src = Path(args.d2data)

    def load(name):
        return json.load(open(src / f"{name}.json", encoding="utf-8"))

    d2 = {n: load(n) for n in
          ["uniqueitems", "weapons", "armor", "misc", "itemtypes",
           "itemstatcost", "properties", "skills", "skilldesc"]}
    kor = load("localestrings-kor")
    eng = load("localestrings-eng")
    supp = json.load(open(args.supplement, encoding="utf-8"))
    d2r = {}
    if args.d2r and Path(args.d2r).exists():
        d2r = json.load(open(args.d2r, encoding="utf-8"))

    def ko_classic(key, default=""):
        """구작(TBL) 한국어."""
        if not key:
            return default
        v = kor.get(key, "").strip()
        return strip_color(v) if v else default

    # 키 표기가 다른 경우(Vampiregaze ↔ Vampire Gaze)를 위한 정규화 색인
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
            d = d2r_norm.get(re.sub(r"[^a-z0-9]", "", k.lower()))
            if d:
                return d
        return None

    def ko(key, default=""):
        """D2R 재번역 우선, 없으면 구작 → 보충 파일 순."""
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
        return strip_color(s["en"]) if s and s["en"] else default

    # 스킬명/클래스명/트리명 참조 테이블
    skills_by_key = {v["skill"]: v for v in d2["skills"].values() if v.get("skill")}
    skills_by_id = {str(v["*Id"]): v for v in d2["skills"].values() if "*Id" in v}
    sdesc_by_name = {v["skilldesc"]: v for v in d2["skilldesc"].values() if "skilldesc" in v}
    skill_names = {}
    for key, s in skills_by_key.items():
        d = sdesc_by_name.get(s.get("skilldesc", ""), {})
        nm = ko(d.get("str name", ""), key) or key
        skill_names[key] = nm
        if "*Id" in s:
            skill_names[str(s["*Id"])] = nm
        cc = s.get("charclass")
        if cc:
            skill_names["skillclass:" + key] = ko(CLASS_EN[cc], CLASS_EN[cc])
            if "*Id" in s:
                skill_names["skillclass:" + str(s["*Id"])] = skill_names["skillclass:" + key]
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

    # 베이스 아이템 인덱스
    base = {}
    for kind in ["weapons", "armor", "misc"]:
        for v in d2[kind].values():
            c = v.get("code")
            if c:
                v["_kind"] = {"weapons": "weapon", "armor": "armor", "misc": "misc"}[kind]
                base[c] = v

    types = {v.get("Code"): v for v in d2["itemtypes"].values() if v.get("Code")}

    WCLASS_KO = {
        "axe": "도끼", "swor": "검", "knif": "단검", "spea": "창", "pole": "폴암",
        "mace": "메이스", "hamm": "망치", "club": "곤봉", "scep": "셉터",
        "wand": "완드", "staf": "지팡이", "bow": "활", "xbow": "석궁",
        "jave": "투창", "tkni": "투척 단검", "taxe": "투척 도끼", "orb": "오브",
        "h2h": "클로", "h2h2": "클로", "abow": "아마존 활", "aspe": "아마존 창",
        "ajav": "아마존 투창", "wlbw": "악마술사 무기",
    }
    SLOT_KO = {
        "helm": "투구", "tors": "갑옷", "shie": "방패", "glov": "장갑",
        "boot": "신발", "belt": "벨트", "ring": "반지", "amul": "목걸이",
        "jewl": "주얼", "cm1": "참", "cm2": "참", "cm3": "참",
        "circ": "서클릿", "pelt": "드루이드 투구", "head": "네크로맨서 두개골",
        "ashd": "팔라딘 방패", "phlm": "바바리안 투구", "barb": "바바리안 투구",
        "tiar": "서클릿", "grim": "마도서(그리무아르)",
        "scha": "부적(차암)", "mcha": "부적(차암)", "lcha": "부적(차암)",
        "char": "부적(차암)",
    }

    def tier_of(b):
        c = b.get("code")
        if b.get("ultracode") == c:
            return "elite"
        if b.get("ubercode") == c:
            return "exceptional"
        return "normal"

    rend = Renderer(d2, ko, en, tree_names, skill_names)
    arch = {}
    if args.archives and Path(args.archives).exists():
        a = json.load(open(args.archives, encoding="utf-8"))
        for nm, v in a["content"]["uniqueItems"].items():
            key = re.sub(r"[^a-z0-9]", "", nm.lower())
            arch[key] = v
            arch[re.sub(r"^the", "", key)] = v

    items = []
    seen_slugs = {}
    for v in d2["uniqueitems"].values():
        idx, code = v.get("index"), v.get("code")
        if not idx or not code or not v.get("spawnable"):
            continue
        if idx in QUEST_INDEXES or idx.startswith("PreCrafted"):
            continue
        b = base.get(code)
        if not b:
            continue
        name_en = en(idx, idx)
        dr = d2r_get(idx, name_en)
        name_ko = strip_color(dr["ko"]) if dr else ko_classic(idx, name_en) or name_en
        name_ko_classic = ko_classic(idx)
        if name_ko_classic == name_ko:
            name_ko_classic = ""

        # 레인보우 패싯: 동명 8종을 원소·발동 조건으로 구분
        if idx == "Rainbow Facet":
            elem = trigger = ""
            for i in range(1, 13):
                pp = v.get(f"prop{i}") or ""
                m = re.fullmatch(r"pierce-(fire|ltng|cold|pois)", pp)
                if m:
                    elem = ELEM_KO[m.group(1)]
                if pp == "death-skill":
                    trigger = "사망 시"
                if pp == "levelup-skill":
                    trigger = "레벨 상승 시"
            if elem or trigger:
                name_ko = f"{name_ko} ({elem}·{trigger})"
                name_en = f"{name_en} ({elem} {trigger})"
                if name_ko_classic:
                    name_ko_classic = f"{name_ko_classic} ({elem}·{trigger})"

        lines = []
        for i in range(1, 13):
            p = v.get(f"prop{i}")
            if not p or p.startswith("*"):
                continue
            lines += rend.render(p, v.get(f"par{i}"), v.get(f"min{i}"),
                                 v.get(f"max{i}"), v)
        lines.sort(key=lambda t: -t[0])

        tcode = b.get("type", "")
        kind = b["_kind"]
        t = types.get(tcode, {})
        if kind == "weapon":
            cat_ko = WCLASS_KO.get(tcode, t.get("ItemType", "무기"))
        elif kind == "armor":
            cat_ko = SLOT_KO.get(tcode, t.get("ItemType", "방어구"))
        else:
            cat_ko = SLOT_KO.get(tcode, t.get("ItemType", "기타"))

        slug = slugify(name_en)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 1

        base_ko = ko(code, code)
        base_ko_classic = ko_classic(code)
        entry = {
            "id": slug,
            "name_en": name_en,
            "name_ko": name_ko,
            **({"name_ko_classic": name_ko_classic} if name_ko_classic else {}),
            "base": {"code": code, "name_en": en(code, code), "name_ko": base_ko,
                     **({"name_ko_classic": base_ko_classic}
                        if base_ko_classic and base_ko_classic != base_ko else {})},
            "kind": kind,
            "category_ko": cat_ko,
            "tier": tier_of(b),
            "item_level": v.get("lvl"),
            "required_level": v.get("lvl req", 0),
            "required_strength": b.get("reqstr") or None,
            "required_dexterity": b.get("reqdex") or None,
            "props_ko": [t for _, t in lines],
        }
        if kind == "weapon":
            dmg = {}
            if b.get("mindam") is not None:
                dmg["one_hand"] = [b.get("mindam"), b.get("maxdam")]
            if b.get("2handmindam") is not None:
                dmg["two_hand"] = [b.get("2handmindam"), b.get("2handmaxdam")]
            if dmg:
                entry["base_damage"] = dmg
        if kind == "armor" and b.get("minac") is not None:
            entry["base_defense"] = [b.get("minac"), b.get("maxac")]

        if idx in IMAGE_OVERRIDES:
            entry["image_src"] = IMAGE_OVERRIDES[idx]
        else:
            k1 = re.sub(r"[^a-z0-9]", "", en(idx, idx).lower())
            k2 = re.sub(r"[^a-z0-9]", "", idx.lower())
            a = (arch.get(k1) or arch.get(k2) or
                 arch.get(re.sub(r"^the", "", k1)) or arch.get(re.sub(r"^the", "", k2)))
            if a:
                entry["image_src"] = a.get("image", "").replace("/images/Items/", "")
        items.append(entry)

    items.sort(key=lambda e: (e["kind"], e["category_ko"], e["required_level"]))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"count": len(items), "items": items},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(items)} uniques -> {args.out}")
    print("unknown props:", sorted(rend.unknown))
    noimg = [e["name_en"] for e in items if "image_src" not in e]
    print(f"no image: {len(noimg)}", noimg[:25])


if __name__ == "__main__":
    main()
