"""1-location: 서울시 상권분석서비스(행정동) 데이터 수집 + 제과점(CS100005) 지표표 생성.

사용법 (레포 루트 어디서든):
    python parts/1-location/analysis.py download   # API에서 받아 data/*.csv로 저장 (이미 있으면 건너뜀)
    python parts/1-location/analysis.py download --refresh
    python parts/1-location/analysis.py process    # data/*.csv -> dong_indicators.csv, 서울 전체 추세표
    python parts/1-location/analysis.py all

- API 키는 레포 루트 .env 의 SEOUL_OPENAPI_KEY 에서만 읽는다. 키를 출력·저장하지 않는다.
- 호출 형식: http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/ (최대 1000건)
- 필터 인자가 무시되므로 전부 페이지로 받아 코드에서 CS100005만 남긴다.
- 표준 라이브러리만 사용 (pandas 없음).
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / "data"
BAKERY = "CS100005"
BASE = "http://openapi.seoul.go.kr:8088"
PAGE = 1000
WORKERS = 4  # 동시 호출 수를 작게 유지 (서버 부담 최소화)

# 서비스명 -> (저장 파일, 행 필터)
SERVICES = {
    "VwsmAdstrdStorW": ("stor_bakery.csv", lambda r: r.get("SVC_INDUTY_CD") == BAKERY),
    "VwsmAdstrdSelngW": ("selng_bakery.csv", lambda r: r.get("SVC_INDUTY_CD") == BAKERY),
    "VwsmAdstrdFlpopW": ("flpop.csv", None),
    "VwsmAdstrdRepopW": ("repop.csv", None),
    "VwsmAdstrdWrcPopltnW": ("wrcpop.csv", None),
    "VwsmAdstrdIxQq": ("change_ix.csv", None),
    "VwsmAdstrdFcltyW": ("facility.csv", None),
    "VwsmAdstrdAptW": ("apt.csv", None),
    "VwsmAdstrdNcmCnsmpW": ("income_cnsmp.csv", None),
    "VwsmSignguIxQq": ("signgu_ix.csv", None),  # 구 코드 -> 구 이름 매핑용
}


# ---------------------------------------------------------------- download
def _key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("SEOUL_OPENAPI_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("SEOUL_OPENAPI_KEY not found in .env")


def fetch(key: str, service: str, start: int, end: int, tries: int = 4) -> dict:
    url = f"{BASE}/{key}/json/{service}/{start}/{end}/"
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            if service in d:
                return d[service]
            code = d.get("RESULT", {}).get("CODE", "?")
            if code == "INFO-200":  # 데이터 없음
                return {"list_total_count": 0, "row": []}
            last = f"API {code}"
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__  # 예외 메시지에는 URL(키)이 들어갈 수 있어 출력하지 않음
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{service} {start}-{end} failed: {last}")


def download(service: str, out_name: str, keep, refresh: bool = False) -> None:
    out = DATA / out_name
    if out.exists() and not refresh:
        print(f"[skip] {out_name} exists")
        return
    key = _key()
    total = int(fetch(key, service, 1, 1)["list_total_count"])
    ranges = [(s, min(s + PAGE - 1, total)) for s in range(1, total + 1, PAGE)]
    print(f"[get] {service}: {total:,} rows, {len(ranges)} pages", flush=True)
    rows, done = [], 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for part in ex.map(lambda r: fetch(key, service, *r)["row"], ranges):
            rows.extend(x for x in part if keep is None or keep(x))
            done += 1
            if done % 50 == 0:
                print(f"  {service}: {done}/{len(ranges)} pages", flush=True)
    if not rows:
        raise RuntimeError(f"{service}: no rows kept")
    fields = list(rows[0].keys())
    rows.sort(key=lambda r: (r.get("STDR_YYQU_CD", ""), r.get("ADSTRD_CD", r.get("SIGNGU_CD", ""))))
    DATA.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[ok] {out_name}: kept {len(rows):,} of {total:,} rows", flush=True)


def download_all(refresh: bool = False) -> None:
    # 작은 서비스부터
    order = sorted(SERVICES, key=lambda s: s in ("VwsmAdstrdStorW", "VwsmAdstrdSelngW"))
    for svc in order:
        name, keep = SERVICES[svc]
        download(svc, name, keep, refresh)


# ---------------------------------------------------------------- helpers
def read(name: str) -> list[dict]:
    with (DATA / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def q_index(q: str) -> int:
    return int(q[:4]) * 4 + int(q[4]) - 1


def q_label(q: str) -> str:
    return f"{q[:4]}Q{q[4]}"


def cagr(first: float, last: float, years: float):
    if not first or first <= 0 or last is None or last < 0 or years <= 0:
        return None
    return ((last / first) ** (1 / years) - 1) * 100


def by_dong_q(rows: list[dict], code_field: str = "ADSTRD_CD") -> dict:
    out = {}
    for r in rows:
        out[(r[code_field], r["STDR_YYQU_CD"])] = r
    return out


def rnd(x, n=1):
    return None if x is None else round(x, n)


# ---------------------------------------------------------------- process
def process() -> None:
    stor, selng, flpop = read("stor_bakery.csv"), read("selng_bakery.csv"), read("flpop.csv")
    repop, wrc = read("repop.csv"), read("wrcpop.csv")
    ix, fac, apt, ncm = read("change_ix.csv"), read("facility.csv"), read("apt.csv"), read("income_cnsmp.csv")
    gu = {r["SIGNGU_CD"]: r["SIGNGU_CD_NM"] for r in read("signgu_ix.csv")}

    S, M, F = by_dong_q(stor), by_dong_q(selng), by_dong_q(flpop)
    R, W, X = by_dong_q(repop), by_dong_q(wrc), by_dong_q(ix)
    FC, A, N = by_dong_q(fac), by_dong_q(apt), by_dong_q(ncm)

    quarters = sorted({r["STDR_YYQU_CD"] for r in stor})
    lq = quarters[-1]
    last4 = quarters[-4:]
    first4 = quarters[:4]
    span_q = q_index(last4[-1]) - q_index(first4[-1])  # 롤링 4분기 창 간 거리(분기)
    span_y = span_q / 4
    q_span_y = (q_index(lq) - q_index(quarters[0])) / 4

    def latest_q(rows):
        return sorted({r["STDR_YYQU_CD"] for r in rows})[-1]

    def first_q(rows):
        return sorted({r["STDR_YYQU_CD"] for r in rows})[0]

    rq_l, rq_f = latest_q(repop), first_q(repop)
    wq_l, wq_f = latest_q(wrc), first_q(wrc)
    xq, fq, aq, nq = latest_q(ix), latest_q(fac), latest_q(apt), latest_q(ncm)

    # 동 목록 & 이름 (가장 최근 이름 사용)
    names = {}
    for rows in (flpop, stor, repop):
        for r in sorted(rows, key=lambda r: r["STDR_YYQU_CD"]):
            names[r["ADSTRD_CD"]] = r["ADSTRD_CD_NM"]
    dongs_latest = {r["ADSTRD_CD"] for r in flpop if r["STDR_YYQU_CD"] == latest_q(flpop)}
    dongs = sorted(dongs_latest | {r["ADSTRD_CD"] for r in stor if r["STDR_YYQU_CD"] == lq})

    L = q_label
    out = []
    for d in dongs:
        row = {"행정동코드": d, "행정동명": names.get(d, ""), "자치구": gu.get(d[:5], "")}
        s = S.get((d, lq))
        stores = num(s["SIMILR_INDUTY_STOR_CO"]) if s else 0.0
        frc = num(s["FRC_STOR_CO"]) if s else 0.0
        row[f"제과점수(개·{L(lq)})"] = stores
        row[f"프랜차이즈제과점수(개·{L(lq)})"] = frc
        row[f"프랜차이즈비율(%·{L(lq)})"] = rnd(frc / stores * 100) if stores else None
        opn = sum(num(S[(d, q)]["OPBIZ_STOR_CO"]) for q in last4 if (d, q) in S)
        cls = sum(num(S[(d, q)]["CLSBIZ_STOR_CO"]) for q in last4 if (d, q) in S)
        avg_st = sum(num(S[(d, q)]["SIMILR_INDUTY_STOR_CO"]) for q in last4 if (d, q) in S) / 4
        row["개업점포수(개·최근4분기합)"] = opn
        row["폐업점포수(개·최근4분기합)"] = cls
        row["개업률(%·최근4분기, 평균점포수 대비)"] = rnd(opn / avg_st * 100) if avg_st else None
        row["폐업률(%·최근4분기, 평균점포수 대비)"] = rnd(cls / avg_st * 100) if avg_st else None
        s0 = S.get((d, quarters[0]))
        row[f"제과점수CAGR(%/년·{L(quarters[0])}→{L(lq)})"] = rnd(
            cagr(num(s0["SIMILR_INDUTY_STOR_CO"]) if s0 else None, stores, q_span_y))

        # 매출
        sales4 = sum(num(M[(d, q)]["THSMON_SELNG_AMT"]) for q in last4 if (d, q) in M)
        cnt4 = sum(num(M[(d, q)]["THSMON_SELNG_CO"]) for q in last4 if (d, q) in M)
        morn4 = sum(num(M[(d, q)]["TMZON_06_11_SELNG_AMT"]) for q in last4 if (d, q) in M)
        wkend4 = sum(num(M[(d, q)]["WKEND_SELNG_AMT"]) for q in last4 if (d, q) in M)
        per_store = 0.0
        ok = False
        for q in last4:
            if (d, q) in M and (d, q) in S and num(S[(d, q)]["SIMILR_INDUTY_STOR_CO"]) > 0:
                per_store += num(M[(d, q)]["THSMON_SELNG_AMT"]) / num(S[(d, q)]["SIMILR_INDUTY_STOR_CO"])
                ok = True
        sales_first4 = sum(num(M[(d, q)]["THSMON_SELNG_AMT"]) for q in first4 if (d, q) in M)
        full_first = all((d, q) in M for q in first4)
        row["제과점매출(원·최근4분기)"] = round(sales4) if sales4 else None
        row["제과점점포당매출(원·최근4분기)"] = round(per_store) if ok else None
        row["제과점매출건수(건·최근4분기)"] = round(cnt4) if cnt4 else None
        row["제과점객단가(원/건·최근4분기)"] = round(sales4 / cnt4) if cnt4 else None
        row["제과점아침매출비중(%·06-11시·최근4분기)"] = rnd(morn4 / sales4 * 100) if sales4 else None
        row["제과점주말매출비중(%·최근4분기)"] = rnd(wkend4 / sales4 * 100) if sales4 else None
        row[f"제과점매출CAGR(%/년·{L(first4[0])}~{L(first4[-1])}→{L(last4[0])}~{L(last4[-1])})"] = rnd(
            cagr(sales_first4, sales4, span_y)) if full_first and all((d, q) in M for q in last4) else None

        # 유동인구
        fl4 = [F[(d, q)] for q in last4 if (d, q) in F]
        fl_first = [F[(d, q)] for q in first4 if (d, q) in F]
        tot4 = sum(num(r["TOT_FLPOP_CO"]) for r in fl4)
        row["유동인구(명·최근4분기 합계)"] = round(tot4) if fl4 else None
        row[f"유동인구CAGR(%/년·{L(first4[0])}~{L(first4[-1])}→{L(last4[0])}~{L(last4[-1])})"] = rnd(
            cagr(sum(num(r["TOT_FLPOP_CO"]) for r in fl_first), tot4, span_y)) if len(fl4) == 4 and len(fl_first) == 4 else None
        if tot4:
            row["유동인구아침비중(%·06-11시·최근4분기)"] = rnd(sum(num(r["TMZON_06_11_FLPOP_CO"]) for r in fl4) / tot4 * 100)
            row["유동인구저녁비중(%·17-21시·최근4분기)"] = rnd(sum(num(r["TMZON_17_21_FLPOP_CO"]) for r in fl4) / tot4 * 100)
            for a, lab in (("10", "10대"), ("20", "20대"), ("30", "30대"), ("40", "40대"), ("50", "50대"), ("60_ABOVE", "60대이상")):
                row[f"유동인구{lab}비중(%·최근4분기)"] = rnd(sum(num(r[f"AGRDE_{a}_FLPOP_CO"]) for r in fl4) / tot4 * 100)

        # 상주인구 / 가구
        r_l, r_f = R.get((d, rq_l)), R.get((d, rq_f))
        ry = (q_index(rq_l) - q_index(rq_f)) / 4
        pop = num(r_l["TOT_REPOP_CO"]) if r_l else None
        row[f"상주인구(명·{L(rq_l)})"] = pop
        row[f"상주인구CAGR(%/년·{L(rq_f)}→{L(rq_l)})"] = rnd(cagr(num(r_f["TOT_REPOP_CO"]) if r_f else None, pop, ry)) if r_l else None
        row[f"가구수(가구·{L(rq_l)})"] = num(r_l["TOT_HSHLD_CO"]) if r_l else None
        # repop의 APT_HSHLD_CO는 최신 분기에 전부 0이라 쓰지 않고, VwsmAdstrdAptW 면적별 세대수 합을 쓴다
        row[f"가구수CAGR(%/년·{L(rq_f)}→{L(rq_l)})"] = rnd(cagr(num(r_f["TOT_HSHLD_CO"]) if r_f else None, num(r_l["TOT_HSHLD_CO"]), ry)) if r_l else None
        if r_l and pop:
            row[f"상주인구30-40대비중(%·{L(rq_l)})"] = rnd((num(r_l["AGRDE_30_REPOP_CO"]) + num(r_l["AGRDE_40_REPOP_CO"])) / pop * 100)
        row[f"상주인구1만명당제과점수(개·{L(lq)})"] = rnd(stores / pop * 10000, 2) if pop else None

        # 직장인구
        w_l, w_f = W.get((d, wq_l)), W.get((d, wq_f))
        wy = (q_index(wq_l) - q_index(wq_f)) / 4
        row[f"직장인구(명·{L(wq_l)})"] = num(w_l["TOT_WRC_POPLTN_CO"]) if w_l else None
        row[f"직장인구CAGR(%/년·{L(wq_f)}→{L(wq_l)})"] = rnd(cagr(num(w_f["TOT_WRC_POPLTN_CO"]) if w_f else None, num(w_l["TOT_WRC_POPLTN_CO"]), wy)) if w_l else None

        # 기타 맥락 지표
        x = X.get((d, xq))
        row[f"상권변화지표({L(xq)})"] = x["TRDAR_CHNGE_IX_NM"] if x else None
        row[f"운영점포평균영업기간(개월·{L(xq)})"] = num(x["OPR_SALE_MT_AVRG"]) if x else None
        row[f"폐업점포평균영업기간(개월·{L(xq)})"] = num(x["CLS_SALE_MT_AVRG"]) if x else None
        fc = FC.get((d, fq))
        row[f"지하철역수(개·{L(fq)})"] = num(fc["SUBWAY_STATN_CO"]) if fc else None
        row[f"버스정류장수(개·{L(fq)})"] = num(fc["BUS_STTN_CO"]) if fc else None
        a = A.get((d, aq))
        row[f"아파트평균시가(원·{L(aq)})"] = num(a["AVRG_MKTC"]) if a else None
        row[f"아파트세대수(세대·{L(aq)})"] = sum(num(a[k]) for k in (
            "AE_66_SQMT_BELO_HSHLD_CO", "AE_66_SQMT_HSHLD_CO", "AE_99_SQMT_HSHLD_CO",
            "AE_132_SQMT_HSHLD_CO", "AE_165_SQMT_HSHLD_CO")) if a else None
        # 주의: 이 세대수의 2021→2026 증감은 신축 입주(예: 개포2동)를 반영하지 않고 거의 모든 동에서 감소로 나와
        # 증감 지표로는 쓰지 않는다. 수준값도 참고용.
        n = N.get((d, nq))
        row[f"지출총액(원·{L(nq)})"] = num(n["EXPNDTR_TOTAMT"]) if n else None
        row[f"식료품지출(원·{L(nq)})"] = num(n["FD_EXPNDTR_TOTAMT"]) if n else None
        out.append(row)

    fields = list(dict.fromkeys(k for r in out for k in r))
    with (DATA / "dong_indicators.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)
    print(f"[ok] dong_indicators.csv: {len(out)} dongs, {len(fields)} cols, latest store quarter {lq}")
    print(f"     store quarters {quarters[0]}..{lq} ({len(quarters)}), sales quarters "
          f"{sorted({r['STDR_YYQU_CD'] for r in selng})[0]}..{sorted({r['STDR_YYQU_CD'] for r in selng})[-1]} "
          f"({len({r['STDR_YYQU_CD'] for r in selng})}), repop {rq_f}..{rq_l}, wrc {wq_f}..{wq_l}, "
          f"ix {xq}, fac {fq}, apt {aq}, ncm {nq}")
    seoul_trend(stor, selng, flpop, quarters)


def seoul_trend(stor, selng, flpop, quarters) -> None:
    """서울 전체 제과점 분기·연도 추세표."""
    q_st = defaultdict(lambda: defaultdict(float))
    has_sales = {(r["ADSTRD_CD"], r["STDR_YYQU_CD"]) for r in selng}
    for r in stor:
        if (r["ADSTRD_CD"], r["STDR_YYQU_CD"]) in has_sales:
            q_st[r["STDR_YYQU_CD"]]["stores_matched"] += num(r["SIMILR_INDUTY_STOR_CO"])
        t = q_st[r["STDR_YYQU_CD"]]
        t["stores"] += num(r["SIMILR_INDUTY_STOR_CO"])
        t["stor_co"] += num(r["STOR_CO"])
        t["frc"] += num(r["FRC_STOR_CO"])
        t["open"] += num(r["OPBIZ_STOR_CO"])
        t["close"] += num(r["CLSBIZ_STOR_CO"])
        t["dongs_with_bakery"] += 1 if num(r["SIMILR_INDUTY_STOR_CO"]) > 0 else 0
    for r in selng:
        t = q_st[r["STDR_YYQU_CD"]]
        t["sales"] += num(r["THSMON_SELNG_AMT"])
        t["cnt"] += num(r["THSMON_SELNG_CO"])
        t["morning"] += num(r["TMZON_06_11_SELNG_AMT"])
        t["wkend"] += num(r["WKEND_SELNG_AMT"])
        t["sales_dongs"] += 1
        for a in ("10", "20", "30", "40", "50", "60_ABOVE"):
            t[f"age_{a}"] += num(r[f"AGRDE_{a}_SELNG_AMT"])
    for r in flpop:
        q_st[r["STDR_YYQU_CD"]]["flpop"] += num(r["TOT_FLPOP_CO"])

    qrows = []
    for q in sorted(q_st):
        t = q_st[q]
        age_tot = sum(t[f"age_{a}"] for a in ("10", "20", "30", "40", "50", "60_ABOVE"))
        qrows.append({
            "분기": q_label(q),
            "제과점수(개)": round(t["stores"]),
            "일반점포수(개)": round(t["stor_co"]),
            "프랜차이즈점포수(개)": round(t["frc"]),
            "프랜차이즈비율(%)": rnd(t["frc"] / t["stores"] * 100) if t["stores"] else None,
            "개업점포수(개·분기)": round(t["open"]),
            "폐업점포수(개·분기)": round(t["close"]),
            "제과점있는행정동수(개)": round(t["dongs_with_bakery"]),
            "제과점매출(억원·분기)": rnd(t["sales"] / 1e8) if t["sales"] else None,
            "점포당매출(만원·분기, 매출집계동 점포 기준)": rnd(t["sales"] / t["stores_matched"] / 1e4) if t["stores_matched"] else None,
            "매출집계동 점포수(개)": round(t["stores_matched"]),
            "매출건수(만건·분기)": rnd(t["cnt"] / 1e4) if t["cnt"] else None,
            "객단가(원/건)": round(t["sales"] / t["cnt"]) if t["cnt"] else None,
            "아침매출비중(%·06-11시)": rnd(t["morning"] / t["sales"] * 100) if t["sales"] else None,
            "주말매출비중(%)": rnd(t["wkend"] / t["sales"] * 100) if t["sales"] else None,
            "20-30대매출비중(%)": rnd((t["age_20"] + t["age_30"]) / age_tot * 100) if age_tot else None,
            "60대이상매출비중(%)": rnd(t["age_60_ABOVE"] / age_tot * 100) if age_tot else None,
            "매출데이터행정동수(개)": round(t["sales_dongs"]),
            "유동인구(억명·분기합계)": rnd(t["flpop"] / 1e8, 2) if t["flpop"] else None,
        })
    write_rows(DATA / "seoul_bakery_quarterly.csv", qrows)

    # 연도표: 점포수는 해당 연도 마지막 분기, 흐름(개폐업·매출)은 연간 합, 비율은 연평균점포 대비
    years = sorted({q[:4] for q in q_st})
    yrows = []
    for y in years:
        qs = [q for q in sorted(q_st) if q[:4] == y]
        tl = q_st[qs[-1]]
        avg = sum(q_st[q]["stores"] for q in qs) / len(qs)
        avg_m = sum(q_st[q]["stores_matched"] for q in qs) / len(qs)
        per_store = sum(q_st[q]["sales"] / q_st[q]["stores_matched"] for q in qs if q_st[q]["stores_matched"])
        op = sum(q_st[q]["open"] for q in qs)
        cl = sum(q_st[q]["close"] for q in qs)
        sa = sum(q_st[q]["sales"] for q in qs)
        cn = sum(q_st[q]["cnt"] for q in qs)
        yrows.append({
            "연도": y + ("" if len(qs) == 4 else f"(Q1-Q{qs[-1][4]}만)"),
            "분기수": len(qs),
            "제과점수(개·연말분기)": round(tl["stores"]),
            "프랜차이즈비율(%·연말분기)": rnd(tl["frc"] / tl["stores"] * 100),
            "개업점포수(개·연간합)": round(op),
            "폐업점포수(개·연간합)": round(cl),
            "개업률(%·연평균점포대비)": rnd(op / avg * 100),
            "폐업률(%·연평균점포대비)": rnd(cl / avg * 100),
            "순증(개·개업-폐업)": round(op - cl),
            "제과점매출(억원·연간합)": rnd(sa / 1e8),
            "점포당매출(만원·연간, 분기별 매출÷매출집계동 점포수의 합)": rnd(per_store / 1e4),
            "매출집계동 점포수(개·연평균)": round(avg_m),
            "객단가(원/건)": round(sa / cn) if cn else None,
            "매출건수(만건·연간합)": rnd(cn / 1e4),
            "아침매출비중(%·06-11시)": rnd(sum(q_st[q]["morning"] for q in qs) / sa * 100),
            "주말매출비중(%)": rnd(sum(q_st[q]["wkend"] for q in qs) / sa * 100),
            "20-30대매출비중(%)": rnd(sum(q_st[q]["age_20"] + q_st[q]["age_30"] for q in qs)
                                 / sum(q_st[q][f"age_{a}"] for q in qs for a in ("10", "20", "30", "40", "50", "60_ABOVE")) * 100),
            "60대이상매출비중(%)": rnd(sum(q_st[q]["age_60_ABOVE"] for q in qs)
                                 / sum(q_st[q][f"age_{a}"] for q in qs for a in ("10", "20", "30", "40", "50", "60_ABOVE")) * 100),
            "유동인구(억명·연간합계)": rnd(sum(q_st[q]["flpop"] for q in qs) / 1e8, 2),
        })
    write_rows(DATA / "seoul_bakery_yearly.csv", yrows)
    for r in yrows:
        print(r)


def rankings(top: int = 15, min_stores: int = 3) -> None:
    """dong_indicators.csv 원값 순위 (가중치 없음). 점포당·비율 지표는 점포 min_stores개 이상 동만."""
    with (DATA / "dong_indicators.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys())
    st_col = next(c for c in cols if c.startswith("제과점수("))

    def col(prefix):
        return next(c for c in cols if c.startswith(prefix))

    specs = [  # (지표 열, 점포 하한 적용 여부)
        (st_col, False),
        (col("제과점매출(원"), False),
        (col("제과점점포당매출"), True),
        (col("제과점매출CAGR"), True),
        (col("제과점수CAGR"), True),
        (col("유동인구(명"), False),
        (col("유동인구CAGR"), False),
        (col("제과점아침매출비중"), True),
        (col("상주인구CAGR"), False),
        (col("가구수CAGR"), False),
        (col("직장인구CAGR"), False),
    ]
    out = []
    for c, need in specs:
        cand = [r for r in rows if r[c] not in ("", None)
                and (not need or num(r[st_col]) >= min_stores)]
        cand.sort(key=lambda r: num(r[c]), reverse=True)
        for i, r in enumerate(cand[:top], 1):
            out.append({"지표": c, "필터": f"제과점 {min_stores}개 이상" if need else "전체",
                        "순위": i, "행정동코드": r["행정동코드"], "자치구": r["자치구"],
                        "행정동명": r["행정동명"], "값": r[c], st_col: r[st_col]})
    write_rows(DATA / "dong_rankings_top15.csv", out)


def write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[ok] {path.name}: {len(rows)} rows")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    refresh = "--refresh" in sys.argv
    if cmd in ("download", "all"):
        download_all(refresh)
    if cmd in ("process", "all"):
        process()
        rankings()
