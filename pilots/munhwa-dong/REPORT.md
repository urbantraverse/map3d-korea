# 마산합포구 문화동 3D 파일럿 — 기술 노트

> 2026-05-27
> buildhub × VWorld PNU 조인으로 임의 행정동의 3D 박스 모델 생성 검증

## 1. 목적

임의 시·군·구·동에서 *건축물대장 속성*과 *공간 footprint*를 결합한
3D 박스 시각화 파이프라인이 한국 데이터 환경에서 작동하는지 검증한다.

검증 대상: 창원시 마산합포구 문화동(행정동, 법정동코드 11500).

## 2. 데이터 소스

| 소스 | 엔드포인트 | 단위 | 키 |
|---|---|---|---|
| 건축물대장 표제부 | `apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo` | 1동(棟) | `DATAGO_API_KEY` (data.go.kr 활용신청) |
| VWorld 건물 폴리곤 | `api.vworld.kr/req/data` data=`LT_C_SPBD` | 1동(棟) | `VWORLD_API_KEY` |

키는 마스터 `.env` (`/Users/dw/G-Drive2T/Research_tools/.env`)에서 로드.

## 3. 조인 키 규칙 (핵심 발견)

두 데이터셋 모두 *건물 단위 식별자*가 있으나 **체계가 다르다**:

- buildhub `mgmBldrgstPk` (15자리) — 건축물대장 내부 PK
- VWorld `bd_mgt_sn` (25자리) — 도로명주소법상 건물고유번호

**둘은 직접 매칭 불가**. 대안으로 *지번 PNU 19자리* 합성 매칭이 작동한다.

```python
# buildhub PNU 합성 (11번째 자리 강제 1)
def buildhub_pnu(it):
    sig = it['sigunguCd'].zfill(5)   # 5
    bjd = it['bjdongCd'].zfill(5)    # 5
    bun = it['bun'].zfill(4)         # 4
    ji  = it['ji'].zfill(4)          # 4
    return f"{sig}{bjd}1{bun}{ji}"   # 11번째 = 1 고정

# VWorld는 bd_mgt_sn 앞 19자리 그대로
vworld_pnu = bd_mgt_sn[:19]
```

⚠️ **인코딩 차이 주의**: buildhub `platGbCd=0`(대지) ↔ VWorld 11번째 자리=`1`.
**같은 의미를 다르게 표기**. PNU 합성 시 11번째 자리를 `1`로 통일하면 매칭.

## 4. 파이프라인 (재현 단계)

```
[행정동 좌표 확보]            VWorld geocode("경상남도 ... ○○동")
        ↓
[법정동코드 식별]             VWorld LT_C_SPBD 호출 → gu='○○동' 필터링
                              → bd_mgt_sn 첫 10자리 분포 → 산하 법정동 추출
        ↓
[buildhub 표제부 전수]        getBrTitleInfo (sigunguCd, bjdongCd, page=1~)
                              ※ totalCount 확인 후 페이지 루프
        ↓
[VWorld footprint 전수]       LT_C_SPBD (geomFilter=BOX, size=200, page=1~)
                              ※ BBOX 최대 10km² 한도 (그 이상은 분할 호출 필요)
                              ※ bd_mgt_sn 앞 10자리로 해당 법정동만 필터
        ↓
[PNU 조인]                    bh_pnu ↔ vw_pnu 교집합 (set 연산)
                              1:N 페어링은 totArea 정렬로 매칭
        ↓
[속성 인코딩]                 사용승인일 → 시기 카테고리
                              층수 × 3m → height_m
                              ugrndFlrCnt ≥ 1 → 반지하 플래그
        ↓
[GeoJSON 저장 + 3D 렌더]      deck.gl PolygonLayer extruded
                              MapLibre GL 베이스맵 (CARTO Positron)
```

## 5. 매칭률 비교 (문화동 사례)

| 버전 | BBOX | VWorld 11500 PNU | 매칭 PNU (고유) | 매칭 건물 (1:N 페어 포함) | 매칭률 (buildhub 242 기준) |
|---|---|---|---|---|---|
| v1 | 4.5km² (좁음) | 261 | 130 | 130 | **53.7%** |
| v2 | 6.5km² (확장) | 239* | 193 | 199 | **82.2%** |

\* v2의 11500 PNU 397개 중 buildhub와 교집합 193 (중복 제거 후).
v2에서 같은 PNU에 buildhub 여러 동·VWorld 여러 동이 1:N 페어링되어 *건물 수*가 PNU 수보다 6건 많다.

**v2 도달한 비결:**
1. BBOX 확장 (10km² 한도 내까지)
2. 1:N 페어링 (한 PNU에 buildhub 여러 건 ↔ VWorld 여러 건, 연면적 정렬)

미매칭 buildhub **43건** (242 - 199)의 추정 원인:
- VWorld DB의 부속건물 폴리곤 누락
- 갱신 지연
- BBOX 경계 잘림 (10km² 한도로 인해)

## 6. 산출물

```
munhwa-dong/
├── buildhub_munhwa.jsonl          # buildhub 표제부 전수 (242건, 78필드)
├── munhwa_joined.geojson          # v1 통합 GeoJSON (130건)
├── munhwa_joined_v2.geojson       # v2 통합 GeoJSON (199건, 권장)
├── munhwa_3d.html                 # v1 시각화
├── munhwa_3d_v2.html              # v2 시각화 (권장)
└── REPORT.md                      # 이 문서
```

## 7. 발견 — 문화동의 도시 패턴 (참고)

매칭된 199건 분포:

| 시기 | 건수 | 비율 |
|---|---|---|
| 1970s | 60 | 30% |
| 1980s | 56 | 28% |
| 1990s | 35 | 18% |
| 2000+ | 16 | 8% |
| 미상 | 32 | 16% |

- 1990년 이전 = **76%**
- 단독주택 비중 87%, 1-2층 90%
- 반지하 보유 13%
- 다가구(fmlyCnt≥2) 6건 — 분산형 임대 구조 *없음*
- 본번 14에 104건 집중 (조밀한 단독 클러스터)

→ 유형 분류: **C형 (단독·다가구 노후형)** — 마산 구도심 전형

## 8. 한계

1. **BBOX 한도 10km²**: 큰 행정동은 분할 호출 필요
2. **PNU 11번째 자리 인코딩 차이**: 두 데이터셋 표준이 다름 (이 문서가 우회 규칙 제시)
3. **1:N 페어링의 약점**: 한 필지에 buildhub-VWorld 동 수 차이가 있을 때,
   *어느 동이 어느 동에 대응되는지* 정확 매칭 불가. 현재는 연면적 정렬로 페어링하나
   정확하지 않음. 향후 *동명 매칭*(`dongNm` ↔ `buld_nm`) 또는 *공간 가까움*으로 강화 가능
4. **footprint 미등록 건물**: VWorld DB가 모든 동을 폴리곤화하지 않음 (특히 부속건물)

## 9. 다른 동에 적용 절차

```python
# 1. 행정동 → 산하 법정동코드 식별
geocode = vworld_geocode("경상남도 창원시 마산합포구 ○○동")
bbox = make_bbox(geocode.x, geocode.y, ±0.012)  # 약 5~6km²
features = vworld_data_get_feature(LT_C_SPBD, geomFilter=BOX(bbox))
bjd_codes = set(f.bd_mgt_sn[5:10] for f in features if f.gu == '○○동')

# 2. 각 법정동에 대해 buildhub 전수 호출
for bjd in bjd_codes:
    items = call_buildhub(sigunguCd, bjd)

# 3. PNU 조인 (위 4번 규칙)
# 4. GeoJSON + HTML 생성
```

행정동 1개당 약 10~15분 소요 (호출 시간 + 조인). 일일 트래픽 한도 1,000건/일 주의.

## 10. 다음 단계 (후보)

- 인접 동(대창동·신월동·월영동 등) 동일 파이프라인 적용 → *비교 시각화*
- buildhub-physical-analyzer 6유형 클러스터링 결과를 색상에 통합
- KOSIS 인구·가구 데이터 결합 → 동 단위 *물리상태 × 거주특성* 결합 분석
- 도시재생 정책 대상지 매칭 (datago API의 정비구역·도시재생활성화지역)

---

*작성: 2026-05-27*
