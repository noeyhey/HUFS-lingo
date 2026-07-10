# -*- coding: utf-8 -*-
"""
에브리타임 게시판 직접 순회 크롤러 v2 (HUFS-Lingo 니즈 분석용)

동작 방식:
  1) 로그인 후 에타 메인의 게시판 목록(사이드바)에서 대상 게시판을 자동으로 찾음
     (자유게시판, 홍보게시판, 아르바이트 등 — BOARD_NAME_PATTERNS로 매칭)
  2) 각 게시판을 페이지 단위로 넘기며 글 목록(제목+미리보기)을 전부 수집
  3) 키워드(약어 포함)가 포함된 글만 골라 eta_posts.csv 저장

사용 방법:
  python eta_crawler.py
  → 브라우저 로그인 → 터미널에서 Enter

수집이 0건이면 debug/ 폴더에 화면 캡처와 HTML이 저장되니 그걸 확인하세요.
"""

import csv
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent

# 학교 커뮤니티 주소 (한국외대)
SCHOOL_URL = "https://hufs.everytime.kr"

# ──────────────────────────────────────────────
# 1) 대상 게시판: 이 단어가 포함된 게시판을 사이드바에서 자동 선택
# ──────────────────────────────────────────────
BOARD_NAME_PATTERNS = ["자유", "홍보", "아르바이트", "알바", "정보"]

# 자동 탐색이 실패하면 여기에 직접 입력 (게시판 접속 시 주소창의 숫자)
# 예: {"서울캠 자유게시판": 370438, "글캠 자유게시판": 370439}
MANUAL_BOARDS = {}

MIN_MATCHED_PER_BOARD = 30     # 게시판당 이만큼 매칭되면 다음 게시판으로
MAX_PAGES_PER_BOARD = 150      # 안전장치: 매칭이 안 채워져도 이 페이지 수에서 중단
DELAY_RANGE = (2.0, 4.0)       # 페이지 간 대기(초) — 줄이지 마세요

# ──────────────────────────────────────────────
# 2) 필터 키워드: 정식 명칭 + 커뮤니티 약어
#    ※ 약어는 팀에서 아는 것 위주로 자유롭게 추가/삭제하세요
# ──────────────────────────────────────────────
FILTER_KEYWORDS = [
    # 언어·학과 (정식)
    "태국어", "베트남어", "말레이", "인도네시아어", "아랍어",
    "터키어", "아제르바이잔", "페르시아", "이란어", "힌디", "인도학",
    "카자흐", "우즈베크", "중앙아시아", "몽골어",
    "폴란드어", "체코어", "슬로바키아", "루마니아어", "헝가리어",
    "세르비아", "크로아티아", "우크라이나어", "스와힐리", "아프리카학",
    "그리스어", "불가리아", "브라질학", "포르투갈어",
    "스칸디나비아", "노르웨이어", "스웨덴어", "덴마크어", "이탈리아어",
    "융합인재", "소수어",
    # 언어·학과 (약어)
    "마인어",        # 말레이·인도네시아어
    "터아제",        # 터키·아제르바이잔
    "세크과", "세크어",  # 세르비아·크로아티아
    "체슬",          # 체코·슬로바키아
    "중아과",        # 중앙아시아
    "우크라어",
    "이란학",
    "타이어과",
    "그불",          # 그리스·불가리아
    "브포",          # 브라질(포르투갈어)
    "스칸어",        # 스칸디나비아
    "융인",          # 융합인재학부

    # 니즈
    "첨삭", "작문", "교정", "번역", "통역", "과외", "튜터",
    "단어장", "요약본", "족보", "교재",
    "회화", "발음", "쉐도잉", "스피킹",
    "flex", "플렉스",
]
# ──────────────────────────────────────────────

OUTPUT_CSV = BASE / "eta_posts.csv"
DEBUG_DIR = BASE / "debug"


def dump_debug(page, name):
    DEBUG_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=True)
    (DEBUG_DIR / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print(f"  [debug] {DEBUG_DIR / name}.png / .html 저장")


MAIN_URL = "https://everytime.kr"


def is_logged_in(page):
    """확실한 로그인 판별: 로그인 폼/로그인 링크/account 도메인이면 로그아웃 상태"""
    if "account.everytime.kr" in page.url:
        return False
    if page.query_selector('form[action*="login"]'):
        return False
    if page.query_selector('a[href*="account.everytime.kr/login"]'):
        return False
    return True


def find_boards(page):
    """로그인 확인 후 사이드바에서 게시판 이름·ID 자동 수집"""
    page.goto(MAIN_URL, wait_until="networkidle")
    time.sleep(2)

    # 로그인 상태 확인 — 될 때까지 진행하지 않음
    while not is_logged_in(page):
        print("\n※ 아직 로그인이 안 됐습니다.")
        print("※ 반드시 '이 스크립트가 띄운 브라우저 창'에서 로그인하세요. (평소 쓰는 크롬 창 아님!)")
        input("로그인 완료 후 다시 Enter → ")
        page.goto(MAIN_URL, wait_until="networkidle")
        time.sleep(2)

    def scan():
        found = {}
        for a in page.query_selector_all("a[href]"):
            href = a.get_attribute("href") or ""
            m = re.fullmatch(r"/(\d{5,})", href)
            if not m:
                continue
            name = a.inner_text().strip().replace("\n", " ")
            if not name:
                continue
            if any(p in name for p in BOARD_NAME_PATTERNS):
                found[name] = m.group(1)
        return found

    boards = scan()
    if not boards:
        # 메인에서 못 찾으면 학교 커뮤니티 페이지에서 ID만 수집
        page.goto(SCHOOL_URL, wait_until="networkidle")
        time.sleep(2)
        boards = scan()
        page.goto(MAIN_URL, wait_until="networkidle")
        time.sleep(1)
    return boards


def collect_page(page, board_name):
    """게시판 목록 한 페이지에서 글 추출 (여러 레이아웃 대비)"""
    rows = []
    articles = page.query_selector_all("article a.article, article.list, div.wrap article")
    if not articles:
        articles = page.query_selector_all("article")
    for a in articles:
        def txt(sel):
            el = a.query_selector(sel)
            return el.inner_text().strip() if el else ""

        title = txt("h2")
        body = txt("p")
        if not title and not body:
            continue
        rows.append({
            "board": board_name,
            "title": title,
            "text": body,
            "time": txt("time"),
            "vote": txt("li.vote"),
            "comment": txt("li.comment"),
        })
    return rows


def main():
    matched_rows = []
    seen = set()
    total_scanned = 0

    with sync_playwright() as p:
        # 세션(쿠키)을 .pw_profile 폴더에 저장 → 최초 1회만 로그인하면 됨
        context = p.chromium.launch_persistent_context(
            str(BASE / ".pw_profile"),
            headless=False,
            locale="ko-KR",
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(MAIN_URL, wait_until="networkidle")
        time.sleep(2)

        if not is_logged_in(page):
            page.goto("https://everytime.kr/login")
            print("\n※ 이 스크립트가 띄운 브라우저 창에서 로그인해 주세요. (평소 쓰는 크롬 아님!)")
            input("로그인 완료 후 여기서 Enter를 누르세요 → ")

        # 게시판 목록 확보
        boards = {name: bid for name, bid in find_boards(page).items()}
        for name, bid in MANUAL_BOARDS.items():
            boards[name] = str(bid)

        if not boards:
            print("게시판을 찾지 못했습니다. debug 폴더를 확인하세요.")
            dump_debug(page, "main")
            context.close()
            return

        print(f"\n대상 게시판 {len(boards)}개:")
        for name, bid in boards.items():
            print(f"  - {name} (id={bid})")

        for board_name, bid in boards.items():
            print(f"\n[게시판] {board_name}")

            # 게시판 진입: 메인 사이드바 링크 클릭, 없으면 URL 직접 이동
            try:
                page.goto(MAIN_URL, wait_until="networkidle", timeout=20000)
                time.sleep(1)
                link = page.query_selector(f'a[href="/{bid}"]')
                if link:
                    link.click()
                    page.wait_for_load_state("networkidle")
                else:
                    page.goto(f"{MAIN_URL}/{bid}", wait_until="networkidle", timeout=20000)
                time.sleep(1.5)
            except Exception as e:
                print(f"  게시판 진입 실패: {e}")
                continue

            board_matched = 0
            for page_num in range(1, MAX_PAGES_PER_BOARD + 1):
                if not is_logged_in(page):
                    print("  로그인 페이지로 튕김 → 이 게시판 건너뜀 (디버그 저장)")
                    dump_debug(page, f"board_{bid}")
                    break

                rows = collect_page(page, board_name)
                if not rows:
                    if page_num == 1:
                        print("  글을 읽지 못했습니다 → 디버그 저장")
                        dump_debug(page, f"board_{bid}")
                    else:
                        print(f"  p{page_num}: 마지막 페이지 도달")
                    break

                total_scanned += len(rows)
                new_matched = 0
                for r in rows:
                    key = (r["title"], r["text"])
                    if key in seen:
                        continue
                    seen.add(key)
                    full = (r["title"] + " " + r["text"]).lower()
                    hits = [k for k in FILTER_KEYWORDS if k.lower() in full]
                    if hits:
                        r["matched"] = ", ".join(hits)
                        matched_rows.append(r)
                        new_matched += 1
                        board_matched += 1

                print(f"  p{page_num}: {len(rows)}글 스캔, 매칭 {new_matched}건 (게시판 {board_matched}/{MIN_MATCHED_PER_BOARD}, 전체 {len(matched_rows)})")

                if board_matched >= MIN_MATCHED_PER_BOARD:
                    print(f"  이 게시판 {MIN_MATCHED_PER_BOARD}건 달성 → 다음 게시판으로")
                    break

                time.sleep(random.uniform(*DELAY_RANGE))

                # 하단 페이지네이션의 '다음' 버튼 클릭으로 페이지 이동
                next_link = (
                    page.query_selector("div.pagination a.next")
                    or page.query_selector('a:has-text("다음")')
                    or page.query_selector("a.next")
                )
                if not next_link:
                    print("  다음 페이지 없음 → 게시판 끝")
                    break
                try:
                    next_link.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                except Exception as e:
                    print(f"  다음 페이지 이동 실패: {e}")
                    break

        context.close()

    print(f"\n총 {total_scanned}글 스캔 / 키워드 매칭 {len(matched_rows)}건")

    if not matched_rows:
        print("매칭된 글이 없습니다. FILTER_KEYWORDS를 넓히거나 MAX_PAGES_PER_BOARD를 늘려보세요.")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["board", "title", "text", "time", "vote", "comment", "matched"]
        )
        writer.writeheader()
        writer.writerows(matched_rows)

    print(f"저장 완료 → {OUTPUT_CSV}")
    print("다음 단계: python eta_analyzer.py")


if __name__ == "__main__":
    main()
