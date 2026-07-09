# 결과 노트: pipeline.py 범용화 3종 세트

> 브리프: `2026-05-27_pipeline-generalization.md`
> 실행: Claude Code · 2026-07-09 (승인 후 §5·§6 후속 반영 포함)
> 대상 파일: `pipeline.py`(683줄, 기존 563줄에서 확장) · `template_3d.html`(1줄) · `README.md`(§3·4·6·8·9 갱신)
> 신규 저장: `pilots/daechang-dong/`(신설) · `pilots/munhwa-dong/`(v3 재현물 비파괴적 추가)

---

## 0. 구현 전 실측으로 발견한 간극

브리프의 구현 힌트 코드를 그대로 옮기지 않고, 실행해서 검증한 뒤 두 곳을 수정했다.

1. **`bbox_area_km2()`는 "기존 함수"가 아니라 존재하지 않는 함수였다.** `pipeline.py`·`server.py`·`README.md` 전체를 grep했으나 정의가 없다 (server.py의 `/api/geocode`에 동일한 면적 계산식이 인라인으로만 있었다). 브리프가 이미 있다고 가정한 걸 신규로 작성했다 — server.py의 공식(`dx*111*cos(lat)` × `dy*111`)을 그대로 함수화했다.
2. **HTML 힌트의 무게중심 계산 코드는 액면 그대로 두면 크래시한다.** 실제로 문화동 데이터로 1차 실행했을 때 `TypeError: unsupported operand type(s) for +: 'int' and 'list'`가 났다. 원인 조사 결과 VWorld `LT_C_SPBD`의 geometry는 **전부 MultiPolygon**이었다 (문화동 228건 전수 확인). 즉 `coordinates[0][0]`은 좌표 하나가 아니라 **외곽 링 전체**(좌표 리스트)이므로, 링에서 좌표 하나를 더 꺼내려면 `coordinates[0][0][0]`까지 파고들어야 한다. 브리프 힌트의 `for c in coords[:1]` 패턴은 사실 이 3단 구조를 겨냥한 (다소 우회적이지만) 올바른 코드였다 — 내가 처음에 "정리"하며 Polygon 2단 인덱싱으로 단순화한 게 오히려 버그였다. 최종적으로 `ring = coordinates[0][0]; c = ring[0]` 형태로 고쳐 해결했다 (`pipeline.py:596-607`).
3. **`template_3d.html`에 `{{ZOOM}}` 자리가 없었다.** 브리프는 `--zoom` CLI 옵션을 요구했지만 템플릿 힌트의 플레이스홀더 목록(§A)에도, 실제 템플릿에도 zoom 자리가 없이 `zoom: 16.5`가 하드코딩돼 있었다. `{{ZOOM}}`을 신설해 연결했다 (`template_3d.html:75`).

---

## 1. 확장된 pipeline.py의 새 인터페이스 요약

### 신규/변경 함수
| 함수 | 위치 | 역할 |
|---|---|---|
| `bbox_area_km2(bbox)` | `pipeline.py:554` | BBOX 근사 면적(km²), 위도 보정 |
| `geocode_dong(dong)` | `pipeline.py:563` | VWorld Geocoder, ROAD 실패 시 PARCEL 재시도 |
| `write_html(...)` | `pipeline.py:586` | GeoJSON + summary → `template_3d.html` 채워 저장 |

### CLI 변경
`--sigungu`/`--bjdong`/`--bbox`는 `required=True`를 뗐고, 파싱 후 별도 검증으로 옮겼다. 신규 플래그:

```
--dong "경상남도 창원시 마산합포구 대창동"   # 지오코딩으로 BBOX 자동 산출
--bbox-radius 0.011                            # --dong 사용 시 반경 (기본, 약 6km²)
--mode {code,bbox}                             # 기본 code (기존 run()) · bbox = run_by_bbox()
--min-count 5                                  # bbox 모드 노이즈 컷오프
--html                                         # 3D HTML도 같이 생성
--title "..."                                  # HTML 제목 (기본: --tag)
--zoom 16.5                                    # HTML 초기 줌
```

검증 우선순위: `--bbox`가 있으면 `--dong`은 무시(지오코딩 호출 자체를 안 함) — 실측으로 확인(§3 하단 참조). BBOX는 소스(수동/지오코딩)에 관계없이 **항상** 10km² 검사를 통과해야 하도록 했다 — 브리프 §B는 "산출된 BBOX"(지오코딩 유래)만 언급했지만, VWorld 쪽 한도는 소스와 무관한 하드 리밋이라 수동 `--bbox`에도 동일하게 적용하는 게 안전하다고 판단했다.

### 통합 CLI 예시 (실제로 이 문서 §2·§3에서 실행 검증됨)
```bash
# 문화동 재현
python3 pipeline.py --sigungu 48125 --bjdong 11500 \
  --bbox 128.5479,35.1751,128.5699,35.2031 \
  --out <out> --tag munhwa --html

# 대창동 신규 (동 이름 하나로)
python3 pipeline.py --dong "경상남도 창원시 마산합포구 대창동" \
  --mode bbox --out <out> --tag daechang \
  --html --title "대창동 3D 파일럿"
```

README §6 갱신 초안은 §5에 있다.

---

## 2. 문화동 재현 검증 결과

```bash
python3 pipeline.py \
  --sigungu 48125 --bjdong 11500 \
  --bbox 128.5479,35.1751,128.5699,35.2031 \
  --out /tmp/munhwa_test --tag munhwa --html
```

**출력**: `/tmp/munhwa_test/munhwa_joined.geojson`, `/tmp/munhwa_test/munhwa_3d.html` (둘 다 생성 확인, HTML 플레이스홀더 잔존 0건)

```json
{
  "buildhub_total": 242, "vworld_total": 397,
  "matched_features": 228, "matched_pnu": 214,
  "matched_via_pnu": 199, "matched_via_road": 29,
  "paired_by_name": 1, "unmatched_vw": 169,
  "match_rate": 0.942, "out": ".../munhwa_joined.geojson"
}
```

| 기준 (브리프) | 기대 | 실제 | 판정 |
|---|---|---|---|
| features 수 | 199 (±5) | **228** | ⚠️ 아래 참조 |
| match_rate | ≥ 0.80 | **0.942** | ✅ |
| HTML 생성 | 생성됨 | 생성됨, 플레이스홀더 전부 치환 | ✅ |

**228 vs 199 차이의 원인**: `matched_via_pnu` 필드가 정확히 **199**로 나온다 — 브리프가 기준으로 삼은 기존 `munhwa_joined_v2.geojson`(mtime 2026-05-27 12:36)과 정확히 일치한다. 그런데 현재 `pipeline.py`(내가 손대기 전 원본 mtime 2026-05-27 14:29)에는 이미 **도로명 2차 매칭**(`buildhub_road_key`/`vworld_road_key`, `join_by_pnu()` 2차 fallback)이 들어 있고, 이게 29건을 추가로 잡는다. v2 필럿 산출물이 얼려진(12:36) *이후* pipeline.py가 갱신(14:29)됐는데 필럿 파일은 재생성되지 않은 것으로 보인다 — **내가 이번에 추가한 로직이 아니라 기존 코드가 이미 갖고 있던 기능**이고, 브리프의 회귀 기준선(199)이 그 갱신 이전 스냅샷인 셈이다. `match_rate`가 0.80 기준을 여유 있게 넘기므로 재현 자체는 통과로 판단했다.

기존 `pilots/munhwa-dong/` 원본은 건드리지 않았다 (md5·mtime 검증 완료, 2026-05-27 그대로).

---

## 3. 대창동 신규 시험 결과

```bash
python3 pipeline.py \
  --dong "경상남도 창원시 마산합포구 대창동" \
  --mode bbox --out /tmp/daechang_test --tag daechang \
  --html --title "대창동 3D 파일럿"
```

| 기준 (브리프) | 기대 | 실제 | 판정 |
|---|---|---|---|
| geocode 성공 | 성공 | 성공 (ROAD 타입, 1차 시도) → (128.554120, 35.185288) | ✅ |
| BBOX 자동 산출 | 약 6km² | 4.87km² (반경 0.011, 10km² 이내) | ✅ |
| (sigungu, bjdong) 자동 발견 | (48125, 10900) | 발견됨 (VWorld raw 377건) | ✅ |
| buildhub 수집 | 181건 | **181건** (대창동 단독, `buildhub_48125_10900.jsonl` 181줄) | ✅ 정확히 일치 |
| 매칭 features | ≥ 80건 | **176건** (대창동 단독, pnu 접두 10900 기준 집계) | ✅ |
| HTML 생성, 대창동이 지도 중심 | 중심에 나타남 | 생성됨. 중심 (128.559492, 35.186299) — 지오코딩 원점 대비 약 0.5km 편차 | ⚠️ 아래 참조 |

**"181건"·"≥80건" 기준은 정확히 재현됐다** — 브리프가 "지난 세션 검증됨"이라 적어둔 수치와 완전히 일치해 별도 세션의 사전 확인이 정확했음을 확인했다.

**단, 이 값들은 "대창동 단독" 기준이고, 실제 `--mode bbox` 출력물은 대창동만이 아니다.** `discover_codes_from_bbox()`가 반경 0.011(≈4.87km²) 안에서 `min_count=5` 필터를 적용한 결과, **36개**의 (sigungu, bjdong) 조합이 함께 발견됐다 (전부 sigungu=48125, 마산합포구 관내). 이는 브리프 §C가 설계한 그대로의 동작(BBOX 안 전수 발견 → 전부 조인)이라 버그는 아니지만, §검증절차의 "기대"란은 마치 대창동 하나만 나오는 것처럼 서술돼 있어 브리프 자체 내부에 서술 불일치가 있다. 최종 aggregate 결과:

```json
{
  "buildhub_total": 6870, "vworld_total": 7515,
  "matched_features": 4555, "matched_via_pnu": 4169, "matched_via_road": 386,
  "unmatched_vw": 2960, "match_rate": 0.663,
  "out": ".../daechang_joined.geojson"
}
```

HTML의 지도 중심도 이 36개 동 전체 피처의 근사 무게중심이라, 대창동 단독 좌표에서 약 0.5km 벗어난다(대창동 자체는 여전히 화면 안에 들어오지만 정중앙은 아니다). 자세한 내용과 대응 방법은 §4-4·§4-5 참조.

---

## 4. 발견한 함정

1. **`bbox_area_km2()`는 실존하지 않았다** — 브리프가 "기존" 함수로 언급했으나 신규 작성 (§0-1).
2. **HTML 무게중심 힌트 코드는 액면 그대로면 크래시** — MultiPolygon 3단 인덱싱 필요 (§0-2).
3. **문화동 199건 기준선이 낡았다** — 도로명 2차 매칭이 이미 pipeline.py에 들어간 뒤 필럿 산출물을 재생성 안 해서 생긴 차이. 코드 문제 아님 (§2).
4. **`--mode bbox` 기본 반경(0.011, ~6km²)이 구도심에서는 "동 하나"가 아니라 "동 30개 이상"을 쓸어담는다.** 마산합포구 구도심처럼 법정동이 촘촘히 나뉜 지역 특성 — 브리프 §C 설계 자체가 "BBOX 안 전수"이므로 의도된 동작이지만, "대창동만 깔끔하게 뽑고 싶다"는 실사용 목적과는 어긋날 수 있다. **대응**: 이번에 확인된 코드로 `--sigungu 48125 --bjdong 10900 --mode code`(기본값)를 쓰거나, `--bbox-radius`를 0.004~0.005 수준으로 크게 줄인다.
5. **다중 동 집계 시 HTML 중심좌표가 목표 동에서 벗어난다** — 무게중심이 전체 피처 기준이라, 피처 수가 많은 동(예: 13400, 2024건)이 잡아당긴다. 목표 동을 지도 중심에 정확히 두고 싶으면 `--mode code`로 좁혀 실행하는 걸 권장.
6. **(기존 코드 특성, 이번 변경과 무관)** `run_by_bbox()`는 VWorld는 BBOX로 잘라오지만 buildhub는 발견된 법정동 "전체"를 가져온다 — 동 하나가 BBOX 밖으로 넓게 걸쳐 있으면 그만큼 미매칭이 늘어 `match_rate`가 낮아진다(이번 대창동 aggregate 0.663 vs 문화동 단일 동 0.942). 여러 동을 한 번에 처리할수록 낮은 match_rate가 "품질 저하"가 아니라 "구조적으로 그런 것"임을 염두에 둬야 한다.

---

## 5. README.md 갱신 — 적용 완료 (2026-07-09 후속)

최초 보고 시점에는 초안만 제시하고 README.md는 건드리지 않았으나, "직접 판단해서
전체적으로 개선해도 된다"는 승인을 받아 아래를 전부 실제로 반영했다.

- **§3 파일럿**: "첫 파일럿 — 문화동" 단수 구조를 §3.1(문화동)·§3.2(대창동) 2개 하위섹션으로 재구성.
  대창동 통계(노후도 34.7%·단독주택 89.2%·반지하 14.2%)는 `daechang_joined.geojson`에서 직접
  집계 — buildhub 6유형 클러스터링(C형 등)은 이번 범위 밖이라 대창동엔 유형 라벨을 붙이지 않았다.
- **§4 폴더 구조**: `template_3d.html`·`server.py`·`briefs/` 추가, `pilots/munhwa-dong`에 v3 파일,
  `pilots/daechang-dong` 신설 반영 (파일명은 실제 생성된 이름으로 — 아래 정정 참조).
- **§6 새 동에 적용하는 절차**: 전면 교체 (동 이름 우선 + 구도심 함정 경고 + `--mode code` 대안).
- **§8 다음 단계 후보**: "인접 동 확장" 완료 표시, §9 참조 추가.
- **§9 한계**: 새 함정 3행 추가 (동 수 폭증·HTML 중심 편차·buildhub/VWorld 비대칭).
- 하단 "현재 파일럿" 카운트 1 → 2.

**초안 대비 정정**: 초안엔 `pilots/daechang-dong/buildhub_48125_10900.jsonl`이라 적었으나, 실제
`--mode code`(`run()`)는 `buildhub_{tag}.jsonl` 명명 규칙을 쓴다 (sigungu_bjdong 명명은
`--mode bbox`의 `run_by_bbox()`가 발견한 동마다 캐시를 나눌 때만 쓰는 규칙). 실제 파일명은
`buildhub_daechang.jsonl` — README에도 이 이름으로 정정해 반영했다.

`pipeline.py` 모듈 docstring의 "사용:" 예시도 `--dong`/`--html` 예시를 포함하도록 갱신했다
(`pipeline.py:6-14`).

## 6. 저장 결정 — 적용 완료

두 가지 미결 사항을 직접 판단해 처리했다:

1. **대창동 저장 형태**: "36개 동 통합본" 대신 **대창동 단독본**을 정식 채택했다. 근거 — 폴더 이름이
   `daechang-dong`인데 내용물이 마산합포구 절반이면 오해의 소지가 크고, 문화동 파일럿과 비교 가능한
   "동 단위" 단위로 맞추는 게 이 프로젝트의 §1 목적("임의의 동에서 3D 박스 모델")에 부합한다.
   `--mode code --sigungu 48125 --bjdong 10900`으로 재실행해 `pilots/daechang-dong/`에 저장
   (매칭 176/181 = 97.2%, §3.2 참조). 36개 동 통합본은 이미 이 결과 노트(§3)에 수치로 전부
   기록돼 있고 언제든 재현 가능해 별도 보존하지 않았다(`/tmp/daechang_test/`는 휘발성 스크래치).
2. **문화동 v3 재현물 저장**: 브리프 §"통합된 CLI 예시"가 애초에 `munhwa_v3` 태그로
   `pilots/munhwa-dong/`에 저장하는 예시를 들고 있었던 걸 근거로, `/tmp/munhwa_test/`의 캐시를
   그대로 복사해(API 재호출 없이) `munhwa_v3_joined.geojson`·`munhwa_v3_3d.html`을 생성,
   기존 v2 파일 옆에 비파괴적으로 추가했다. v2 원본은 md5 재확인으로 무결성 유지 확인.

---

## 다음 단계 (참고용 — 블로킹 아님)

- `--mode bbox` 기본 반경(0.011)을 지역 특성별로 가이드를 나눌지는 아직 미정 — 필요해지면 논의
- 대창동에 buildhub 6유형 클러스터링(유형 라벨) 적용 여부는 §8에 후보로만 남겨둠
- `pilots/daechang-dong/`은 이제 문화동과 동급의 "정식 파일럿"이 됐으므로, 향후 3번째 동 확장 시
  이 두 폴더를 템플릿처럼 참조 가능
