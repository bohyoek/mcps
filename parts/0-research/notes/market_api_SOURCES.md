# market_api.md 출처

- 호출일: **2026-11-14**
- 호출 형식: `http://openapi.seoul.go.kr:8088/{인증키}/json/{서비스명}/{시작}/{끝}/` (1,000건씩 전체 페이지 수집 → 코드에서 필터)
- 인증키: 레포 루트 `.env`의 `SEOUL_OPENAPI_KEY` (파일·로그에 남기지 않음)
- 수집·가공 코드: `parts/1-location/analysis.py` (`download` → `process`)
- 제공처: 서울 열린데이터광장 — 서울시 상권분석서비스 (https://data.seoul.go.kr , 웹 화면 https://golmok.seoul.go.kr)

## 사용한 서비스 (모두 행정동 단위, 2021Q1–2026Q2)

| # | 서비스명 | 내용 | 전체 행 | 저장 파일 (`parts/1-location/data/`) | 저장 행 |
|---|---|---|---|---|---|
| 1 | `VwsmAdstrdStorW` | 점포 (점포 수, 프랜차이즈, 개·폐업) | 775,084 | `stor_bakery.csv` (CS100005만) | 9,283 |
| 2 | `VwsmAdstrdSelngW` | 추정매출 (분기 매출·건수, 시간대·요일·성별·연령) | 376,485 | `selng_bakery.csv` (CS100005만) | 8,353 |
| 3 | `VwsmAdstrdFlpopW` | 유동인구 (총량, 시간대, 요일, 연령) | 9,350 | `flpop.csv` | 9,350 |
| 4 | `VwsmAdstrdRepopW` | 상주인구·가구 | 9,350 | `repop.csv` | 9,350 |
| 5 | `VwsmAdstrdWrcPopltnW` | 직장인구 (414개 행정동) | 9,108 | `wrcpop.csv` | 9,108 |
| 6 | `VwsmAdstrdIxQq` | 상권변화지표 (운영·폐업 점포 평균 영업개월) | 9,350 | `change_ix.csv` | 9,350 |
| 7 | `VwsmAdstrdFcltyW` | 집객시설 (지하철역, 버스정류장 등) | 9,350 | `facility.csv` | 9,350 |
| 8 | `VwsmAdstrdAptW` | 아파트 (단지 수, 면적·가격대별 세대, 평균 시가) | 9,331 | `apt.csv` | 9,331 |
| 9 | `VwsmAdstrdNcmCnsmpW` | 소득소비 (지출 총액, 식료품 지출 등) | 9,350 | `income_cnsmp.csv` | 9,350 |
| 10 | `VwsmSignguIxQq` | 자치구 상권변화지표 (구 코드→구 이름 매핑에만 사용) | 550 | `signgu_ix.csv` | 550 |

## 시도했지만 없던 서비스명 (ERROR-500)

`VwsmAdstrdWrcpplW`, `VwsmAdstrdIxW`, `VwsmAdstrdChgIxW`, `VwsmAdstrdChangeIxW`, `VwsmAdstrdChngIxW`, `VwsmAdstrdTrdarChangeIxW`, `VwsmAdstrdTrdarChngIxW`, `VwsmAdstrdCmercChngIxW`, `VwsmSignguChgIxW`, `VwsmAdstrdIncmCnsmpW`, `VwsmAdstrdRentW`, `VwsmAdstrdLeaseW`, `VwsmAdstrdIxQqW`
→ 행정동 **임대시세** OpenAPI는 찾지 못함.

## 가공 결과물

- `parts/1-location/data/dong_indicators.csv` — 행정동 425개 × 지표 45열 (단위·기간은 열 이름에 표기)
- `parts/1-location/data/seoul_bakery_yearly.csv`, `seoul_bakery_quarterly.csv` — 서울 전체 제과점 추세
- `parts/1-location/data/dong_rankings_top15.csv` — 지표별 원값 상위 15개 행정동
