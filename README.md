# map3d-korea

**🔴 [라이브 데모 열기](https://urbantraverse.github.io/map3d-korea/)** — 클론 없이 브라우저에서 바로 3D 뷰 확인 가능

> **한국 공공 데이터로 구축하는 도시 3D 모델 파이프라인**
> 아이디어 출처: [cartesiancs/map3d](https://github.com/cartesiancs/map3d) (Hyeong Jun Huh, MIT License) — "실제 도시를 3D 박스로 보여준다"는 발상만 가져왔고, 코드·데이터·기술스택은 전부 별개로 새로 작성함 (§10 크레딧 참조)
> 차이점: OSM이 부실한 한국 도시를 *건축물대장 + VWorld*로 우회

---

## 1. 무엇

임의의 시·군·구·동에서 **3D 박스 도시 모델**을 자동 생성한다.
각 박스는 *실제 건물 footprint*에 *건축물대장 속성*(층수·사용승인·구조·다가구·반지하 등)을
얹은 데이터로 채워진다.

산출물 형태: 인터랙티브 HTML, GeoJSON, 정적 figure (모두 G-Drive 동기화 가능).

## 2. 왜

map3d 원본은 OpenStreetMap 기반인데, 한국은 OSM이 부실하다.
서울 도심 일부를 빼면 *건물 폴리곤조차 없는* 동이 대부분.

반면 이 프로젝트는 다음 자원을 활용한다:
- **buildhub API** (국토부 건축HUB 건축물대장) — 모든 건물의 78필드 속성
- **VWorld API** (국토부 공간정보 오픈플랫폼) — 건물 footprint 폴리곤 (`LT_C_SPBD`)
- **KOSIS·SGIS·datago·법령·KCI 등** 15+ 공공 API 키

이 자원들을 *map3d의 렌더링 패턴*과 결합하면 *지방 중소도시의 정밀한 3D 진단*이 가능하다.

## 3. 파일럿

### 3.1 마산합포구 문화동 (첫 파일럿)

[**📂 pilots/munhwa-dong/**](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong)

| 결과 | 값 |
|---|---|
| 매칭률 (v2) | 199 / 242 = **82.2%** |
| 노후도 (1990 이전) | 76% |
| 단독주택 비중 | 87% |
| 반지하 보유 | 13% |
| 유형 분류 | C형 (단독·다가구 노후형) |

핵심 시각화: [**`munhwa_3d_v2.html` 열기**](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/munhwa_3d_v2.html)
재현 가능성 노트: [`REPORT.md`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/REPORT.md)

범용 파이프라인(2026-07-09 확장) 재현판 `munhwa_v3`도 같은 폴더에 있다 — 매칭 228건(94.2%).
v2 이후 추가된 도로명 2차매칭이 29건을 더 잡아서 v2보다 많다(코드 변경 아님, 재현 시점 차이).
[`munhwa_v3_3d.html` 열기](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/munhwa_v3_3d.html)

### 3.2 마산합포구 대창동 (두 번째 파일럿, 2026-07-09)

[**📂 pilots/daechang-dong/**](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/daechang-dong)

`--dong` 지오코딩 → 확인된 코드(sigungu=48125, bjdong=10900)로 생성한 단일 동 결과:

| 결과 | 값 |
|---|---|
| 매칭률 | 176 / 181 = **97.2%** |
| 노후도 (1990 이전) | 34.7% |
| 단독주택 비중 | 89.2% |
| 반지하 보유 | 14.2% |

핵심 시각화: [**`daechang_3d.html` 열기**](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/daechang-dong/daechang_3d.html)

문화동보다 노후도가 훨씬 낮다(34.7% vs 76%) — 같은 마산합포구 안에서도 동별 노후도 편차가 크다.

## 4. 폴더 구조

```
map3d-korea/
├── README.md               # 이 문서 (프로젝트 소개)
├── SESSION_LOG.md          # 2026-05-27 셋업 세션 흐름 기록
├── pipeline.py             # buildhub × VWorld 조인 파이프라인 (--dong/--mode bbox/--html 지원)
├── template_3d.html        # 3D 시각화 HTML 템플릿 (--html 옵션이 채워 넣음)
├── server.py               # 로컬 미니 서버 (브라우저 폼으로 pipeline 호출)
├── briefs/                 # 확장 브리프 + 결과 노트
└── pilots/                 # 동별 파일럿 결과
    ├── munhwa-dong/        # 마산합포구 문화동 (첫 파일럿)
    │   ├── buildhub_munhwa.jsonl      # v2 표제부 전수 242건 (78필드)
    │   ├── munhwa_joined_v2.geojson   # v2 PNU 조인 통합 199건 (고유 PNU 193, 원본 보존)
    │   ├── munhwa_3d_v2.html          # v2 인터랙티브 3D 박스 (deck.gl)
    │   ├── REPORT.md                  # 기술 노트 (재현 가능성)
    │   ├── munhwa_v3_joined.geojson   # 범용 파이프라인 재현판 228건 (도로명 매칭 포함)
    │   ├── munhwa_v3_3d.html          # v3 인터랙티브 3D
    │   └── _legacy/                   # v1 산출물 보관 (참고용, 사용 금지)
    └── daechang-dong/      # 마산합포구 대창동 (두 번째 파일럿, 2026-07-09)
        ├── buildhub_daechang.jsonl    # 표제부 전수 181건 (--mode code, sigungu=48125/bjdong=10900)
        ├── vworld_daechang.json       # VWorld LT_C_SPBD 캐시 (377건)
        ├── daechang_joined.geojson    # PNU 조인 통합 176건 (97.2%)
        └── daechang_3d.html           # 인터랙티브 3D 박스
```

## 5. 핵심 기술 자산 — PNU 조인 규칙

두 데이터셋의 *건물 식별자*가 체계가 다르다:

| 출처 | 식별자 | 길이 | 의미 |
|---|---|---|---|
| buildhub | `mgmBldrgstPk` | 15 | 건축물대장 PK |
| VWorld `LT_C_SPBD` | `bd_mgt_sn` | 25 | 도로명주소법 건물고유번호 |

직접 매칭 불가. 대안으로 *지번 PNU 19자리* 합성:

```python
# buildhub PNU 합성 — 11번째 자리 강제 '1' (인코딩 차이 보정)
def buildhub_pnu(it):
    return (it['sigunguCd'].zfill(5) + it['bjdongCd'].zfill(5) +
            '1' +
            it['bun'].zfill(4) + it['ji'].zfill(4))

# VWorld는 bd_mgt_sn[:19] 그대로
vworld_pnu = feat['properties']['bd_mgt_sn'][:19]
```

⚠️ 함정: buildhub `platGbCd=0`(대지) ↔ VWorld bd_mgt_sn[10]=`1` — *같은 의미를 다르게 표기*.
**11번째 자리를 `1`로 통일하는 한 줄이 이 프로젝트의 핵심 자산.**

자세한 발견 경위는 [`SESSION_LOG.md`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/SESSION_LOG.md) §3.1 참조.

## 6. 새 동에 적용하는 절차

가장 간단한 경로 — **동 이름 하나로 끝** (2026-07-09부터, `--dong`/`--mode bbox`/`--html` 지원):

```bash
python3 pipeline.py \
  --dong "경상남도 창원시 마산합포구 대창동" \
  --mode bbox \
  --out pilots/daechang-dong --tag daechang \
  --html --title "대창동 3D"
```

내부적으로 (1) VWorld 지오코딩으로 좌표 획득 → (2) `--bbox-radius`(기본 0.011, 약 5~6km²)로
BBOX 자동 산출 → (3) BBOX 안 건물의 `bd_mgt_sn`으로 (sigungu, bjdong) 조합을 전수 역추적
(`--min-count` 미만은 노이즈로 제외) → (4) 발견된 동을 모두 buildhub 조인.

⚠️ **구도심처럼 법정동이 촘촘한 지역은 `--mode bbox`가 목표 동 하나가 아니라 인접 동 수십 개를
함께 끌어온다.** 마산합포구 실측: 대창동 지오코딩 후 기본 반경(약 4.9km²) 안에서 **36개**
(sigungu,bjdong) 조합이 한꺼번에 발견됨 (전부 buildhub 조인 대상이 됨). 특정 동 하나만
깔끔하게 원하면 코드를 먼저 확인한 뒤 `--mode code`(기본값)로 좁혀서 쓴다:

```bash
# sigungu/bjdong을 이미 알고 있으면 --mode code(기본값)로 좁혀서
python3 pipeline.py \
  --sigungu 48125 --bjdong 10900 \
  --bbox 128.543120,35.174288,128.565120,35.196288 \
  --out pilots/daechang-dong --tag daechang --html
```

BBOX 면적은 소스(수동 지정/`--dong` 지오코딩)에 관계없이 **10km² 초과 시 자동 에러**
(`bbox_area_km2()`가 매 실행마다 검사). 위경도 차이로 면적을 직접 환산하려면:
`(maxx-minx) × cos(위도°) × 111` × `(maxy-miny) × 111` (km).

산출: `{out}/buildhub_{tag}.jsonl`(또는 `--mode bbox`는 `{out}/buildhub_{sigungu}_{bjdong}.jsonl`
동별로 여러 개), `{out}/vworld_{tag}.json`(캐시), `{out}/{tag}_joined.geojson`(최종 통합),
`--html` 지정 시 `{out}/{tag}_3d.html`(3D 시각화, 템플릿을 수동 복제할 필요 없음).

행정동 1개당 약 10~15분 (네트워크 대기 포함, `--mode bbox`로 다수 동을 한 번에 묶으면 더 길다).
일일 트래픽 한도: data.go.kr 활용신청별 1,000건/일, VWorld 키별 별도.

⚠️ **현재 PNU 규칙은 대지(`platGbCd=0/1`)만 가정**. 산(山)지 필지(`platGbCd=2`)가
많은 동은 별도 분기 필요.

## 7. 의존 인프라

이 프로젝트는 다음에 의존하지만 *위치 자체가 의미*라서 이 폴더로 옮기지 않음:

| 자원 | 위치 | 역할 |
|---|---|---|
| 마스터 `.env` | `/Users/dw/G-Drive2T/Research_tools/.env` | 모든 API 키 SSOT |
| MCP 서버들 | `Research_tools/KOSIS_Vworld/{datago,vworld,kosis}-mcp/` | Cowork·Claude Desktop에서 dotenv 자동 로드 |
| 셸 환경 | `~/.zshrc`에 마스터 .env source 한 줄 | Claude Code·터미널 Python 자동 인식 |
| 글로벌 지침 | `~/.claude/CLAUDE.md` + Cowork `memory/CLAUDE.md` | 미래 세션이 마스터 .env 인식 |

이 인프라 셋업 *전체 과정*은 [`SESSION_LOG.md`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/SESSION_LOG.md) §2 참조.

## 8. 다음 단계 후보

- ~~인접 동 확장~~ → `--dong`/`--mode bbox`/`--html`로 완료 (2026-07-09). 대창동 1차 검증 완료
  (§3.2). 신월동·월영동 등 추가 동은 같은 방식으로 한 줄 호출 가능 — 단 구도심 지역은
  `--bbox-radius` 축소 또는 `--mode code` 권장 (§9 한계 참조)
- **buildhub 6유형 클러스터링** 결과를 색상에 통합
  (이미 `buildhub-physical-analyzer` 스킬에 알고리즘 존재) — 대창동은 아직 미분류
- **KOSIS 인구·가구 결합** — 동 단위 *물리상태 × 거주특성*
- **도시재생 정책 매칭** — datago의 정비구역·재생활성화지역 GeoJSON 오버레이
- **Obsidian 노트화** — `20_Projects/map3d-korea/` 생성, STATUS·DECISIONS 분리

## 9. 한계

| 한계 | 우회 |
|---|---|
| VWorld BBOX 한도 10km² | 큰 행정동은 분할 호출 |
| 1:N 페어링 정확도 | 현재는 연면적 정렬. *동명 매칭* 또는 *공간 가까움*으로 강화 가능 |
| VWorld DB의 footprint 누락 | 부속건물 일부 미등록 — 매칭률 100% 도달 불가 |
| 일일 트래픽 1,000건/일 | 큰 시군구는 며칠에 나눠 수집 |
| `--mode bbox`가 구도심에서 동 수 폭증 | 마산합포구 실측 36개 동 동시 발견 (§6). 단일 동만 필요하면 코드 확인 후 `--mode code` |
| `--mode bbox` 다중 동 집계 시 HTML 중심 편차 | 무게중심이 전체 피처 기준이라 피처 많은 동에 쏠림 (실측 약 0.5km) — 목표 동 중심이 필요하면 `--mode code`로 좁힐 것 |
| `run_by_bbox()`의 buildhub·VWorld 비대칭 | buildhub는 발견된 법정동 전체, VWorld는 BBOX로만 클립 — 동을 많이 묶을수록 match_rate가 구조적으로 낮아짐 (단일 동 매칭률과 직접 비교 금지) |

## 10. 크레딧

이 프로젝트의 계기는 [**cartesiancs/map3d**](https://github.com/cartesiancs/map3d) (제작: [Hyeong Jun Huh](https://github.com/DipokalLab), MIT License)를 접한 것이었다 — "실제 건물을 3D 박스로 세워서 보여준다"는 발상 자체가 출발점.

**가져온 것**: 3D 박스 시각화라는 아이디어, 그리고 "건물 데이터 + 지도 렌더링을 결합한다"는 구조적 접근.

**독립적으로 새로 만든 것** (원본과 코드 공유 없음):

| | cartesiancs/map3d | map3d-korea |
|---|---|---|
| 데이터 출처 | OpenStreetMap | 건축HUB(buildhub, 국토부) + VWorld(국토부 공간정보) |
| 프런트엔드 | React + React-Three-Fiber + Vite/TypeScript | 순수 JS + deck.gl + MapLibre GL |
| 백엔드/파이프라인 | (해당 없음, 클라이언트 단독) | Python(`pipeline.py`) + Flask(`server.py`) |
| 핵심 로직 | OSM 태그 → 3D 압출 | buildhub-VWorld **PNU 조인**(§5) → 3D 압출 |

원본은 MIT 라이선스라 코드를 그대로 가져다 써도 법적으로 문제는 없지만, 실제로는 **공유 코드가 한 줄도 없다** — 완전히 다른 기술스택으로 한국 공공데이터에 맞춰 처음부터 새로 짰다. 그래도 발상의 출처를 숨기는 건 온당치 않다고 판단해 이 섹션과 README 상단에 명시해 둔다.

---

*시작: 2026-05-27*
*현재 파일럿: 2 (마산합포구 문화동·대창동) · pipeline.py 범용화 2026-07-09 (`briefs/2026-05-27_pipeline-generalization_result.md` 참조)*
