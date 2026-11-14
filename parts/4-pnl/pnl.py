"""4. 손익 시뮬레이션 — 2029년 하계1동 15평 빵집 (빵·디저트 반반)

실행: 레포 루트에서  python parts/4-pnl/pnl.py   → pnl.csv
모든 값은 만원. 근거는 각 줄 주석과 ../1-location/for-pnl.csv, ../0-research/notes/costs_for-pnl.csv
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

BASE_SALES = 21988.6  # 하계1동 빵집 점포당 연매출 (만원, 2025Q3~2026Q2, 서울시 상권분석서비스)
SCENARIOS = {
    # 이름: (연매출 증가율, 한정 메뉴 효과, 원가율)
    "비관": (-0.014, 0.0, 0.407),  # 서울 중간 증가율 −1.4%/년, 한정 메뉴 실패, 외식업 식재료비 40.7%(2024)
    "기본": (0.102, 0.0, 0.34),    # 하계1동 증가율 +10.2%/년 (5년 CAGR 규칙), 원가율 34%(가정)
    "낙관": (0.102, 0.20, 0.30),   # 기본 + 한정 메뉴 성공 시 +20%(가정), 원가율 30%
}
YEARS = 3  # 2026 → 2029

AREA = 15                      # 평 (2번)
RENT_PER_PYEONG = 8.0          # 만원/3.3㎡·월, 2029 환산 (R-ONE 상계역 상권 대용)
WAGE_HOUR = 11386 / 10000      # 만원/시간, 2029 최저임금 추정
STAFF_HOURS = 209 * 2.5        # 제빵 1명 + 판매 1명 + 파트 0.5명 (주휴 포함 209시간 기준, 7시 오픈·빵·디저트 동시 생산 고려). 사장 본인 인건비는 제외
INSURANCE = 0.10               # 4대보험 등 사업주 부담 (가정)
UTILITIES = 80                 # 만원/월, 오븐 전기·가스·수도 (가정, 미확인)
OTHER_RATE = 0.05              # 포장·소모품·마케팅, 매출의 5% (가정)

INVEST = {                     # 만원
    "보증금": AREA * RENT_PER_PYEONG * 12.8,  # 월세 12.8개월 (서울시 상가임대차 실태조사 2023)
    "권리금": 5497,             # 서울 음식점업 평균 2029 환산 (노원은 더 낮을 수 있음)
    "인테리어": AREA * 220,     # 평당 220만원 2029 환산 (추정)
    "설비": 4500,               # 2,000~7,000만원 범위 중간 (추정)
    "초도재료·기타": 500,       # 가정
}


def card_rate(annual):  # 금융위 우대수수료율 2025.2.14~ (신용, 만원 기준 연매출)
    return 0.004 if annual <= 30000 else 0.010 if annual <= 50000 else 0.0115


def main():
    invest_total = sum(INVEST.values())
    sunk = invest_total - INVEST["보증금"]  # 보증금은 돌려받으므로 회수 대상에서 뺌
    rows = []
    for name, (g, hook, cogs) in SCENARIOS.items():
        annual = BASE_SALES * (1 + g) ** YEARS * (1 + hook)
        m = annual / 12
        cost = {
            "재료비": m * cogs,
            "임대료": AREA * RENT_PER_PYEONG,
            "인건비": WAGE_HOUR * STAFF_HOURS * (1 + INSURANCE),
            "공과금": UTILITIES,
            "카드수수료": m * card_rate(annual),
            "기타": m * OTHER_RATE,
        }
        profit = m - sum(cost.values())
        fixed = cost["임대료"] + cost["인건비"] + cost["공과금"]
        var_rate = cogs + card_rate(annual) + OTHER_RATE
        bep_month = fixed / (1 - var_rate)
        rows.append({
            "시나리오": name,
            "연매출(만원)": round(annual),
            "월매출(만원)": round(m),
            **{f"{k}(만원/월)": round(v) for k, v in cost.items()},
            "월영업이익(만원·사장 인건비 전)": round(profit),
            "영업이익률(%)": round(profit / m * 100, 1),
            "손익분기 월매출(만원)": round(bep_month),
            "손익분기 하루손님(명·객단가 14,730원·월30일)": round(bep_month * 10000 / 14730 / 30),
            "투자회수(개월·보증금 제외)": round(sunk / profit, 1) if profit > 0 else "회수 불가",
        })
    with open(HERE / "pnl.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print("초기투자", {k: round(v) for k, v in INVEST.items()}, "합계", round(invest_total), "회수대상", round(sunk))
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
