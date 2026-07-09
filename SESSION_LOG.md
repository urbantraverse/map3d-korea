# 2026-05-27 세션 — buildhub × VWorld 3D 파일럿 + 인프라 SSOT 정비

> Cowork 한 세션에서 두 줄기 작업이 얽혀 진행됨.
> 한 줄기는 *마산합포구 문화동의 첫 3D 박스 시각화*, 다른 줄기는
> *모든 API 키와 글로벌 지침의 SSOT(단일 출처) 정비*.

---

## TL;DR

| 줄기 | 결과 |
|---|---|
| **인프라 SSOT** | 마스터 `.env` (15+ 키), MCP 5개 dotenv 패치, CLAUDE.md 4개 (글로벌·Code 글로벌·프로젝트 3개) 정비 |
| **buildhub 3D 파일럿** | 문화동 199건 3D 박스 (PNU 매칭률 82.2%), 조인 키 규칙 발견 |

핵심 기술 자산: **buildhub와 VWorld의 PNU 인코딩 차이 해결 규칙** — 두 한국 표준 데이터셋을 *11번째 자리 변환 한 줄*로 연결.

---

## 1. 세션의 발단

[cartesiancs/map3d](https://github.com/cartesiancs/map3d) GitHub 저장소를 접함:
"신기한데". R3F 기반 3D 도시 시각화 도구.

진단:
- map3d는 OpenStreetMap 기반 → 한국은 OSM 부실
- buildhub-physical-analyzer 스킬(건축물대장 API)·VWorld MCP·KOSIS MCP 보유
- **데이터가 풍부한 한국 공공 API + map3d의 렌더링 패턴**을 결합하면 *지방 중소도시 3D 파일럿* 가능

→ 마산합포구 *문화동*을 파일럿 대상으로 결정.

---

## 2. 인프라 SSOT 정비 (먼저 풀린 줄기)

파일럿 진행 중 **buildhub API 키 위치를 못 찾아서 막힘**.
개발 환경에 `.env` 파일이 *3곳에 산재* (rag-pipeline, arena-app, law_mcp).
이 사고를 *근본 해결*하기로 결정.

### 2.1 마스터 `.env` 신설

위치: `~/G-Drive2T/Research_tools/.env`

15개 카테고리·19+ 슬롯의 단일 출처:

| 카테고리 | 슬롯 |
|---|---|
| 공공데이터·통계 | DATAGO_API_KEY, DATAGO_API_KEY_LEGACY, KOSIS_API_KEY, SGIS_SERVICE_ID, SGIS_SECRET_KEY, SEOUL_OPEN_DATA_API_KEY |
| 공간정보 | VWORLD_API_KEY, NGII_API_KEY, TRAFFIC_NURI_API_KEY |
| 법령·기록·의회 | LAW_OC, ARCHIVES_API_KEY, ASSEMBLY_OPEN_API_KEY |
| 학술 | KCI_API_KEY, SEMANTIC_SCHOLAR_API_KEY |
| 미디어 | NL_API_KEY |
| AI·음성·메일 | ANTHROPIC_API_KEY, ANTHROPIC_API_KEY_RESEARCH, ELEVENLABS_API_KEY, GOOGLE_VERTEX_API_KEY, RESEND_API_KEY |

`.gitignore` 동반 (`**/.env` 패턴).

### 2.2 MCP 5개 dotenv 패치

각 MCP 부팅 시 마스터 `.env` 자동 흡수:

```python
try:
    from dotenv import load_dotenv
    load_dotenv()  # sub-project .env 먼저 (기존 동작 보존)
    load_dotenv("/Users/dw/G-Drive2T/Research_tools/.env", override=False)
except ImportError:
    pass
```

패치된 파일:
- `KOSIS_Vworld/datago-mcp/datago_mcp.py`
- `KOSIS_Vworld/vworld-mcp/vworld_mcp.py`
- `KOSIS_Vworld/kosis-mcp/kosis_mcp.py`
- `law_mcp/src/server.py`
- `research_raglocal/rag-pipeline/mcp_server.py`

핵심 안전장치: **`override=False`** → 기존 sub-project `.env`가 우선,
마스터는 *없는 키만 보충*. 기존 시스템 100% 보존.

### 2.3 CLAUDE.md 4개 정비

| 파일 | 변경 |
|---|---|
| `Research_tools/CLAUDE.md` | "## 환경"·"## 보안" 섹션에 마스터 .env 위치 명시 |
| `current_writings/AI_geography/Physical_ai_geography/CLAUDE.md` | 헤더 박스에 한 줄 추가 |
| `current_writings/Automobile_Human/CLAUDE.md` | 헤더 박스 + 주요 파일 표의 .env 항목 마스터 참조로 갱신 |
| `~/.claude/CLAUDE.md` (신설) | Claude Code 글로벌 — 한 단락 (5줄) |
| `~/Library/.../memory/CLAUDE.md` (Cowork 글로벌) | **70줄 → 28줄 다이어트** + 마스터 .env 한 줄 통합 |

### 2.4 셸 환경 (Claude Code 자동 인식)

`~/.zshrc` 한 줄:
```bash
[ -f "$HOME/G-Drive2T/Research_tools/.env" ] && set -a && source "$HOME/G-Drive2T/Research_tools/.env" && set +a
```

→ 새 터미널 열 때마다 마스터 키들이 환경변수로 자동 export.

### 2.5 Claude Desktop Custom Instructions

```
## API 키
모든 API 키는 마스터 .env 한 곳에 있다: /Users/dw/G-Drive2T/Research_tools/.env
- 코드 로드: load_dotenv("/Users/dw/G-Drive2T/Research_tools/.env")
- 새 키는 무조건 이 파일에. sub-project별 .env 생성 금지.
```

### 2.6 4중 방어 구조

```
[마스터 .env] /Users/dw/G-Drive2T/Research_tools/.env
       │
       ├─ Cowork              ← file tools 직접 (무설정)
       ├─ Claude Code (터미널) ← zshrc source + ~/.claude/CLAUDE.md
       ├─ Claude Desktop MCP  ← 5개 MCP에 dotenv 패치
       └─ Claude Desktop 대화 ← Custom Instructions
```

---

## 3. buildhub × VWorld 3D 파일럿

인프라 정비 후 본격 진행. *원래 요청이었던* 문화동 3D 박스.

### 3.1 핵심 발견 — 조인 키 규칙

두 데이터셋의 *건물 단위 식별자*가 서로 다름:

| 출처 | 필드 | 길이 | 의미 |
|---|---|---|---|
| buildhub | `mgmBldrgstPk` | 15 | 건축물대장 PK |
| VWorld `LT_C_SPBD` | `bd_mgt_sn` | 25 | 도로명주소법 건물고유번호 |

**둘은 직접 매칭 불가.** 대신 *지번 PNU 19자리*를 합성해 매칭:

```python
# buildhub PNU 합성 — 11번째 자리 강제 '1'
def buildhub_pnu(it):
    return f"{it['sigunguCd'].zfill(5)}{it['bjdongCd'].zfill(5)}1{it['bun'].zfill(4)}{it['ji'].zfill(4)}"

# VWorld는 bd_mgt_sn[:19] 그대로
```

⚠️ **인코딩 차이의 함정**: buildhub `platGbCd=0`(대지) ↔ VWorld bd_mgt_sn[10]=`1`.
*같은 의미를 다르게 표기*. 11번째 자리를 `1`로 통일하는 *한 줄*이 핵심.

### 3.2 매칭률 개선의 두 번의 점프

| 단계 | BBOX | 매칭 PNU | 매칭률 (buildhub 242 기준) |
|---|---|---|---|
| v1 | 4.5km² (좁음, 1:1) | 130 | **53.7%** |
| v2 | 6.5km² (확장, 1:N 페어링) | 199 | **82.2%** ✅ |

비결:
1. **BBOX 확장** (VWorld 한도 10km² 내까지)
2. **1:N 페어링** — 한 PNU에 buildhub 여러 건 ↔ VWorld 여러 건을 *연면적 정렬*로 짝지움

### 3.3 문화동의 정량적 초상

매칭된 199건 분포:

| 지표 | 수치 | 해석 |
|---|---|---|
| 1990 이전 준공 | **76%** | 극단적 노후 |
| 단독주택 비중 | 87% | 마산 구도심 전형 |
| 1-2층 비중 | 90% | 신축·고밀 부재 |
| 반지하 보유 | 13% | 단독 위주임에도 *지층 압력* |
| 다가구(fmlyCnt≥2) | 6건 | 분산형 임대 *없음* |
| 본번 14에 집중 | **104건** | 조밀한 단독 클러스터 |

→ 유형 분류: **C형 (단독·다가구 노후형)** — 마산 구도심 전형
→ 정책 함의: *집수리·매입형 도시재생*이 정공법. 신축형 부적합.

### 3.4 파이프라인 (재현 절차)

```
[행정동 좌표]  vworld_geocode("경상남도 ... ○○동")
      ↓
[법정동코드]   VWorld LT_C_SPBD BBOX → gu='○○동' → bd_mgt_sn[5:10]
      ↓
[buildhub 전수] getBrTitleInfo(sigunguCd, bjdongCd, page=1~)
      ↓
[VWorld 전수]   LT_C_SPBD geomFilter (size=200, BBOX ≤10km²)
                → bd_mgt_sn[:10] = 해당 법정동 필터
      ↓
[PNU 조인]      bh_pnu ↔ vw_pnu 교집합 + 1:N 연면적 페어링
      ↓
[속성 인코딩]   사용승인일→시기, 층수×3m→높이, 반지하 플래그
      ↓
[GeoJSON + HTML] deck.gl PolygonLayer extruded + MapLibre 베이스맵
```

행정동 1개당 약 10~15분 소요. 일일 트래픽 한도 1,000건 주의.

---

## 4. 산출물 인덱스

### 4.1 인프라 (영구 자산)

| 위치 | 역할 |
|---|---|
| [`Research_tools/.env`](computer:///Users/dw/G-Drive2T/Research_tools/.env) | 마스터 SSOT (19+ 키 슬롯) |
| [`Research_tools/.gitignore`](computer:///Users/dw/G-Drive2T/Research_tools/.gitignore) | `**/.env` 보호 |
| [`Research_tools/CLAUDE.md`](computer:///Users/dw/G-Drive2T/Research_tools/CLAUDE.md) | 프로젝트 지침 (환경·보안 섹션 보강) |
| `KOSIS_Vworld/{datago,vworld,kosis}-mcp/*.py` | dotenv 패치 적용 |
| `law_mcp/src/server.py` | dotenv 패치 |
| `research_raglocal/rag-pipeline/mcp_server.py` | dotenv 패치 |
| `~/.claude/CLAUDE.md` | Claude Code 글로벌 (신설) |
| `~/Library/.../memory/CLAUDE.md` | Cowork 글로벌 (28줄 다이어트) |

### 4.2 buildhub 파일럿 (재사용 가능 산출물)

> 산출물은 `map3d-korea/pilots/munhwa-dong/`로 이전 완료 (2026-05-27). 옛 경로 `Research_tools/buildhub-3d-pilot/`는 빈 폴더.

| 파일 | 내용 |
|---|---|
| [`map3d-korea/pilots/munhwa-dong/buildhub_munhwa.jsonl`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/buildhub_munhwa.jsonl) | 표제부 전수 242건 (78필드) |
| [`map3d-korea/pilots/munhwa-dong/munhwa_joined_v2.geojson`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/munhwa_joined_v2.geojson) | PNU 조인 통합 199건 (고유 PNU 193) |
| [`map3d-korea/pilots/munhwa-dong/munhwa_3d_v2.html`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/munhwa_3d_v2.html) | 인터랙티브 3D 박스 (deck.gl) |
| [`map3d-korea/pilots/munhwa-dong/REPORT.md`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pilots/munhwa-dong/REPORT.md) | 재현 가능성 기술 노트 |
| [`map3d-korea/pipeline.py`](computer:///Users/dw/G-Drive2T/Research_tools/map3d-korea/pipeline.py) | 파이프라인 모듈 (2026-05-27 추가, 인접 동 적용용) |

### 4.3 이 세션 정리 노트

| 파일 | 내용 |
|---|---|
| `sessions/2026-05-27_buildhub-pilot-infra/README.md` | 이 문서 (단일 통합 정리) |

---

## 5. 풀린 함정 6개 (다음 작업 시 참고)

| 함정 | 어떻게 풀렸나 |
|---|---|
| `.env` 파일이 3곳에 산재 | 마스터 SSOT + dotenv 패치 |
| buildhub API 키 못 찾음 | 셀프 분석: data.go.kr는 활용신청 묶음별로 다른 키 발급. 마스터 키 ≠ 건축HUB 활용중 키 |
| HTTP 403 (Forbidden) | 처음엔 IP 차단 의심 → 결국 *마스터에 잘못된 키 입력*이 원인. 활용중 키로 교체로 해결 |
| VWorld에 건물 footprint 없는 줄 알았음 | `LT_C_SPBD` 데이터셋 발견 (WFS 카탈로그엔 없지만 Data API에 있음) |
| PNU 매칭 0% | 11번째 자리 인코딩 차이 (`0` vs `1`) — 통일 규칙으로 해결 |
| BBOX 14km² 거부 | VWorld 한도 10km² 발견. 6.5km²로 조정 |

---

## 6. 다음 단계 후보

- **다른 동 확장** — 대창동·신월동·월영동 등 같은 파이프라인 적용 → 비교 시각화 (마산합포구 *비교 카드*)
- **buildhub 6유형 클러스터링** 결과를 색상에 통합 (이미 buildhub-physical-analyzer 스킬에 알고리즘 있음)
- **KOSIS 인구·가구 결합** — 동 단위 *물리상태 × 거주특성*
- **도시재생 정책 매칭** — datago의 정비구역·재생활성화지역 GeoJSON 오버레이
- **Obsidian 노트화** — 20_Projects/에 프로젝트 폴더 만들고 STATUS·DECISIONS 분리 (lean root 패턴)
- **mcp venv 정리** — datago-mcp pip 권한 + New_developmentalism 절대경로 흔적 정리

---

## 7. 세션 흐름 (시간순)

```
[발단]
  GitHub map3d 저장소 발견 ("신기한데")
  → OSM 한국 부실 진단, buildhub × VWorld 결합 제안
      ↓
[1차 시도]
  파일럿 시작 → API 키 못 찾음 → .env 산재 발견
      ↓
[인프라 우회 결정]
  "매번 입력하라고 하는데 해결할 방법 없나" 문제의식
  → 마스터 .env SSOT 설계 → 4중 방어 구조 구축
      ↓
[키 사고 해결]
  마스터에 잘못된 키 입력 → 403 → 활용신청 묶음 확인 →
  진짜 건축HUB 키로 교체 → 200 OK
      ↓
[파일럿 본격]
  대창동에서 조인 키 검증 → 11번째 자리 인코딩 차이 발견 →
  통일 규칙 도출 → 매칭률 91% (대창동 1:1)
      ↓
[문화동 실전]
  buildhub 전수 242건 → VWorld footprint 261건 →
  v1 매칭률 53.7%
      ↓
[v2 개선]
  BBOX 확장 + 1:N 페어링 → 199건 → 매칭률 82.2%
      ↓
[3D 시각화]
  deck.gl PolygonLayer extruded → 인터랙티브 HTML
      ↓
[기록]
  REPORT.md (기술 노트) → 이 README.md (세션 통합)
```

---

*작성: 2026-05-27*
*세션 폴더: `Research_tools/sessions/2026-05-27_buildhub-pilot-infra/`*
