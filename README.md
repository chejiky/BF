# BF — 디아블로 2 레저렉션 정보 앱

디아블로 2 레저렉션(D2R)의 게임 정보를 모아 보여주는 앱 프로젝트입니다. (인벤 스타일)

## 진행 단계

- [x] **1단계: 클래스별 스킬 데이터 + 아이콘** ← 현재
- [ ] 2단계: 아이템(유니크/세트/룬워드) 데이터
- [ ] 3단계: 프론트엔드 (스킬 트리 뷰어)

## 1단계 결과물

### `data/skills/` — 클래스별 스킬 데이터 (JSON)

8개 클래스 × 30개 스킬 = 총 240개. `index.json`이 클래스 목록을 담고 있습니다.

| 파일 | 클래스 |
|---|---|
| `amazon.json` | 아마존 |
| `assassin.json` | 어쎄신 |
| `barbarian.json` | 바바리안 |
| `druid.json` | 드루이드 |
| `necromancer.json` | 네크로맨서 |
| `paladin.json` | 팔라딘 |
| `sorceress.json` | 소서리스 |
| `warlock.json` | 악마술사 (확장팩 "악마술사의 군림") |

스킬 명칭과 설명은 **게임 클라이언트의 공식 한국어/영어 문자열**을 그대로 사용합니다.

스킬 엔트리 예시:

```json
{
  "id": "frozen-orb",
  "name_en": "Frozen Orb",
  "name_ko": "프로즌 오브",
  "tree": { "page": 3, "name_en": "Cold Spells", "name_ko": "콜드 스펠" },
  "position": { "row": 6, "col": 1 },
  "required_level": 30,
  "max_level": 20,
  "mana_cost": 50,
  "element": "cold",
  "prerequisites": [{ "id": "blizzard", "name_ko": "블리자드", "...": "..." }],
  "synergies": [{ "id": "ice-bolt", "name_ko": "아이스 볼트", "...": "..." }],
  "description_ko": "구형으로 발사되는 강한 아이스 볼트를 사방에 퍼뜨려 ..."
}
```

- `tree.page`: 게임 UI의 스킬 탭 순서(1~3), `position`: 트리 내 행(1~6)/열(1~3)
- `prerequisites`: 선행 스킬, `synergies`: 시너지 스킬 (게임 데미지 수식에서 추출)

### `assets/skills/` — 스킬 아이콘 (96×96 PNG)

`assets/skills/<class>/<skill_id>.png` 형태로 스킬당 1장, 총 210장.
데이터의 `id` 필드와 파일명이 일치하므로 바로 매핑됩니다.

> ⚠️ 아이콘과 게임 데이터의 저작권은 Blizzard Entertainment에 있으며,
> 비상업적 팬 콘텐츠 범위에서만 사용합니다. 자세한 내용은 [NOTICE.md](NOTICE.md) 참고.

## 데이터 재생성 방법

```bash
# 1) 게임 데이터 (npm 패키지) 받기
npm pack @blizzhackers/d2data && tar xzf blizzhackers-d2data-*.tgz

# 2) 스킬 JSON 생성
python3 scripts/build_skills.py --d2data ./package/json --out ./data/skills

# 3) 아이콘 추출 (d2planner 저장소 필요, 기존 7클래스)
git clone --depth 1 https://github.com/d2planner/d2planner /tmp/d2planner
python3 scripts/extract_icons.py \
    --images /tmp/d2planner/d2planner/src/assets/1.14D/game_images \
    --data ./data/skills --out ./assets/skills

# 4) 악마술사(워록): d2data 로케일에 아직 없는 문자열은 보충 파일로,
#    아이콘은 D2R .sprite 시트에서 추출
#    (보충 문자열 원본: D2R 게임 데이터의 strings/skills.json·ui.json —
#     https://github.com/D2R-Reimagined/d2r-reimagined-mod 에 포함된 사본 사용)
python3 scripts/build_skills.py --d2data ./package/json --out ./data/skills \
    --supplement ./data/raw/warlock-strings.json
python3 scripts/extract_sprite_icons.py \
    --sprite <...>/data/hd/global/ui/spells/warlock/waskillicon.sprite \
    --data ./data/skills/warlock.json --out ./assets/skills/warlock
```
