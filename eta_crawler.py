# -*- coding: utf-8 -*-
"""
에브리타임 게시글 키워드 검색 크롤러 (HUFS-Lingo 니즈 분석용)

사용 방법:
  1) pip install playwright pandas
  2) playwright install chromium
  3) python eta_crawler.py
  4) 브라우저가 열리면 본인 계정으로 직접 로그인 → 터미널에서 Enter
  5) 키워드별 검색 결과가 eta_posts.csv 로 저장됨

주의:
  - 본인 계정으로, 소량·연구(아이디어톤 검증) 목적으로만 사용하세요.
  - 요청 간 딜레이가 있으니 임의로 줄이지 마세요 (계정 제재 방지).
  - 에타 페이지 구조가 바뀌면 SELECTORS 부분을 수정해야 할 수 있습니다.
"""

import csv
import random
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# ──────────────────────────────────────────────
# 설정: 필요에 맞게 수정하세요
# ──────────────────────────────────────────────
KEYWORDS = [
    # 언어/학과 계열
    "태국어", "베트남어", "말레이", "인도네시아어", "아랍어",
    "터키어", "페르시아어", "이란어", "힌디", "인도어",
    "카자흐어", "우즈베크어", "중앙아시아",
    "폴란드어", "체코어", "슬로바키아어", "루마니아어",
    "헝가리어", "세르비아어", "크로아티아어", "우크라이나어", "스와힐리어",
    # 니즈 계열 (언어명과 조합해 검색하고 싶으면 "태국어 첨삭" 처럼 직접 추가)
    "첨삭", "작문 봐주", "과외 구합", "번역 도와",
]

MAX_PAGES_PER_KEYWORD = 5      # 키워드당 최대 페이지 수
DELAY_RANGE = (2.5, 5.0)       # 페이지 간 대기 시간(초)
OUTPUT_CSV = Path(__file__).parent / "eta_posts.csv"

# 페이지 구조가 바뀌면 여기를 수정
SELECTORS = {
    "article": "article.medium, article.list a.article, div.searchresults article",
    "title": "h2.medium, h2.small, h2",
    "text": "p.medium, p.small, p.large, p",
    "time": "time.medium, time.small, time",
    "vote": "li.vote",
    "comment": "li.comment",
}
# ──────────────────────────────────────────────


def collect_articles(page, keyword):
    """현재 검색 결과 화면에서 게시글 정보 추출"""
    rows = []
    articles = page.query_selector_all(SELECTORS["article"])
    for a in articles:
        def txt(sel):
            el = a.query_selector(sel)
            return el.inner_text().strip() if el else ""

        title = txt(SELECTORS["title"])
        body = txt(SELECTORS["text"])
        if not title and not body:
            continue
        rows.append({
            "keyword": keyword,
            "title": title,
            "text": body,
            "time": txt(SELECTORS["time"]),
            "vote": txt(SELECTORS["vote"]),
            "comment": txt(SELECTORS["comment"]),
        })
    return rows


def main():
    all_rows = []
    seen = set()  # (title, text) 중복 제거

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto("https://everytime.kr/login")

        print("\n브라우저에서 직접 로그인해 주세요.")
        input("로그인 완료 후 여기서 Enter를 누르세요 → ")

        for kw in KEYWORDS:
            print(f"\n[검색] {kw}")
            for page_num in range(1, MAX_PAGES_PER_KEYWORD + 1):
                url = f"https://everytime.kr/search/all/{kw}/p/{page_num}"
                try:
                    page.goto(url, wait_until="networkidle", timeout=20000)
                except Exception as e:
                    print(f"  p{page_num} 로드 실패: {e}")
                    break

                rows = collect_articles(page, kw)
                if not rows:
                    print(f"  p{page_num}: 결과 없음 → 다음 키워드로")
                    break

                new = 0
                for r in rows:
                    key = (r["title"], r["text"])
                    if key in seen:
                        continue
                    seen.add(key)
                    all_rows.append(r)
                    new += 1
                print(f"  p{page_num}: {len(rows)}건 수집 (신규 {new}건)")

                time.sleep(random.uniform(*DELAY_RANGE))

        browser.close()

    if not all_rows:
        print("\n수집된 게시글이 없습니다. SELECTORS 또는 검색 URL을 확인하세요.")
        print("(에타 화면에서 F12 → 게시글 요소의 태그/클래스명을 확인해 수정)")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n총 {len(all_rows)}건 저장 완료 → {OUTPUT_CSV}")
    print("다음 단계: python eta_analyzer.py")


if __name__ == "__main__":
    main()
