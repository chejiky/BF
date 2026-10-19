# 작업 인계 노트 (다음 Claude 세션용)

## 사용자와 목표
- 디아블로 2 레저렉션(D2R) 정보 앱을 **아이폰 홈 화면 앱**으로 만드는 개인 프로젝트 ("인벤 같은 앱").
- 사용자는 비개발자, 아이폰으로 작업. 한국어. **단계별 + 링크 포함 + 캡처 기준 안내**를 선호하고,
  모르는 부분은 중간에 물어보며 진행하길 원함. 전날 같은 방식으로 뱀파이어 서바이벌즈 앱을 만듦
  (저장소 chejiky/BF2, Netlify sunny-bonbon-a3dc1f).

## 배포 현황 (완료)
- 저장소: **chejiky/BF** (private). 작업 브랜치 `claude/d2r-skill-data` = `main` (동일 커밋 유지 중)
- **Netlify 프로젝트 `yuiga-d2` → https://yuiga-d2.netlify.app** (Public 설정 완료, main 자동 배포)
  - `netlify.toml`: publish = `docs`, 빌드 명령 없음
  - 사용자의 Netlify GitHub 앱 권한에 BF 추가 완료
- 미리보기용 아티팩트: https://claude.ai/artifact/1q74pRfhMQTV1NfdJW4vkd (비공개, Safari에서는 claude.ai 로그인 필요)
- 아이폰: Safari로 Netlify 주소 열기 → 공유 → 홈 화면에 추가 (아이콘: 금색 링 "D2R", 이름 "D2R 사전")

## 수정 → 배포 루틴
1. 데이터 스크립트 또는 `app/template.html` 수정
2. `python3 scripts/build_pwa.py`  (내부에서 build_app 실행 → app/index.html, docs/ 재생성)
3. 커밋 후 `git push origin claude/d2r-skill-data` 그리고 `git push origin claude/d2r-skill-data:main`
   → Netlify 자동 재배포 (1~2분). 아이폰 앱은 닫았다 열면 새 버전 (서비스워커 캐시 버전 자동 갱신)
4. (선택) 아티팩트도 갱신: Artifact publish `app/index.html` + url 위 주소. 아티팩트는 파일 511개 한도 —
   이미지 이미 올라가 있음, 새 이미지 생길 때만 files로 추가.
- 검증: scratchpad에 `npm install playwright`, chromium은 `/opt/pw-browsers/chromium`,
  node http 서버로 docs/ 서빙 후 390x844 뷰포트로 스크린샷/오프라인 테스트.

## 앱 구성 (app/template.html, 단일 HTML + 해시 라우팅)
- 홈: 8클래스 카드, 유니크(무기/방어구/장신구), 세트/룬워드/부적/큐브 카드, **통합 검색**(신·구 명칭, 공백 무시)
- 라우트: `c-<class>` 스킬트리, `s-<class>-<id>` 스킬상세, `u-<weapon|armor|misc>`, `i-<id>`,
  `sets`, `set-<id>`, `ti-<id>`(세트아이템), `rw`, `r-<id>`, `charms`, `ca-<scha|mcha|lcha>`, `cube`,
  `auras`(오라 사전: 성기사 오라 20종 1→20레벨 수치 요약 + "장착 시 오라" 아이템 칩, 데이터는 런타임에 paladin.json·아이템 props에서 추출)
- 스킬 상세: **레벨 슬라이더 1~20**(인게임 툴팁 문구), **정량 시너지**("얼음살: 레벨당 냉기 피해 +2%"),
  **시너지 계산기**(스킬별 −/＋ 스테퍼 0~20, 모두 20/초기화, 수치 줄에 "기본 ▶ 강화" 표시.
  synMode()가 시너지 스탯→툴팁 줄 매핑: 원소 피해는 mult, +% 줄은 add,
  "피해"는 공격력 줄 우선·없으면 원소/흡수 줄 fallback — 볼케이노 vs 허리케인 케이스)
- 목록 필터: 유니크(검색+분류칩+등급칩), 세트(검색), 룬워드(검색+소켓칩+베이스칩),
  큐브(검색+카테고리칩+영문토글, 구작 별칭 검색). 필터 상태는 메모리(listState)에 유지
- 디자인: 다크 단일 테마(금색 포인트), 스킬 아이콘은 클래스별 스프라이트 시트 사용

## 데이터 (모두 저장소에 생성물 커밋됨)
| 파일 | 내용 |
|---|---|
| data/skills/<class>.json (8) + index.json | 240스킬: 한/영/구작명, 트리, 위치, 요구Lv, 선행, 시너지, 설명, `tooltip`(per_level/static/synergies) |
| data/items/uniques.json | 유니크 391 (퀘스트템·PreCrafted 제외), props_ko, image_src, 등급/분류 |
| data/items/sets.json | 35세트 130아이템, 아이템별 N개 착용 보너스, 부분/풀 보너스 |
| data/items/runewords.json | 활성 룬워드 99, 룬(한/영), 소켓, 베이스, 요구Lv |
| data/items/charms.json | 기본 부적 3종, 유니크 부적 id, 분쇄 부적 6원소(잠복형→제작형) |
| data/items/charm_affixes.json | 부적 크기별 접두/접미 전체 티어 292종 + 스킬러 클래스별 요약 |
| data/items/cube_recipes.json | 큐브 레시피 157 (10카테고리), aliases_ko(구작명) |
| data/raw/d2r-strings.json | **D2R 재번역 문자열**(en/ko) — 앱 기본 명칭 |
| data/raw/warlock-strings.json, items-strings.json | d2data에 없는 ROTW 문자열 보충 |

명칭 원칙: **D2R 정식 번역이 기본**(바람살, 얼음 보주, 원소술사), 구작 TBL 명칭은 `*_classic` 필드로 병기(윈드포스, 프로즌 오브, 소서리스).

## 원본 소스 (세션 컨테이너는 임시라 재작업 시 다시 받아야 함)
- 게임 데이터: `npm pack @blizzhackers/d2data` → package/json/*.json (skills, skilldesc, localestrings-kor/eng,
  uniqueitems, setitems, sets, runes, magicprefix/suffix, cubemain, missiles, properties, itemstatcost, itemtypes, weapons/armor/misc)
- D2R 한국어 문자열 + 워록 아이콘 스프라이트: github **D2R-Reimagined/d2r-reimagined-mod**
  (data/local/lng/strings/*.json — UTF-8 BOM, `utf-8-sig`로 읽기; data/hd/global/ui/spells/warlock/waskillicon.sprite)
  - **주의**: 모드의 워록 한국어는 구버전 팬 번역이 섞여 있음. Summon Trickster(키 SummonDefiler)는
    모드 koKR "악마 말썽꾼 소환"이지만 **실제 게임은 "파멸자 소환"** — warlock-strings.json에 교정해 둠
    (재추출 시 덮어쓰지 말 것). 나머지 29개 스킬명·트리명(악마/기괴/혼돈)은 인벤·나무위키 대조로 일치 확인(2026-10-14).
    웹 검색 도구(WebSearch)는 인벤·나무위키 내용을 읽을 수 있음(직접 fetch는 차단).
- 클래식 스킬 아이콘: github **d2planner/d2planner** (src/assets/1.14D/game_images/<class>_tree_N.jpg, GPL-3)
- 아이템·룬 이미지: github **bartosz-kasprzyk/d2archives** (src/images/items, src/images/Runes, src/common/config/uniqueAndSetData.json)
- 네트워크: npm, GitHub(add_repo로 공개 저장소 clone)는 됨. namu.wiki, fandom 등 대부분 웹사이트는 차단.

## 스크립트 (scripts/) 실행 순서
1. build_skills.py `--d2data <json> --out data/skills --supplement data/raw/warlock-strings.json --d2r data/raw/d2r-strings.json`
2. build_skill_tooltips.py `--d2data <json> --d2r ... --supplement data/raw/warlock-strings.json --skills-dir data/skills` (skills JSON을 제자리 수정 — 반드시 1 다음)
3. 아이콘: extract_icons.py(클래식 트리 이미지 크롭), extract_sprite_icons.py(SpA1 .sprite 파서), build_skill_sheets.py(6×5 시트)
4. build_uniques.py `--d2data --supplement data/raw/items-strings.json --skills-dir data/skills --archives <d2archives json> --d2r ... --out data/items/uniques.json`
5. build_sets_runes.py / build_charm_affixes.py / build_cube.py — build_uniques의 Renderer를 import하므로
   **scripts/ 폴더에서 `python3`(‑I 없이)** 실행
6. build_pwa.py (build_app 포함) → docs/

## 데이터 함정 (이미 처리됨, 재작업 시 주의)
- skilldesc SkillPage와 SkillCategory 번호가 역순 (워록만 정방향)
- 구작 TBL 한국어 여러 줄 문자열은 줄 순서가 역순(fix_lines), skillxld 비면 skillld로 대체
- 포이즌 크리퍼 문자열 포인터가 워울프를 가리킴 → strUI8로 예외 처리
- 문자열의 색코드 `ÿc?`, 티어 첨자 `¹²³`, 장식 `*` 제거 (strip_color)
- 레인보우 패싯 8종 변형 이름 구분, d2archives 이미지 오매핑 보정(Windforce, Gimmershred, Hellfire Torch)
- 툴팁 수식: 약 10% 줄 생략(암살자 차지업 m1en/macr 등 미지원 변수). 시너지/숙련 투자는 0 기준
- 미렌더 속성 2개: magdam-rand(오팔맥), roguesbow-affix1(피어스립)
- 속성 인코딩 함정 (2026-10-14 교정): proc(hit/att/gethit-skill)의 max=0은 레벨 비례 —
  7개 아이템은 build_uniques.py의 PROC_LEVEL0_RANGES에 D2R DB 확인값 하드코딩(라이트세이버 14~20 등).
  sock·레벨당(/lvl) 속성은 값이 par에 있기도 min/max에 있기도 함(인내 hp/lvl은 min8 max12 범위).
  randclassskill은 properties.txt val1=3 고정(+3), min/max는 클래스 ID 범위.
- 워로드의 영광 세트 5부위는 이미지 없음

## 저작권 안내 (사용자에게 설명한 입장)
- 이미지·명칭·설명은 블리자드 저작물. 비상업적 팬 프로젝트로 사용(NOTICE.md).
- 광고/유료화 금지, SNS·커뮤니티에 주소 퍼뜨리지 않기, 삭제 요청 시 즉시 내리기.

## 다음 후보 (사용자에게 제안했던 것)
- ~~시너지 투자 레벨 입력 → 최종 피해 계산기~~ (완료, 2026-10-14)
- 레어/매직 접사 전체 사전, 보석·룬 단일 효과표
- 스킬트리 연결선이 라벨 글자를 가리는 사소한 시각 문제
