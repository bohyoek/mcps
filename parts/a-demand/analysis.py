"""A 수요: 서울시 상권분석서비스(길단위인구-행정동) API로 시간대·요일·연령대 유동인구 CSV를 만든다.

실행: 레포 루트에서  python parts/a-demand/analysis.py
필요: 레포 루트 .env 에 SEOUL_OPENAPI_KEY=... (커밋 금지)
"""
import csv
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SVC = "VwsmAdstrdFlpopW"
DONGS = {"11170625": "한강로동", "11200670": "성수2가1동", "11200690": "성수2가3동"}


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("SEOUL_OPENAPI_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env 에 SEOUL_OPENAPI_KEY 가 없습니다")


def fetch(key):
    rows, start = [], 1
    while True:
        url = f"http://openapi.seoul.go.kr:8088/{key}/json/{SVC}/{start}/{start + 999}/"
        data = json.load(urllib.request.urlopen(url, timeout=60))[SVC]
        page = data.get("row", [])
        rows += [r for r in page if r["ADSTRD_CD"] in DONGS]
        start += 1000
        if start > data["list_total_count"] or not page:
            return rows


def write(name, header, body):
    with open(HERE / name, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(body)


def share(row, cols):
    total = sum(row[c] for c in cols)
    return [round(row[c] / total * 100, 1) for c in cols]


def main():
    rows = fetch(load_key())
    rows.sort(key=lambda r: (r["STDR_YYQU_CD"], r["ADSTRD_CD"]))

    raw_cols = list(rows[0].keys())
    write("data/api_길단위인구_행정동_원본.csv", raw_cols, [[r[c] for c in raw_cols] for r in rows])

    latest = max(r["STDR_YYQU_CD"] for r in rows)
    last = {r["ADSTRD_CD"]: r for r in rows if r["STDR_YYQU_CD"] == latest}
    names = [DONGS[c] for c in DONGS]

    time_cols = ["TMZON_00_06_FLPOP_CO", "TMZON_06_11_FLPOP_CO", "TMZON_11_14_FLPOP_CO",
                 "TMZON_14_17_FLPOP_CO", "TMZON_17_21_FLPOP_CO", "TMZON_21_24_FLPOP_CO"]
    time_labels = ["00-06시", "06-11시", "11-14시", "14-17시", "17-21시", "21-24시"]
    day_cols = ["MON_FLPOP_CO", "TUES_FLPOP_CO", "WED_FLPOP_CO", "THUR_FLPOP_CO",
                "FRI_FLPOP_CO", "SAT_FLPOP_CO", "SUN_FLPOP_CO"]
    day_labels = ["월", "화", "수", "목", "금", "토", "일"]
    age_cols = ["AGRDE_10_FLPOP_CO", "AGRDE_20_FLPOP_CO", "AGRDE_30_FLPOP_CO",
                "AGRDE_40_FLPOP_CO", "AGRDE_50_FLPOP_CO", "AGRDE_60_ABOVE_FLPOP_CO"]
    age_labels = ["10대", "20대", "30대", "40대", "50대", "60대 이상"]

    for fname, cols, labels, col_name in [
        (f"for-video/06_시간대별_유동인구비율_{latest}.csv", time_cols, time_labels, "시간대"),
        (f"for-video/07_요일별_유동인구비율_{latest}.csv", day_cols, day_labels, "요일"),
        (f"for-video/08_연령대별_유동인구비율_{latest}.csv", age_cols, age_labels, "연령대"),
    ]:
        shares = {c: share(last[c], cols) for c in DONGS}
        write(fname, [col_name] + [f"{n}(%)" for n in names],
              [[lab] + [shares[c][i] for c in DONGS] for i, lab in enumerate(labels)])

    quarters = sorted({r["STDR_YYQU_CD"] for r in rows})
    by = {(r["STDR_YYQU_CD"], r["ADSTRD_CD"]): r["TOT_FLPOP_CO"] for r in rows}
    write("for-video/09_분기별_총유동인구.csv", ["기준분기"] + [f"{n}(명·분기누적)" for n in names],
          [[f"{q[:4]}Q{q[4]}"] + [int(by[(q, c)]) for c in DONGS] for q in quarters])

    print("최신 분기", latest, "/ 행", len(rows))
    for c in DONGS:
        r = last[c]
        print(DONGS[c], "총", int(r["TOT_FLPOP_CO"]),
              "시간대", share(r, time_cols), "요일", share(r, day_cols), "연령", share(r, age_cols),
              "여성", round(r["FML_FLPOP_CO"] / r["TOT_FLPOP_CO"] * 100, 1))


if __name__ == "__main__":
    main()
