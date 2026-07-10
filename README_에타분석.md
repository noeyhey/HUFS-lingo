# 에타 게시글 니즈 분석 (HUFS-Lingo)

## 준비 (최초 1회)

```
pip install playwright pandas matplotlib
playwright install chromium
```

## 1단계: 크롤링 — `eta_crawler.py`

```
python eta_crawler.py
```

브라우저가 열리면 **본인 에타 계정으로 직접 로그인** 후 터미널에서 Enter.
키워드별 검색 결과를 자동 수집해 `eta_posts.csv`로 저장합니다.

- 검색 키워드는 파일 상단 `KEYWORDS` 리스트에서 수정 ("태국어 첨삭"처럼 조합 키워드 추가 추천)
- `MAX_PAGES_PER_KEYWORD`로 키워드당 수집량 조절
- 결과가 0건이면 에타 페이지 구조가 바뀐 것 → F12로 게시글 요소 클래스명 확인 후 `SELECTORS` 수정

## 2단계: 분석 — `eta_analyzer.py`

```
python eta_analyzer.py
```

`charts/` 폴더에 생성:

| 파일 | 내용 |
|---|---|
| `chart_needs.png` | 니즈 유형별 게시글 수 (300dpi, 투명배경 — PPT에 바로 삽입) |
| `chart_language.png` | 언어별 언급 게시글 수 |
| `summary.csv` | 니즈 × 언어 교차표 |
| `chart_quotes.csv` | **IR Deck 인용 후보** 게시글 원문 모음 |

니즈 분류 기준은 `eta_analyzer.py` 상단 `NEEDS` 사전에서 수정 가능.

## 주의

- 본인 계정, 소량, 아이디어톤 검증 목적으로만 사용 (에타 약관상 자동수집 제한 있음 — 딜레이 설정을 줄이지 말 것)
- 인용문을 IR Deck에 넣을 때는 작성자 특정 가능 정보(학과+학번 등) 제거 권장
