# -*- coding: utf-8 -*-
"""
에타 게시글 니즈 분석 + PPT용 차트 생성 (HUFS-Lingo)

사용 방법:
  1) pip install pandas matplotlib
  2) eta_posts.csv 가 같은 폴더에 있는 상태에서: python eta_analyzer.py

산출물 (charts/ 폴더, 300dpi PNG — PPT에 바로 삽입 가능):
  - chart_needs.png     니즈 유형별 게시글 수
  - chart_language.png  언어별 언급 게시글 수
  - chart_quotes.csv    IR Deck 인용 후보 게시글 (니즈 매칭된 원문)
  - summary.csv         니즈 x 언어 교차표
"""

import re
from pathlib import Path

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

BASE = Path(__file__).parent
INPUT_CSV = BASE / "eta_posts.csv"
OUT_DIR = BASE / "charts"

# ──────────────────────────────────────────────
# 분류 사전: 팀 논의에 맞게 자유롭게 수정
# ──────────────────────────────────────────────
NEEDS = {
    "첨삭/작문": ["첨삭", "작문", "교정", "봐주", "봐줄", "검토", "봐줄 사람", "봐주실"],
    "과외/스터디": ["과외", "스터디", "튜터", "가르쳐", "배우고 싶", "레슨", "같이 공부", "공부하실"],
    "교재/자료": ["교재", "책 추천", "자료", "단어장", "요약본", "족보", "pdf", "피디에프", "필기"],
    "번역": ["번역", "통역", "해석 좀", "해석해", "번역 알바", "뜻이 뭐"],
    "회화/발음": ["회화", "발음", "말하기", "스피킹", "쉐도잉", "회화 스터디"],
    "시험/자격증": ["flex", "플렉스", "시험", "자격증", "성적", "중간", "기말", "족보"],
    "진로/취업": ["취업", "진로", "인턴", "취준", "복수전공", "이중전공", "이중", "복전", "전과"],
}

LANGUAGES = {
    "태국어": ["태국어", "태국말", "타이어과"],
    "베트남어": ["베트남어", "베트남과"],
    "말레이·인니어": ["말레이", "인도네시아어", "인니어", "마인어"],
    "아랍어": ["아랍어", "아랍과"],
    "터키·아제르어": ["터키어", "아제르", "터아제"],
    "페르시아어": ["페르시아", "이란어", "이란학"],
    "인도어": ["힌디", "인도어", "인도학"],
    "중앙아시아어": ["카자흐", "우즈베크", "중앙아시아", "중아과"],
    "폴란드어": ["폴란드어", "폴란드과"],
    "체코·슬로바키아어": ["체코어", "슬로바키아", "체슬"],
    "루마니아어": ["루마니아어"],
    "헝가리어": ["헝가리어"],
    "세르비아·크로아티아어": ["세르비아", "크로아티아", "세크과", "세크어"],
    "우크라이나어": ["우크라이나어", "우크라어"],
    "스와힐리어": ["스와힐리", "아프리카학"],
    "몽골어": ["몽골어"],
    # 설문 응답 기반 추가 (2026-07)
    "그리스·불가리아어": ["그리스어", "불가리아", "그불"],
    "브라질(포르투갈어)": ["브라질학", "포르투갈어", "브포"],
    "스칸디나비아어": ["스칸디나비아", "스칸어", "노르웨이어", "스웨덴어", "덴마크어"],
    "이탈리아어": ["이탈리아어"],
    "융합인재(통번역)": ["융합인재", "융인"],
}

# "소수어"라는 단어 자체가 들어간 글도 소수어 관련으로 분류
MINORITY_MARKERS = ["소수어"]

# 분석에서 제외할 글 (우리 팀이 올린 홍보/설문글 등)
EXCLUDE_PATTERNS = ["실제 서비스로 만들어질", "저희는 이런 문제를 해결하는"]

# 팀 컬러 (PPT 톤에 맞게 수정 가능)
BAR_COLOR = "#4472C4"
# ──────────────────────────────────────────────


def setup_korean_font():
    for font in ["Malgun Gothic", "AppleGothic", "NanumGothic"]:
        if any(font in f.name for f in matplotlib.font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False


def match_categories(text, mapping):
    """텍스트에 매칭되는 카테고리 목록 반환"""
    text = text.lower()
    return [cat for cat, kws in mapping.items() if any(k.lower() in text for k in kws)]


def bar_chart(series, title, path, color=BAR_COLOR):
    series = series.sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(8, max(3, 0.45 * len(series))))
    series.plot.barh(ax=ax, color=color)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("게시글 수")
    for i, v in enumerate(series):
        ax.text(v + 0.1, i, str(int(v)), va="center", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight", transparent=True)
    plt.close(fig)
    print(f"저장: {path.name}")


def main():
    if not INPUT_CSV.exists():
        print(f"{INPUT_CSV.name} 이 없습니다. 먼저 eta_crawler.py 를 실행하세요.")
        return

    setup_korean_font()
    OUT_DIR.mkdir(exist_ok=True)

    df = pd.read_csv(INPUT_CSV).fillna("")
    df["full_text"] = (df["title"].astype(str) + " " + df["text"].astype(str)).str.strip()
    df = df.drop_duplicates(subset="full_text").reset_index(drop=True)
    print(f"게시글 {len(df)}건 로드 (중복 제거 후)")

    # 우리 팀 홍보글 등 제외
    before = len(df)
    df = df[~df["full_text"].apply(lambda t: any(p in t for p in EXCLUDE_PATTERNS))].reset_index(drop=True)
    if before - len(df):
        print(f"제외 처리: {before - len(df)}건 (팀 홍보글 등)")

    df["needs"] = df["full_text"].apply(lambda t: match_categories(t, NEEDS))
    df["languages"] = df["full_text"].apply(lambda t: match_categories(t, LANGUAGES))
    # 소수어 직접 관련: 소수어 언어명 언급 또는 "소수어" 단어 포함
    df["is_minority"] = df.apply(
        lambda r: bool(r["languages"]) or any(m in r["full_text"] for m in MINORITY_MARKERS),
        axis=1,
    )
    mino = df[df["is_minority"]]

    # 1) 니즈 유형별 빈도 — 소수어 관련 vs 전체(배경 수요)
    mino_needs = pd.Series(
        [n for lst in mino["needs"] for n in lst], dtype=object
    ).value_counts()
    if not mino_needs.empty:
        bar_chart(mino_needs, "소수어 관련 니즈 유형별 게시글 수", OUT_DIR / "chart_needs.png")

    all_needs = pd.Series(
        [n for lst in df["needs"] for n in lst], dtype=object
    ).value_counts()
    if not all_needs.empty:
        bar_chart(
            all_needs,
            "전체 어학 니즈 게시글 수 (배경 수요, 소수어 외 포함)",
            OUT_DIR / "chart_needs_all.png",
            color="#A6A6A6",
        )

    # 2) 언어별 빈도 (융합인재는 학부명이라 언어 차트에서 제외)
    lang_count = pd.Series(
        [l for lst in df["languages"] for l in lst if l != "융합인재(통번역)"],
        dtype=object,
    ).value_counts()
    if not lang_count.empty:
        bar_chart(lang_count, "소수어 언어별 관련 게시글 수", OUT_DIR / "chart_language.png")

    # 3) 니즈 x 언어 교차표 (소수어 관련만)
    rows = []
    for _, r in mino.iterrows():
        for n in (r["needs"] or ["(니즈 미분류)"]):
            for l in (r["languages"] or ["(소수어 일반)"]):
                rows.append({"need": n, "language": l})
    if rows:
        cross = pd.DataFrame(rows).value_counts().reset_index(name="count")
        cross.to_csv(OUT_DIR / "summary.csv", index=False, encoding="utf-8-sig")
        print("저장: summary.csv")

    # 4) IR Deck 인용 후보: 소수어 직접 관련 글 원문 (핵심 산출물)
    base_cols = [c for c in ["board", "keyword", "matched", "title", "text", "time"] if c in df.columns]
    quotes = mino[base_cols + ["needs", "languages"]].copy()
    # 니즈가 매칭된 글(플랫폼과 직결)이 위로 오도록 정렬
    quotes["_priority"] = quotes["needs"].str.len()
    quotes = quotes.sort_values("_priority", ascending=False).drop(columns="_priority")
    quotes["needs"] = quotes["needs"].apply(", ".join)
    quotes["languages"] = quotes["languages"].apply(", ".join)
    quotes.to_csv(OUT_DIR / "chart_quotes.csv", index=False, encoding="utf-8-sig")
    print(f"저장: chart_quotes.csv (소수어 관련 인용 후보 {len(quotes)}건)")

    # 콘솔 요약
    print("\n===== 요약 =====")
    print(f"전체 게시글: {len(df)}건")
    print(f"소수어 직접 관련: {len(mino)}건 / 일반 어학·기타: {len(df) - len(mino)}건")
    if not mino_needs.empty:
        print("\n[소수어 관련 니즈 Top]")
        print(mino_needs.head(7).to_string())
    if not lang_count.empty:
        print("\n[언어 Top]")
        print(lang_count.head(7).to_string())


if __name__ == "__main__":
    main()
