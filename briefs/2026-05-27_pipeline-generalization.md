# Brief: pipeline.py 범용화 3종 세트

> 요청자: 프로젝트 작성자 (Cowork 세션에서 설계)
> 대상: Claude Code
> 날짜: 2026-05-27
> 목적: 문화동에 특화된 파이프라인·시각화를 *임의 동에 한 줄로 적용 가능*하게 확장

---

## 배경 맥락

`Research_tools/map3d-korea/`는 buildhub × VWorld를 조인해 임의 행정동의 3D 박스 도시 모델을 만드는 파이프라인이다. 첫 파일럿(마산합포구 문화동)은 완료 상태. 이제 *다른 동에 한 줄 명령으로 확장*할 수 있게 하고 싶다.

현 상태:
- ✅ `pipeline.py` — buildhub·VWorld 수집·PNU 조인·GeoJSON 생성 완료. `run()`과 `run_by_bbox()` 두 함수가 코드에 있으나 CLI는 `run()`만 노출.
- ✅ `pilots/munhwa-dong/munhwa_3d_v2.html` — 문화동 특화 HTML (deck.gl). GeoJSON 데이터·중심 좌표가 하드코딩됨.
- ✅ `template_3d.html` — 방금 생성한 범용 템플릿. `{{TITLE}}`, `{{DATA_JSON}}`, `{{CENTER_LNG}}`, `{{CENTER_LAT}}`, `{{RATE}}`, `{{TOTAL}}`, `{{BH_TOTAL}}`, `{{ERA_DIST}}`, `{{BASEMENT}}`, `{{MULTI}}` 플레이스홀더 포함.

---

## 확장 3종

### A. HTML 자동 생성 (`--html` 옵션)

**목적**: GeoJSON만 만들지 말고 시각화 HTML까지 한 번에.

**CLI 인터페이스**:
```
--html                     # 플래그. 있으면 HTML도 생성
--title "대창동 3D"        # HTML 제목 (선택, 기본은 tag)
--zoom 16.5                # 초기 줌 (선택, 기본 16.5)
```

**동작**:
1. `template_3d.html`을 읽음
2. 통계 계산 (총 features 수, 매칭률, era 분포 문자열, 반지하 수, multi_pair 수)
3. GeoJSON JSON 문자열로 임베드
4. 중심 좌표는 GeoJSON features의 무게중심 (없으면 BBOX 중심)
5. `{out}/{tag}_3d.html`에 저장

**치환할 placeholders** (템플릿에 이미 정의됨):
- `{{TITLE}}` — --title 값 또는 tag
- `{{DATA_JSON}}` — `json.dumps(geojson, ensure_ascii=False)`
- `{{CENTER_LNG}}`, `{{CENTER_LAT}}` — features 무게중심 또는 BBOX 중심
- `{{RATE}}` — `"82.3%"` 형식
- `{{TOTAL}}` — 매칭 features 수
- `{{BH_TOTAL}}` — buildhub 전체 수
- `{{ERA_DIST}}` — `"1970s:60 · 1980s:56 · 1990s:35 · 2000+:16 · 미상:32"` 형식
- `{{BASEMENT}}` — `ugrndFlr >= 1` 개수
- `{{MULTI}}` — `multi_pair == True` 개수

### B. BBOX 자동 산출 (`--dong` 옵션)

**목적**: 매번 BBOX 좌표 계산하지 말고 동 이름만 주면 자동.

**CLI 인터페이스**:
```
--dong "경상남도 창원시 마산합포구 대창동"    # 한글 주소
--bbox-radius 0.011                              # 위경도 반경 (선택, 기본 0.011 → 약 6km²)
```

**동작**:
1. VWorld Geocoder API로 --dong 문자열 → (x, y) 좌표 획득
2. BBOX = (x-r, y-r, x+r, y+r) 자동 산출 (r = --bbox-radius, 기본 0.011)
3. 산출된 BBOX가 10km² 초과하면 에러 (기존 `bbox_area_km2()` 활용)
4. --bbox와 --dong 동시 지정 시 --bbox 우선 (명시적 우선)

**VWorld Geocoder 호출 예시**:
```python
url = "https://api.vworld.kr/req/address"
params = {
    "service": "address", "request": "getcoord",
    "crs": "epsg:4326", "address": args.dong,
    "type": "ROAD", "key": VWORLD, "format": "json"
}
r = requests.get(url, params=params).json()
result = r["response"]["result"]["point"]
x, y = float(result["x"]), float(result["y"])
```

주소가 ROAD 타입으로 실패하면 PARCEL(지번)으로 재시도.

### C. `--mode bbox` — 동 코드 자동 역추적

**목적**: BBOX만 주면 그 안의 (sigungu, bjdong)을 자동으로 발견하고 전수 처리.

**CLI 인터페이스**:
```
--mode {code, bbox}         # 기본 'code' (기존 방식)
--min-count 5               # bbox 모드에서 노이즈 임계 (기본 5)
```

**동작**:
- `code` 모드 (기본): 기존 `run()` 함수. `--sigungu`, `--bjdong` 필수.
- `bbox` 모드: 기존 `run_by_bbox()` 함수. `--bbox` 또는 `--dong` 필수. `--sigungu`, `--bjdong` 무시.

**Bbox 모드 흐름**:
1. VWorld BBOX 안 건물 전수 → `bd_mgt_sn` 앞 10자리로 (sigungu, bjdong) 분포 집계
2. `min_count` 이상인 (sigungu, bjdong) 조합만 buildhub 호출
3. 각 (sigungu, bjdong)의 buildhub 결과를 PNU 조인
4. 통합 GeoJSON 생성

---

## 통합된 CLI 예시 (완성 후)

```bash
# 가장 간단 — 동 이름 하나로 끝
python3 pipeline.py \
  --dong "경상남도 창원시 마산합포구 대창동" \
  --mode bbox \
  --out pilots/daechang-dong --tag daechang \
  --html --title "대창동 (마산합포구) 3D"

# 명시적 — 코드 + BBOX 지정
python3 pipeline.py \
  --sigungu 48125 --bjdong 10900 \
  --bbox 128.550,35.180,128.575,35.195 \
  --out pilots/daechang-dong --tag daechang \
  --html

# 문화동 재현 (기존 파일 덮어쓰지 않게 tag 다르게)
python3 pipeline.py \
  --sigungu 48125 --bjdong 11500 \
  --bbox 128.5479,35.1751,128.5699,35.2031 \
  --out pilots/munhwa-dong --tag munhwa_v3 \
  --html --title "문화동 v3 (범용 파이프라인 재현)"
```

---

## 구현 힌트

### CLI argparse 설계

```python
# 기존 required=True를 재검토
# --dong이 있으면 --bbox 선택적, --sigungu/--bjdong도 선택적
# 검증은 파싱 후 별도

ap.add_argument("--sigungu")   # required=False 로
ap.add_argument("--bjdong")    # required=False 로
ap.add_argument("--bbox", type=_parse_bbox)  # required=False 로
ap.add_argument("--dong")       # 새로
ap.add_argument("--bbox-radius", type=float, default=0.011)  # 새로
ap.add_argument("--mode", choices=["code", "bbox"], default="code")  # 새로
ap.add_argument("--html", action="store_true")  # 새로
ap.add_argument("--title")      # 새로
ap.add_argument("--zoom", type=float, default=16.5)  # 새로
ap.add_argument("--min-count", type=int, default=5)  # 새로 (bbox 모드용)

# 파싱 후 검증
if args.dong and not args.bbox:
    x, y = geocode_dong(args.dong)
    r = args.bbox_radius
    args.bbox = (x-r, y-r, x+r, y+r)
if args.mode == "code" and (not args.sigungu or not args.bjdong or not args.bbox):
    ap.error("code 모드는 --sigungu, --bjdong, --bbox (또는 --dong) 필수")
if args.mode == "bbox" and not args.bbox:
    ap.error("bbox 모드는 --bbox (또는 --dong) 필수")
```

### HTML 생성 함수

```python
def write_html(geojson_path: Path, summary: dict, out_dir: Path, tag: str,
               title: str, bbox: tuple, zoom: float = 16.5) -> Path:
    template_path = Path(__file__).parent / "template_3d.html"
    template = template_path.read_text(encoding="utf-8")

    with geojson_path.open() as f:
        geojson = json.load(f)

    # 중심 좌표 (feature 무게중심 or BBOX 중심)
    if geojson["features"]:
        lngs, lats = [], []
        for f in geojson["features"]:
            coords = f["geometry"]["coordinates"][0][0]  # 외곽 링 첫 좌표들
            for c in coords[:1]:  # 첫 좌표만
                lngs.append(c[0])
                lats.append(c[1])
        center_lng = sum(lngs) / len(lngs)
        center_lat = sum(lats) / len(lats)
    else:
        center_lng = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2

    # 통계
    features = geojson["features"]
    total = len(features)
    bh_total = summary.get("buildhub_total", 0)
    rate = f"{total/max(bh_total,1):.1%}"

    from collections import Counter
    era_counts = Counter(f["properties"]["era"] for f in features)
    era_dist = " · ".join(f"{k}:{v}" for k, v in sorted(era_counts.items()))
    basement = sum(1 for f in features if (f["properties"].get("ugrndFlr") or 0) >= 1)
    multi = sum(1 for f in features if f["properties"].get("multi_pair"))

    html = (template
        .replace("{{TITLE}}", title)
        .replace("{{DATA_JSON}}", json.dumps(geojson, ensure_ascii=False))
        .replace("{{CENTER_LNG}}", f"{center_lng:.6f}")
        .replace("{{CENTER_LAT}}", f"{center_lat:.6f}")
        .replace("{{RATE}}", rate)
        .replace("{{TOTAL}}", str(total))
        .replace("{{BH_TOTAL}}", str(bh_total))
        .replace("{{ERA_DIST}}", era_dist)
        .replace("{{BASEMENT}}", str(basement))
        .replace("{{MULTI}}", str(multi))
    )
    out_path = out_dir / f"{tag}_3d.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

### VWorld Geocode 함수

```python
def geocode_dong(dong: str) -> tuple[float, float]:
    """VWorld Geocoder로 한글 주소를 (x, y) 좌표로 변환. ROAD → PARCEL 재시도."""
    url = "https://api.vworld.kr/req/address"
    for addr_type in ("ROAD", "PARCEL"):
        r = requests.get(url, params={
            "service": "address", "request": "getcoord",
            "crs": "epsg:4326", "address": dong,
            "type": addr_type, "key": VWORLD, "format": "json"
        }, timeout=REQUEST_TIMEOUT)
        try:
            result = r.json()["response"]["result"]["point"]
            return float(result["x"]), float(result["y"])
        except (KeyError, TypeError):
            continue
    raise RuntimeError(f"VWorld geocode 실패: {dong}")
```

---

## 검증 절차 (Definition of Done)

### 1. 문화동 재현 (regression test)

기존 결과와 매칭률·건수가 동일해야 함.

```bash
python3 pipeline.py \
  --sigungu 48125 --bjdong 11500 \
  --bbox 128.5479,35.1751,128.5699,35.2031 \
  --out /tmp/munhwa_test --tag munhwa \
  --html
```

기대:
- `/tmp/munhwa_test/munhwa_joined.geojson` 생성. features 수 199 (± 5 오차 허용, 기존 v2 파이프라인의 도로명 fallback로 조금 더 많을 수 있음)
- `/tmp/munhwa_test/munhwa_3d.html` 생성. 브라우저 열면 3D 박스 표시.
- summary 출력의 `match_rate` ≥ 0.80

### 2. 대창동 신규 적용

한 번도 처리 안 한 동을 --dong으로.

```bash
python3 pipeline.py \
  --dong "경상남도 창원시 마산합포구 대창동" \
  --mode bbox \
  --out /tmp/daechang_test --tag daechang \
  --html --title "대창동 3D 파일럿"
```

기대:
- geocode 성공, BBOX 자동 산출 (약 6km²)
- (sigungu=48125, bjdong=10900) 자동 발견
- buildhub 181건 수집 (지난 세션 검증됨)
- 매칭 features ≥ 80건
- HTML 생성 후 대창동 위치가 지도 중심에 나타남

### 3. 결과 노트 저장

작업 완료 후 `map3d-korea/briefs/2026-05-27_pipeline-generalization_result.md`에:
- 각 검증 결과 (features 수, 매칭률)
- 발견한 함정
- 확인이 필요한 다음 단계

---

## 참고 파일

- `map3d-korea/pipeline.py` — 확장 대상
- `map3d-korea/template_3d.html` — HTML 템플릿 (플레이스홀더 정의됨)
- `map3d-korea/README.md` — 프로젝트 개요 (§6에 새 동 절차 이미 서술 — 완성 후 갱신 필요)
- `map3d-korea/SESSION_LOG.md` — 배경 (§3.1 PNU 조인 규칙 참조)
- `map3d-korea/pilots/munhwa-dong/` — 기존 문화동 결과 (덮어쓰지 말 것)

## 주의사항

- **문화동 기존 결과 덮어쓰지 말 것**. 검증은 `/tmp/`에.
- **마스터 .env 위치는 절대경로 유지**: `/Users/dw/G-Drive2T/Research_tools/.env`
- **VWorld domain 파라미터는 `"localhost"` 유지** (기존 코드 관례)
- **CLAUDE.md 원칙**: 원본 백업, 한 번에 한 가지만 변경, 대량 파일 작업 전 계획 승인. 이 확장은 pipeline.py *한 파일 확장* + HTML 생성 함수 추가이므로 안전 범위.

---

## 완료 후 보고 항목

1. 확장된 pipeline.py의 새 인터페이스 요약 (README §6 갱신 초안 포함)
2. 문화동 재현 검증 결과
3. 대창동 신규 시험 결과
4. 발견한 함정 (있으면)
5. README.md §6·§4·§8을 어떻게 갱신할지 초안

*작성: Cowork 세션에서 설계 · Code에 실행 위임*
