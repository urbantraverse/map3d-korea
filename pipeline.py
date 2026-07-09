"""map3d-korea 파이프라인 — buildhub × VWorld PNU 조인으로 행정동 3D 박스 GeoJSON 생성.

행정동 1개당 약 10~15분 (네트워크 대기 포함).
일일 호출 한도: data.go.kr 활용신청별 1,000건/일, VWorld 키별 별도 한도.

사용:
    # 코드를 아는 경우 (--mode code, 기본)
    python pipeline.py --sigungu 48125 --bjdong 11500 \\
        --bbox 128.539,35.178,128.583,35.215 \\
        --out pilots/munhwa-dong --tag munhwa --html

    # 동 이름만으로 (지오코딩 + BBOX 안 동 코드 자동 역추적)
    python pipeline.py --dong "경상남도 창원시 마산합포구 대창동" --mode bbox \\
        --out pilots/daechang-dong --tag daechang --html

핵심 자산 — PNU 11번째 자리 통일 규칙:
    buildhub `platGbCd=0` (대지) ↔ VWorld `bd_mgt_sn[10]='1'` — 같은 의미를 다르게 표기.
    PNU 합성 시 11번째 자리를 '1'로 통일하면 두 데이터셋 매칭이 작동한다.
    임야(山) 지번(`platGbCd=2`)은 이 규칙으로 처리 불가 — 별도 분기 필요(현재 미구현).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

load_dotenv("/Users/dw/G-Drive2T/Research_tools/.env")

DATAGO = os.environ["DATAGO_API_KEY"]
VWORLD = os.environ["VWORLD_API_KEY"]

BUILDHUB_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
VWORLD_URL = "https://api.vworld.kr/req/data"

PAGE_SIZE = 200
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_PAGES = 0.3  # 친절한 호출


# ──────────────────────────────────────────────────────────────────────
# PNU 합성 — 이 프로젝트의 핵심 자산
# ──────────────────────────────────────────────────────────────────────

def buildhub_pnu(it: dict) -> str:
    """buildhub 표제부 한 건 → 19자리 PNU. 11번째 자리는 '1' 고정."""
    sig = str(it["sigunguCd"]).zfill(5)
    bjd = str(it["bjdongCd"]).zfill(5)
    bun = str(it["bun"]).zfill(4)
    ji = str(it["ji"]).zfill(4)
    return f"{sig}{bjd}1{bun}{ji}"


def vworld_pnu(props: dict) -> str:
    """VWorld LT_C_SPBD 한 건 → 19자리 PNU (bd_mgt_sn 앞 19자리)."""
    return props["bd_mgt_sn"][:19]


_ROAD_NUM_RE = re.compile(r"^(\d+)(?:-(\d+))?$")


def buildhub_road_key(it: dict) -> tuple[str, int, int] | None:
    """buildhub `newPlatPlc` → (도로명, 본번, 부번). 예: '...반월시장1길 43-4 (문화동)' → ('반월시장1길', 43, 4).

    파싱 가정: 토큰 split 시 끝에서 셋·둘째가 도로명·번호, 마지막은 '(법정동명)'.
    """
    plc = (it.get("newPlatPlc") or "").strip()
    if not plc:
        return None
    parts = plc.split()
    if len(parts) < 4:
        return None
    m = _ROAD_NUM_RE.match(parts[-2])
    if not m:
        return None
    return (parts[-3], int(m.group(1)), int(m.group(2) or 0))


def vworld_road_key(props: dict) -> tuple[str, int, int] | None:
    """VWorld → (도로명, 본번, 부번). `rd_nm` + `buld_no` 조합."""
    road = (props.get("rd_nm") or "").strip()
    bn = str(props.get("buld_no") or "").strip()
    if not road or not bn:
        return None
    m = _ROAD_NUM_RE.match(bn)
    if not m:
        return None
    return (road, int(m.group(1)), int(m.group(2) or 0))


# ──────────────────────────────────────────────────────────────────────
# 1단계: buildhub 표제부 전수
# ──────────────────────────────────────────────────────────────────────

def fetch_buildhub_all(sigungu: str, bjdong: str, cache_path: Path) -> list[dict]:
    """sigungu·bjdong 단위로 buildhub 표제부 전수 호출. JSONL 캐시 재사용."""
    if cache_path.exists():
        with cache_path.open() as f:
            return [json.loads(line) for line in f]

    items: list[dict] = []
    page = 1
    while True:
        params = {
            "serviceKey": DATAGO,
            "sigunguCd": sigungu,
            "bjdongCd": bjdong,
            "numOfRows": PAGE_SIZE,
            "pageNo": page,
            "_type": "json",
        }
        r = requests.get(BUILDHUB_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        total = int(body.get("totalCount", 0))
        rows = body.get("items", {}).get("item", [])
        if isinstance(rows, dict):
            rows = [rows]
        items.extend(rows)
        print(f"  buildhub page {page}: +{len(rows)} (누적 {len(items)}/{total})", file=sys.stderr)
        if len(items) >= total or not rows:
            break
        page += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return items


# ──────────────────────────────────────────────────────────────────────
# 2단계: VWorld LT_C_SPBD footprint 전수
# ──────────────────────────────────────────────────────────────────────

def fetch_vworld_buildings(bbox: tuple[float, float, float, float],
                           bjdong_filter: str,
                           cache_path: Path) -> list[dict]:
    """BBOX 내 LT_C_SPBD 전수 → bd_mgt_sn[5:10] == bjdong_filter만 보존.

    VWorld BBOX 한도 10km². 큰 행정동은 호출 전에 분할 BBOX로 split.
    """
    if cache_path.exists():
        with cache_path.open() as f:
            return json.load(f)

    minx, miny, maxx, maxy = bbox
    box = f"{minx},{miny},{maxx},{maxy}"
    features: list[dict] = []
    page = 1
    while True:
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LT_C_SPBD",
            "key": VWORLD,
            "geomFilter": f"BOX({box})",
            "crs": "EPSG:4326",
            "size": PAGE_SIZE,
            "page": page,
            "format": "json",
            "geometry": "true",
            "attribute": "true",
            "domain": "localhost",
        }
        r = requests.get(VWORLD_URL, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        body = r.json()["response"]
        if body.get("status") != "OK":
            raise RuntimeError(f"VWorld 응답 비정상: {body}")
        result = body["result"]["featureCollection"]["features"]
        for feat in result:
            sn = feat["properties"].get("bd_mgt_sn", "")
            if sn[5:10] == bjdong_filter:
                features.append(feat)
        total = int(body["record"]["total"])
        print(f"  vworld page {page}: +{len(result)} (필터링 후 누적 {len(features)}/{total})",
              file=sys.stderr)
        if page * PAGE_SIZE >= total or not result:
            break
        page += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w") as f:
        json.dump(features, f, ensure_ascii=False)
    return features


# ──────────────────────────────────────────────────────────────────────
# 3단계: PNU 조인 + 1:N 페어링
# ──────────────────────────────────────────────────────────────────────

def _norm_name(s: Any) -> str | None:
    """동·건물명 정규화: strip 후 빈 문자열/공백/대시는 None."""
    if s is None:
        return None
    t = str(s).strip()
    return t if t and t not in {"-", "."} else None


def _pair_groups(bh_groups: dict, vw_groups: dict,
                 used_vw_ids: set[int], match_via: str,
                 pairs: list[tuple[dict, dict, bool, str]]) -> int:
    """공통 키별 buildhub·VWorld 그룹 페어링. pairs에 in-place 추가.

    같은 키 안 페어링 우선순위:
    1) `dongNm`(buildhub) == `buld_nm`(VWorld) 정확 일치 — 단지·아파트 동 식별
    2) 남은 것은 면적 정렬 zip (buildhub `totArea` ↓ vs VWorld 외부 링 좌표수 ↓)

    Returns: 이름 일치로 잡힌 쌍 수 (디버그용).
    """
    name_paired = 0
    for key in set(bh_groups) & set(vw_groups):
        bh_remaining = list(bh_groups[key])
        vw_remaining = [f for f in vw_groups[key] if id(f) not in used_vw_ids]
        is_multi = len(bh_remaining) > 1 or len(vw_remaining) > 1

        # 1차: 이름 정확 일치 (단지 안 동 식별)
        if len(bh_remaining) > 1 or len(vw_remaining) > 1:
            i = 0
            while i < len(bh_remaining):
                bh = bh_remaining[i]
                bn = _norm_name(bh.get("dongNm"))
                hit = None
                if bn:
                    for j, vw in enumerate(vw_remaining):
                        if _norm_name(vw["properties"].get("buld_nm")) == bn:
                            hit = j
                            break
                if hit is not None:
                    vw = vw_remaining.pop(hit)
                    bh_remaining.pop(i)
                    pairs.append((bh, vw, is_multi, match_via))
                    used_vw_ids.add(id(vw))
                    name_paired += 1
                else:
                    i += 1

        # 2차: 면적 정렬 zip
        bh_sorted = sorted(bh_remaining,
                           key=lambda it: float(it.get("totArea") or 0), reverse=True)
        vw_sorted = sorted(vw_remaining,
                           key=lambda f: len(f["geometry"]["coordinates"][0][0]),
                           reverse=True)
        for bh, vw in zip(bh_sorted, vw_sorted):
            pairs.append((bh, vw, is_multi, match_via))
            used_vw_ids.add(id(vw))
    return name_paired


def join_by_pnu(bh_items: list[dict], vw_features: list[dict]
                ) -> tuple[list[tuple[dict, dict, bool, str]], list[dict]]:
    """1차 PNU + 2차 도로명 fallback 매칭.

    같은 PNU에 buildhub N건·VWorld M건이 있을 때:
    - buildhub는 `totArea` *내림차순* (큰 건물 우선)
    - VWorld는 폴리곤 면적 *내림차순* (외부 링 좌표 수로 근사)
    - 위치별 짝지움. min(N, M)건만 페어링.

    1차에서 못 잡힌 buildhub·VWorld는 도로명 키(`buildhub_road_key`/`vworld_road_key`)로
    재시도. PNU 미스(11번째 자리 변형·산번지·부번 형식)와 1:N 짤림을 보충.

    Returns:
        pairs: [(buildhub_item, vworld_feature, is_multi_pair, match_via), ...]
               match_via: 'pnu' | 'road'
        unmatched_vw: 어느 단계에서도 페어링 못 된 VWorld features
    """
    pairs: list[tuple[dict, dict, bool, str]] = []
    used_vw_ids: set[int] = set()

    # 1차: PNU
    bh_by_pnu: dict[str, list[dict]] = {}
    for it in bh_items:
        try:
            bh_by_pnu.setdefault(buildhub_pnu(it), []).append(it)
        except (KeyError, TypeError):
            continue
    vw_by_pnu: dict[str, list[dict]] = {}
    for feat in vw_features:
        try:
            vw_by_pnu.setdefault(vworld_pnu(feat["properties"]), []).append(feat)
        except (KeyError, TypeError):
            continue
    name_paired_pnu = _pair_groups(bh_by_pnu, vw_by_pnu, used_vw_ids, "pnu", pairs)

    # 2차: 도로명 fallback (1차 미매칭만)
    matched_bh_pks = {p[0].get("mgmBldrgstPk") for p in pairs}
    remaining_bh = [it for it in bh_items if it.get("mgmBldrgstPk") not in matched_bh_pks]
    remaining_vw = [f for f in vw_features if id(f) not in used_vw_ids]

    bh_by_road: dict[tuple, list[dict]] = {}
    for it in remaining_bh:
        k = buildhub_road_key(it)
        if k:
            bh_by_road.setdefault(k, []).append(it)
    vw_by_road: dict[tuple, list[dict]] = {}
    for feat in remaining_vw:
        k = vworld_road_key(feat["properties"])
        if k:
            vw_by_road.setdefault(k, []).append(feat)
    name_paired_road = _pair_groups(bh_by_road, vw_by_road, used_vw_ids, "road", pairs)

    unmatched_vw = [f for f in vw_features if id(f) not in used_vw_ids]
    pairs_meta = {"paired_by_name": name_paired_pnu + name_paired_road}
    return pairs, unmatched_vw, pairs_meta


def encode_unmatched_vw(vw: dict) -> dict:
    """VWorld 폴리곤은 있으나 buildhub 매칭 실패한 건 → 회색·디폴트 높이 피처."""
    p = vw["properties"]
    props = {
        "pnu": vworld_pnu(p),
        "bd_mgt_sn": p.get("bd_mgt_sn"),
        "rd_nm": p.get("rd_nm"),
        "buld_no": p.get("buld_no"),
        "buld_nm": p.get("buld_nm"),
        "platPlc": None,
        "mainPurps": None,
        "strct": None,
        "useAprYear": None,
        "grndFlr": None,
        "ugrndFlr": 0,
        "fmlyCnt": 0,
        "hhldCnt": 0,
        "totArea": 0,
        "height_m": 6,  # 디폴트 ~2층
        "era": "no_buildhub",
        "multi_pair": False,
        "unmatched": True,
    }
    return {"type": "Feature", "geometry": vw["geometry"], "properties": props}


# ──────────────────────────────────────────────────────────────────────
# 4단계: 속성 인코딩
# ──────────────────────────────────────────────────────────────────────

def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def encode_feature(bh: dict, vw: dict, is_multi: bool, match_via: str = "pnu") -> dict:
    """페어링된 한 쌍 → 시각화용 GeoJSON Feature.

    height_m = 지상 층수 × 3m (사용승인일은 색상 era, 높이는 층수).
    era 카테고리: pre1970 / 1970s / 1980s / 1990s / post2000 / unknown.
    match_via: 어느 단계 매칭인지 ('pnu' | 'road').
    """
    use_apr = str(bh.get("useAprDay") or "")
    use_year = _safe_int(use_apr[:4]) if len(use_apr) >= 4 else 0
    if use_year == 0:
        era = "unknown"
    elif use_year < 1970:
        era = "pre1970"
    elif use_year < 1980:
        era = "1970s"
    elif use_year < 1990:
        era = "1980s"
    elif use_year < 2000:
        era = "1990s"
    else:
        era = "post2000"

    grnd = _safe_int(bh.get("grndFlrCnt"), 0)
    ugrnd = _safe_int(bh.get("ugrndFlrCnt"), 0)
    height_m = max(grnd * 3, 3)

    props = {
        "pnu": buildhub_pnu(bh),
        "mgmBldrgstPk": bh.get("mgmBldrgstPk"),
        "bd_mgt_sn": vw["properties"].get("bd_mgt_sn"),
        "platPlc": bh.get("platPlc"),
        "newPlatPlc": bh.get("newPlatPlc"),
        "dongNm": bh.get("dongNm"),
        "rd_nm": vw["properties"].get("rd_nm"),
        "buld_no": vw["properties"].get("buld_no"),
        "buld_nm": vw["properties"].get("buld_nm"),
        "mainPurps": bh.get("mainPurpsCdNm"),
        "strct": bh.get("strctCdNm"),
        "useAprYear": use_year or None,
        "grndFlr": grnd,
        "ugrndFlr": ugrnd,
        "fmlyCnt": _safe_int(bh.get("fmlyCnt"), 0),
        "hhldCnt": _safe_int(bh.get("hhldCnt"), 0),
        "totArea": float(bh.get("totArea") or 0),
        "height_m": height_m,
        "era": era,
        "multi_pair": is_multi,
        "match_via": match_via,
    }
    return {"type": "Feature", "geometry": vw["geometry"], "properties": props}


# ──────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────

def discover_codes_from_bbox(bbox: tuple[float, float, float, float],
                             out_dir: Path, tag: str,
                             min_count: int = 5) -> tuple[list[dict], list[tuple[str, str, int]]]:
    """BBOX 안 VWorld 건물 전수 → (sigungu, bjdong) 분포 역추적.

    Returns: (vw_features_all, [(sigungu, bjdong, count), ...] 빈도순)
    `min_count` 미만의 (sigungu,bjdong)은 노이즈로 제외 — buildhub 호출 절감.
    """
    vw_cache = out_dir / f"vworld_{tag}.json"
    # bjdong 필터 없이 박스 안 전수 — 임시 sentinel 사용
    if vw_cache.exists():
        with vw_cache.open() as f:
            features = json.load(f)
    else:
        minx, miny, maxx, maxy = bbox
        box = f"{minx},{miny},{maxx},{maxy}"
        features = []
        page = 1
        while True:
            params = {
                "service": "data", "request": "GetFeature", "data": "LT_C_SPBD",
                "key": VWORLD, "geomFilter": f"BOX({box})", "crs": "EPSG:4326",
                "size": PAGE_SIZE, "page": page, "format": "json",
                "geometry": "true", "attribute": "true", "domain": "localhost",
            }
            r = requests.get(VWORLD_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            body = r.json()["response"]
            if body.get("status") != "OK":
                raise RuntimeError(f"VWorld 응답 비정상: {body}")
            result = body["result"]["featureCollection"]["features"]
            features.extend(result)
            total = int(body["record"]["total"])
            print(f"  vworld(BBOX) page {page}: +{len(result)} (누적 {len(features)}/{total})",
                  file=sys.stderr)
            if page * PAGE_SIZE >= total or not result:
                break
            page += 1
            time.sleep(SLEEP_BETWEEN_PAGES)
        out_dir.mkdir(parents=True, exist_ok=True)
        with vw_cache.open("w") as f:
            json.dump(features, f, ensure_ascii=False)

    counts = Counter()
    for feat in features:
        sn = feat["properties"].get("bd_mgt_sn", "")
        if len(sn) >= 10:
            counts[(sn[0:5], sn[5:10])] += 1
    codes = sorted([(s, b, n) for (s, b), n in counts.items() if n >= min_count],
                   key=lambda x: -x[2])
    return features, codes


def run_by_bbox(bbox: tuple[float, float, float, float],
                out_dir: Path, tag: str, min_count: int = 5,
                include_unmatched: bool = False) -> dict:
    """드래그 BBOX 한 번으로 동 코드 자동 역추적 후 buildhub 조인."""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] VWorld BBOX 전수 + 동 코드 역추적", file=sys.stderr)
    vw_all, codes = discover_codes_from_bbox(bbox, out_dir, tag, min_count)
    print(f"  발견된 (sigungu,bjdong): {len(codes)}개 — {codes[:10]}", file=sys.stderr)

    print(f"[2/4] buildhub 전수 ({len(codes)}개 법정동)", file=sys.stderr)
    bh_all: list[dict] = []
    for sig, bjd, _ in codes:
        bh_cache = out_dir / f"buildhub_{sig}_{bjd}.jsonl"
        bh_all.extend(fetch_buildhub_all(sig, bjd, bh_cache))

    print(f"[3/4] PNU 조인 + 1:N 페어링", file=sys.stderr)
    pairs, unmatched_vw, pairs_meta = join_by_pnu(bh_all, vw_all)
    features = [encode_feature(*p) for p in pairs]
    if include_unmatched:
        features.extend(encode_unmatched_vw(vw) for vw in unmatched_vw)

    print(f"[4/4] GeoJSON 저장", file=sys.stderr)
    gj = {"type": "FeatureCollection", "features": features}
    out_path = out_dir / f"{tag}_joined.geojson"
    with out_path.open("w") as f:
        json.dump(gj, f, ensure_ascii=False)

    summary = {
        "mode": "bbox",
        "bbox": list(bbox),
        "codes": [{"sigungu": s, "bjdong": b, "vworld_count": n} for s, b, n in codes],
        "buildhub_total": len(bh_all),
        "vworld_total": len(vw_all),
        "matched_features": len(pairs),
        "matched_pnu": len({encode_feature(*p)["properties"]["pnu"] for p in pairs}) if pairs else 0,
        "matched_via_pnu": sum(1 for p in pairs if p[3] == "pnu"),
        "matched_via_road": sum(1 for p in pairs if p[3] == "road"),
        "paired_by_name": pairs_meta["paired_by_name"],
        "unmatched_vw": len(unmatched_vw),
        "include_unmatched": include_unmatched,
        "match_rate": round(len(pairs) / max(len(bh_all), 1), 3),
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    return summary


def run(sigungu: str, bjdong: str, bbox: tuple[float, float, float, float],
        out_dir: Path, tag: str, include_unmatched: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    bh_cache = out_dir / f"buildhub_{tag}.jsonl"
    vw_cache = out_dir / f"vworld_{tag}.json"

    print(f"[1/3] buildhub 전수 ({sigungu}/{bjdong})", file=sys.stderr)
    bh_items = fetch_buildhub_all(sigungu, bjdong, bh_cache)

    print(f"[2/3] VWorld LT_C_SPBD ({bbox})", file=sys.stderr)
    vw_features = fetch_vworld_buildings(bbox, bjdong, vw_cache)

    print(f"[3/3] PNU 조인 + 1:N 페어링", file=sys.stderr)
    pairs, unmatched_vw, pairs_meta = join_by_pnu(bh_items, vw_features)
    features = [encode_feature(*p) for p in pairs]
    if include_unmatched:
        features.extend(encode_unmatched_vw(vw) for vw in unmatched_vw)

    gj = {"type": "FeatureCollection", "features": features}
    out_path = out_dir / f"{tag}_joined.geojson"
    with out_path.open("w") as f:
        json.dump(gj, f, ensure_ascii=False)

    summary = {
        "buildhub_total": len(bh_items),
        "vworld_total": len(vw_features),
        "matched_features": len(pairs),
        "matched_pnu": len({encode_feature(*p)["properties"]["pnu"] for p in pairs}) if pairs else 0,
        "matched_via_pnu": sum(1 for p in pairs if p[3] == "pnu"),
        "matched_via_road": sum(1 for p in pairs if p[3] == "road"),
        "paired_by_name": pairs_meta["paired_by_name"],
        "unmatched_vw": len(unmatched_vw),
        "include_unmatched": include_unmatched,
        "match_rate": round(len(pairs) / max(len(bh_items), 1), 3),
        "out": str(out_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=sys.stderr)
    return summary


def _parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 4:
        raise ValueError("BBOX는 minx,miny,maxx,maxy 형식")
    return tuple(parts)  # type: ignore[return-value]


def bbox_area_km2(bbox: tuple[float, float, float, float]) -> float:
    """BBOX(minx,miny,maxx,maxy) → 근사 면적(km²). 위도 중앙값으로 경도 방향 보정."""
    minx, miny, maxx, maxy = bbox
    lat_mid = (miny + maxy) / 2
    w_km = (maxx - minx) * 111 * math.cos(math.radians(lat_mid))
    h_km = (maxy - miny) * 111
    return w_km * h_km


def geocode_dong(dong: str) -> tuple[float, float]:
    """VWorld Geocoder로 한글 주소를 (x, y) 좌표로 변환. ROAD 실패 시 PARCEL로 재시도."""
    url = "https://api.vworld.kr/req/address"
    last_status = None
    for addr_type in ("road", "parcel"):
        r = requests.get(url, params={
            "service": "address", "request": "getcoord", "version": "2.0",
            "crs": "epsg:4326", "address": dong,
            "type": addr_type, "key": VWORLD, "format": "json",
        }, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        body = r.json().get("response", {})
        last_status = body.get("status")
        if last_status == "OK":
            point = body["result"]["point"]
            return float(point["x"]), float(point["y"])
    raise RuntimeError(f"VWorld geocode 실패: {dong!r} (마지막 status={last_status})")


# ──────────────────────────────────────────────────────────────────────
# 5단계: HTML 시각화 생성
# ──────────────────────────────────────────────────────────────────────

def write_html(geojson_path: Path, summary: dict, out_dir: Path, tag: str,
               title: str, bbox: tuple[float, float, float, float],
               zoom: float = 16.5) -> Path:
    """조인 결과 GeoJSON → template_3d.html 채워서 인터랙티브 3D HTML 생성."""
    template_path = Path(__file__).parent / "template_3d.html"
    template = template_path.read_text(encoding="utf-8")

    with geojson_path.open() as f:
        geojson = json.load(f)

    features = geojson["features"]
    if features:
        lngs, lats = [], []
        for feat in features:
            # VWorld LT_C_SPBD 지오메트리는 MultiPolygon: coordinates[0][0] = 첫 폴리곤의 외곽 링
            ring = feat["geometry"]["coordinates"][0][0]
            c = ring[0]  # 근사 무게중심용 첫 좌표
            lngs.append(c[0])
            lats.append(c[1])
        center_lng = sum(lngs) / len(lngs)
        center_lat = sum(lats) / len(lats)
    else:
        center_lng = (bbox[0] + bbox[2]) / 2
        center_lat = (bbox[1] + bbox[3]) / 2

    total = len(features)
    bh_total = summary.get("buildhub_total", 0)
    rate = f"{total / max(bh_total, 1):.1%}"

    era_counts = Counter(f["properties"]["era"] for f in features)
    era_dist = " · ".join(f"{k}:{v}" for k, v in sorted(era_counts.items()))
    basement = sum(1 for f in features if (f["properties"].get("ugrndFlr") or 0) >= 1)
    multi = sum(1 for f in features if f["properties"].get("multi_pair"))

    html = (template
        .replace("{{TITLE}}", title)
        .replace("{{DATA_JSON}}", json.dumps(geojson, ensure_ascii=False))
        .replace("{{CENTER_LNG}}", f"{center_lng:.6f}")
        .replace("{{CENTER_LAT}}", f"{center_lat:.6f}")
        .replace("{{ZOOM}}", str(zoom))
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sigungu", help="시군구코드 5자리 (예: 48125). --mode code 필수")
    ap.add_argument("--bjdong", help="법정동코드 5자리 (예: 11500). --mode code 필수")
    ap.add_argument("--bbox", type=_parse_bbox,
                    help="VWorld 호출 BBOX: minx,miny,maxx,maxy (≤10km²). --dong 지정 시 생략 가능")
    ap.add_argument("--dong", help="한글 주소로 BBOX 자동 산출 (예: '경상남도 창원시 마산합포구 대창동')")
    ap.add_argument("--bbox-radius", type=float, default=0.011,
                    help="--dong 지오코딩 결과에 적용할 위경도 반경 (기본 0.011 → 약 6km²)")
    ap.add_argument("--mode", choices=["code", "bbox"], default="code",
                    help="code=--sigungu/--bjdong 지정 (기본) · bbox=BBOX 안 동 코드 자동 역추적")
    ap.add_argument("--min-count", type=int, default=5,
                    help="--mode bbox에서 (sigungu,bjdong) 채택 최소 건물 수 (기본 5, 노이즈 제외)")
    ap.add_argument("--out", required=True, type=Path, help="출력 디렉터리")
    ap.add_argument("--tag", required=True, help="파일명 접두사 (예: munhwa)")
    ap.add_argument("--html", action="store_true", help="GeoJSON과 함께 3D 시각화 HTML도 생성")
    ap.add_argument("--title", help="HTML 제목 (기본: --tag 값)")
    ap.add_argument("--zoom", type=float, default=16.5, help="HTML 초기 줌 레벨 (기본 16.5)")
    args = ap.parse_args()

    if args.dong and args.bbox is None:
        gx, gy = geocode_dong(args.dong)
        r = args.bbox_radius
        args.bbox = (gx - r, gy - r, gx + r, gy + r)
        print(f"  지오코딩: {args.dong!r} → ({gx:.6f}, {gy:.6f}) · 반경 {r} → BBOX {args.bbox}",
              file=sys.stderr)

    if args.bbox is not None:
        area = bbox_area_km2(args.bbox)
        if area > 10:
            ap.error(f"BBOX 면적 {area:.2f}km²가 VWorld 한도(10km²) 초과 — --bbox-radius를 줄이세요")

    if args.mode == "code" and (not args.sigungu or not args.bjdong or args.bbox is None):
        ap.error("--mode code는 --sigungu, --bjdong, --bbox(또는 --dong) 모두 필수")
    if args.mode == "bbox" and args.bbox is None:
        ap.error("--mode bbox는 --bbox(또는 --dong) 필수")

    if args.mode == "bbox":
        summary = run_by_bbox(args.bbox, args.out, args.tag, args.min_count)
    else:
        summary = run(args.sigungu, args.bjdong, args.bbox, args.out, args.tag)

    if args.html:
        html_path = write_html(Path(summary["out"]), summary, args.out, args.tag,
                               args.title or args.tag, args.bbox, args.zoom)
        print(f"  HTML: {html_path}", file=sys.stderr)
