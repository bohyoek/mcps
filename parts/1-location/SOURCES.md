# 1 입지선정 — 출처

수집일: 2026-11-14

| 데이터 | 출처 | 기준 |
|---|---|---|
| 동별 빵집 점포·개폐업·프랜차이즈 | 서울 열린데이터광장 OpenAPI `VwsmAdstrdStorW` (서울시 상권분석서비스) | 2021Q1~2026Q2 |
| 동별 빵집 추정매출·객단가·시간대 | `VwsmAdstrdSelngW` | 2021Q1~2026Q2 |
| 유동인구 (시간대·연령) | `VwsmAdstrdFlpopW` | 2021Q1~2026Q2 |
| 상주인구·가구 | `VwsmAdstrdRepopW` | 2021Q1~2026Q2 |
| 직장인구 | `VwsmAdstrdWrcPopltnW` | 2021Q1~2026Q2 |
| 영업기간 (상권변화지표) | `VwsmAdstrdIxQq` | 2026Q2 |
| 2027~29 입주·신규역 | `../0-research/notes/future_changes.csv` (뉴스·서울시 발표, 출처 URL은 그 파일) | 발표일 기준 |

- 다운로드: `python parts/1-location/analysis.py` (키는 `.env`)
- 점수: `python parts/1-location/scoring.py` → `scoring.csv`, `sensitivity.csv`
