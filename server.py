"""map3d-korea 로컬 미니 서버 — 브라우저 폼으로 pipeline.py 호출.

사용:
    python3 server.py
    → http://127.0.0.1:8000

엔드포인트:
    GET  /                — 폼 페이지
    GET  /api/geocode     — 주소 → 좌표·BBOX 추천 (6km²)
    POST /api/run         — sigungu/bjdong/bbox → pipeline 실행 → GeoJSON 응답
    GET  /api/tags        — 기존 파일럿 폴더 목록
    GET  /api/load?tag=…  — 저장된 GeoJSON 로드 (캐시 재방문)
"""
from __future__ import annotations

import json
import math
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/Users/dw/G-Drive2T/Research_tools/.env")

import requests  # noqa: E402
from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

import pipeline  # noqa: E402

BASE = Path(__file__).parent
PILOTS = BASE / "pilots"
STATIC = BASE / "static"

VWORLD = os.environ["VWORLD_API_KEY"]

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/api/geocode")
def geocode():
    """주소 → 좌표 + 안전 BBOX(약 6.2km², 한도 10km² 내)."""
    addr = (request.args.get("addr") or "").strip()
    if not addr:
        return jsonify(error="addr 파라미터 필요"), 400

    pt = None
    for kind in ("parcel", "road"):
        r = requests.get(
            "https://api.vworld.kr/req/address",
            params={
                "service": "address", "request": "getcoord", "version": "2.0",
                "format": "json", "type": kind, "address": addr, "key": VWORLD,
            },
            timeout=20,
        ).json()
        resp = r.get("response", {})
        if resp.get("status") == "OK":
            pt = resp["result"]["point"]
            break

    if not pt:
        return jsonify(error="지오코딩 실패", detail=resp), 400

    x, y = float(pt["x"]), float(pt["y"])
    dx, dy = 0.011, 0.014
    bbox = [x - dx, y - dy, x + dx, y + dy]
    w_km = (2 * dx) * 111 * math.cos(math.radians(y))
    h_km = (2 * dy) * 111
    return jsonify(center=[x, y], bbox=bbox, area_km2=round(w_km * h_km, 2))


@app.post("/api/run")
def run():
    body = request.get_json(force=True) or {}
    try:
        sigungu = str(body["sigungu"]).strip()
        bjdong = str(body["bjdong"]).strip()
        bbox = tuple(float(x) for x in body["bbox"])
        tag = (body.get("tag") or f"{sigungu}_{bjdong}").strip()
    except (KeyError, ValueError) as e:
        return jsonify(error=f"필수 필드 누락/형식 오류: {e}"), 400

    include_unmatched = bool(body.get("include_unmatched", False))
    out_dir = PILOTS / tag
    try:
        summary = pipeline.run(sigungu, bjdong, bbox, out_dir, tag, include_unmatched)
    except Exception as e:
        return jsonify(error=str(e), traceback=traceback.format_exc()), 500

    with open(summary["out"]) as f:
        summary["geojson"] = json.load(f)
    return jsonify(summary)


@app.post("/api/run_bbox")
def run_bbox():
    """드래그 BBOX → 동 코드 자동 역추적 → 조인까지 한 호출."""
    body = request.get_json(force=True) or {}
    try:
        bbox = tuple(float(x) for x in body["bbox"])
        tag = (body.get("tag") or "bbox_session").strip()
        min_count = int(body.get("min_count", 5))
    except (KeyError, ValueError) as e:
        return jsonify(error=f"필수 필드 누락/형식 오류: {e}"), 400

    include_unmatched = bool(body.get("include_unmatched", False))
    out_dir = PILOTS / tag
    try:
        summary = pipeline.run_by_bbox(bbox, out_dir, tag, min_count, include_unmatched)
    except Exception as e:
        return jsonify(error=str(e), traceback=traceback.format_exc()), 500
    with open(summary["out"]) as f:
        summary["geojson"] = json.load(f)
    return jsonify(summary)


@app.get("/api/tags")
def list_tags():
    if not PILOTS.exists():
        return jsonify(tags=[])
    out = []
    for d in sorted(PILOTS.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        gj_files = list(d.glob("*_joined*.geojson"))
        if gj_files:
            out.append({"tag": d.name, "geojson": gj_files[-1].name})
    return jsonify(tags=out)


@app.get("/api/load")
def load_tag():
    tag = (request.args.get("tag") or "").strip()
    if not tag:
        return jsonify(error="tag 필요"), 400
    d = PILOTS / tag
    if not d.exists():
        return jsonify(error=f"태그 폴더 없음: {tag}"), 404
    candidates = sorted(d.glob("*_joined*.geojson"))
    if not candidates:
        return jsonify(error=f"GeoJSON 없음: {tag}"), 404
    with candidates[-1].open() as f:
        gj = json.load(f)
    return jsonify(tag=tag, geojson=gj, out=str(candidates[-1]))


if __name__ == "__main__":
    print(f"map3d-korea server → http://127.0.0.1:8000  (pilots: {PILOTS})")
    app.run(host="127.0.0.1", port=8000, debug=False)
