"""1. 입지선정 점수 모델 — 2029년 서울 빵집(컨셉: 아침 식사빵 기본 + 시즌 한정 메뉴 교체)

실행: 레포 루트에서  python parts/1-location/scoring.py
입력: data/dong_indicators.csv (서울시 상권분석서비스 OpenAPI), 아래 FUTURE 표 (../0-research/notes/future_changes.csv 에서 2029년까지 '확정'만)
출력: scoring.csv, sensitivity.csv
"""
import csv
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIN_STORES = 5  # 점포가 적은 동은 성장률·점포당 매출이 튀어서 제외

# 2027~2029 확정 입주 세대 (future_changes.csv, 행정동이 둘 중 하나로 '확인 필요'면 반씩 나눔)
MOVE_IN = {
    "반포본동": 5007, "중계본동": 3178, "용답동": 1670, "삼선동": 1223, "서초3동": 1161,
    "월계1동": 1516, "월계2동": 1516, "노량진1동": 1250, "노량진2동": 1250,
    "장위1동": 819, "장위2동": 819,
}
# 2027-11 개통 확정 동북선 역 인접 동 (future_changes.csv, 일부 행정동 '추정') + 위례신사선(공정률 97%, 개통일 미정 → 0.5)
STATION = {d: 1.0 for d in [
    "왕십리도선동", "행당1동", "제기동", "안암동", "종암동", "월곡1동", "길음2동", "송중동",
    "장위1동", "장위2동", "장위3동", "번1동", "월계1동", "월계2동", "하계1동", "하계2동",
    "중계본동", "중계1동", "중계4동", "중계2·3동", "중계2.3동"]}
STATION["위례동"] = 0.5

# 지표: (열 이름, 높을수록 좋음?, 가중치, 축)  — 가중치 합 100
METRICS = [
    # 수요 30: 사람이 늘고, 아침 손님·빵 주력 고객층이 많은가
    ("가구수CAGR(%/년·2021Q1→2026Q2)", True, 10, "수요"),
    ("유동인구아침비중(%·06-11시·최근4분기)", True, 10, "수요"),
    ("유동인구60대이상비중(%·최근4분기)", True, 5, "수요"),
    ("직장인구CAGR(%/년·2021Q1→2026Q2)", True, 5, "수요"),
    # 미래 변화 25: 2029년까지 확정된 변화
    ("확정입주세대(세대·2027~2029)", True, 15, "미래 변화"),
    ("신규역(1=2027 개통 확정)", True, 10, "미래 변화"),
    # 경쟁 20: 빵집이 버틸 자리가 있나
    ("상주인구1만명당제과점수(개·2026Q2)", False, 10, "경쟁"),
    ("폐업률(%·최근4분기, 평균점포수 대비)", False, 5, "경쟁"),
    ("프랜차이즈비율(%·2026Q2)", False, 5, "경쟁"),
    # 수익성 25: 남는 장사인가 (임대료는 2단계에서 후보만 확인)
    ("제과점점포당매출(원·최근4분기)", True, 10, "수익성"),
    ("제과점매출CAGR(%/년·2021Q1~2021Q4→2025Q3~2026Q2)", True, 10, "수익성"),
    ("운영점포평균영업기간(개월·2026Q2)", True, 5, "수익성"),
]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load():
    with open(HERE / "data/dong_indicators.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # 줄바꿈이 들어간 열 이름 정리
        for k in list(r):
            if "\n" in k or "\r" in k:
                r[" ".join(k.split())] = r.pop(k)
        r["확정입주세대(세대·2027~2029)"] = MOVE_IN.get(r["행정동명"], 0)
        r["신규역(1=2027 개통 확정)"] = STATION.get(r["행정동명"], 0)
    ok = [r for r in rows
          if (num(r["제과점수(개·2026Q2)"]) or 0) >= MIN_STORES
          and all(num(r[m[0]]) is not None for m in METRICS)]
    return rows, ok


def pct_rank(vals, higher):
    """0~100 백분위 점수. 동점은 평균 순위. 낮을수록 좋은 지표는 뒤집음. 극단값에 덜 흔들리도록 순위 사용."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    n = len(vals) - 1 or 1
    s = [r / n * 100 for r in ranks]
    return s if higher else [100 - x for x in s]


def score(ok, weights):
    pts = {}
    for (col, higher, _, _), w in zip(METRICS, weights):
        pts[col] = pct_rank([num(r[col]) for r in ok], higher)
    total = [sum(pts[m[0]][i] * w for m, w in zip(METRICS, weights)) / sum(weights) for i in range(len(ok))]
    return pts, total


def main():
    rows, ok = load()
    base_w = [m[2] for m in METRICS]
    assert sum(base_w) == 100
    pts, total = score(ok, base_w)
    order = sorted(range(len(ok)), key=lambda i: -total[i])

    axes = ["수요", "미래 변화", "경쟁", "수익성"]
    out = []
    for rank, i in enumerate(order, 1):
        r = ok[i]
        axis_pts = {a: round(sum(pts[m[0]][i] * m[2] for m in METRICS if m[3] == a)
                             / sum(m[2] for m in METRICS if m[3] == a), 1) for a in axes}
        out.append([rank, r["행정동코드"], r["자치구"], r["행정동명"], round(total[i], 1)]
                   + [axis_pts[a] for a in axes] + [r[m[0]] for m in METRICS])
    with open(HERE / "scoring.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["순위", "행정동코드", "자치구", "행정동명", "총점(0-100)"]
                   + [f"{a}점수(0-100)" for a in axes]
                   + [f"{m[0]} [가중치 {m[2]}]" for m in METRICS])
        w.writerows(out)

    # 민감도: 각 가중치를 ±30% 안에서 무작위로 흔들어 1000번
    random.seed(2029)
    top1, top5 = {}, {}
    for _ in range(1000):
        ws = [b * random.uniform(0.7, 1.3) for b in base_w]
        _, t = score(ok, ws)
        o = sorted(range(len(ok)), key=lambda i: -t[i])
        top1[ok[o[0]]["행정동명"]] = top1.get(ok[o[0]]["행정동명"], 0) + 1
        for i in o[:5]:
            top5[ok[i]["행정동명"]] = top5.get(ok[i]["행정동명"], 0) + 1
    with open(HERE / "sensitivity.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["행정동명", "1위 횟수(회/1000)", "5위 안 횟수(회/1000)"])
        for d in sorted(top5, key=lambda d: -top5[d]):
            w.writerow([d, top1.get(d, 0), top5[d]])

    print(f"전체 {len(rows)}개 동 중 대상 {len(ok)}개 (제과점 {MIN_STORES}개 이상·결측 없음)")
    for row in out[:12]:
        print(row[:9])
    print("민감도 1위:", sorted(top1.items(), key=lambda x: -x[1])[:5])
    print("민감도 5위 안:", sorted(top5.items(), key=lambda x: -x[1])[:8])


if __name__ == "__main__":
    main()
