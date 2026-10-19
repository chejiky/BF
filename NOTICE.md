# 저작권 및 출처 고지 (NOTICE)

이 저장소는 **비상업적 팬 프로젝트**입니다.

## Diablo® II 게임 자산

- 스킬 명칭, 설명, 게임 수치 등 게임 데이터와 `assets/skills/` 하위의 스킬 아이콘
  이미지의 저작권은 **Blizzard Entertainment, Inc.** 에 있습니다.
- Diablo®, Diablo® II: Resurrected™는 Blizzard Entertainment, Inc.의 상표 또는
  등록 상표입니다.
- 이 프로젝트는 Blizzard Entertainment와 무관한 비공식 팬 프로젝트이며, 게임 자산은
  Blizzard의 팬 콘텐츠 관련 정책이 허용하는 **비상업적** 범위 내에서만 사용합니다.
  상업적으로 이용하려는 경우 반드시 별도의 법률 검토가 필요합니다.
  (참고: https://www.blizzard.com/en-us/legal)

## 데이터 출처

- `data/skills/*.json`은 [@blizzhackers/d2data](https://www.npmjs.com/package/@blizzhackers/d2data)
  npm 패키지가 제공하는 게임 데이터 파일(skills / skilldesc / 로케일 문자열)을
  `scripts/build_skills.py`로 가공해 생성했습니다. 한국어/영어 명칭과 설명은 게임
  클라이언트의 공식 로컬라이제이션 문자열을 그대로 사용합니다.

## 악마술사(Warlock) 데이터 출처

- 확장팩 "악마술사의 군림"의 스킬 명칭·설명(`data/raw/warlock-strings.json`)은
  아직 d2data 로케일에 반영되지 않아, [D2R-Reimagined](https://github.com/D2R-Reimagined/d2r-reimagined-mod)
  저장소에 포함된 게임 원본 문자열 파일(`data/local/lng/strings/`)에서 추출했습니다.
  해당 텍스트의 저작권 역시 Blizzard Entertainment에 있습니다.
- `assets/skills/warlock/` 아이콘은 같은 저장소에 포함된 게임 원본 스프라이트
  (`waskillicon.sprite`)에서 `scripts/extract_sprite_icons.py`로 추출했습니다.

## 유니크 아이템 이미지 출처

- `assets/items/`의 아이템 이미지는 [d2archives](https://github.com/bartosz-kasprzyk/d2archives)
  저장소의 이미지 자산을 사용했으며(이름→이미지 매핑 포함), 아트워크의 저작권은
  Blizzard Entertainment에 있습니다.

## 아이콘 이미지 출처

- `assets/skills/` 하위 스킬 아이콘은 D2R 게임 원본 스프라이트
  (`<class>skillicon.sprite`, [D2R-Reimagined](https://github.com/D2R-Reimagined/d2r-reimagined-mod)
  저장소에 포함)에서 `scripts/extract_sprite_icons.py`로 추출했습니다.
  아트워크의 저작권은 Blizzard Entertainment에 있습니다.
- 초기 버전은 GPL-3.0으로 공개된 [d2planner](https://github.com/d2planner/d2planner)
  저장소의 1.14D 스킬 트리 이미지를 `scripts/extract_icons.py`로 잘라내 사용했습니다
  (현재는 D2R 원본 아이콘으로 교체됨).

- `assets/auras/` 오라 이펙트 사진은 실제 게임 화면 캡처(사용자 제공)에서 잘라낸 것입니다.
  아트워크의 저작권은 Blizzard Entertainment에 있습니다.

## 요청 시 삭제

권리자(Blizzard Entertainment)의 요청이 있을 경우 해당 자산은 즉시 삭제합니다.
