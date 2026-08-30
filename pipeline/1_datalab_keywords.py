"""네이버 데이터랩 쇼핑인사이트에서 '오늘' 인기 검색어를 긁어온다.

사용법:
    python3 pipeline/1_datalab_keywords.py [--top N]

- 대상 카테고리: 25~54 남성 타겟에 맞는 5개 분야(디지털/가전, 생활/건강, 스포츠/레저,
  가구/인테리어, 여가/생활편의). 패션의류/화장품/출산육아/식품/면세점/도서는 제외.
- 기간: 종료일(=페이지 기본값, 보통 어제)에서 --days 일 전까지의 구간. 기본 7일(최근 1주).
  ⚠️ 시작일=종료일(1일) 로 두면 데이터랩이 빈 결과를 돌려준다(2026-08-28 확인) → 최소 2일 이상.
  ⚠️ '직접입력' 기간 설정은 반드시 카테고리 선택보다 **먼저** 해야 한다. 순서를 바꾸면 0건이 나온다.
- 이미 제작한 제품(work/*/product.json)의 키워드와 겹치면 표시만 하고 걸러내진 않는다
  (사람이 최종 판단).
- 산출물: work/_datalab/keywords_<YYYYMMDD>.json
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "work", "_datalab")

TARGET_CATEGORIES = {
    "50000003": "디지털/가전",
    "50000008": "생활/건강",
    "50000007": "스포츠/레저",
    "50000004": "가구/인테리어",
    "50000009": "여가/생활편의",
}

URL = "https://datalab.naver.com/shoppingInsight/sCategory.naver"


def existing_keywords():
    kws = set()
    for pj in glob.glob(os.path.join(BASE_DIR, "work", "*", "product.json")):
        try:
            data = json.load(open(pj, encoding="utf-8"))
        except Exception:
            continue
        for k in data.get("keywords", []):
            kws.add(k)
        if data.get("product"):
            kws.add(data["product"])
    return kws


def select_dropdown(page, group, index, text):
    """set_period_target 그룹(엘리먼트 핸들) 안의 index번째 .select 를 열어 text 옵션을 클릭."""
    boxes = group.query_selector_all(".select")
    box = boxes[index]
    box.query_selector(".select_btn").click()
    page.wait_for_timeout(150)
    option = box.query_selector(f".select_list .option:text-is('{text}')")
    if option is None:
        raise RuntimeError(f"dropdown option not found: {text}")
    option.click()
    page.wait_for_timeout(150)


def set_period(page, days):
    """'직접입력' 으로 [종료일-days+1 ~ 종료일] 구간을 지정한다. 카테고리 선택보다 먼저 호출.
    반환: (start_date, end_date)"""
    page.click("label.period.input")
    page.wait_for_timeout(400)
    group = page.query_selector_all(".set_period_target")[0]
    boxes = group.query_selector_all(".select")
    ey, em, ed = (boxes[i].query_selector(".select_btn").inner_text().strip() for i in (3, 4, 5))
    end = date(int(ey), int(em), int(ed))
    start = end - timedelta(days=max(days, 2) - 1)
    select_dropdown(page, group, 0, f"{start.year}")
    select_dropdown(page, group, 1, f"{start.month:02d}")
    select_dropdown(page, group, 2, f"{start.day:02d}")
    return start, end


def scrape_category(page, cid, name, top_n, start, end):
    page.click(".form_row .set_period.category .select .select_btn")
    page.wait_for_timeout(400)
    page.click(f'.form_row .select_list a.option[data-cid="{cid}"]')
    page.wait_for_timeout(700)
    page.click(".btn_submit")
    page.wait_for_timeout(4000)

    items = page.query_selector_all(".rank_top1000_list li")
    result = []
    for li in items[:top_n]:
        num = li.query_selector(".rank_top1000_num")
        rank = int(num.inner_text().strip()) if num else None
        text = li.inner_text().strip()
        keyword = re.sub(r"^\d+\s*", "", text).strip()
        result.append({"rank": rank, "keyword": keyword})
    return {"category": name, "cid": cid,
            "date": f"{start.isoformat()}~{end.isoformat()}", "keywords": result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--days", type=int, default=7,
                    help="종료일 기준 최근 N일 구간(기본 7=최근 1주). 1은 불가 — 최소 2.")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    known = existing_keywords()

    all_results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(8000)
        page.goto(URL, timeout=30000)
        page.wait_for_timeout(1500)

        start, end = set_period(page, args.days)
        print(f"기간: {start} ~ {end} ({args.days}일)\n")

        for cid, name in TARGET_CATEGORIES.items():
            try:
                data = scrape_category(page, cid, name, args.top, start, end)
                all_results.append(data)
                print(f"[{name}] {data['date']} 기준 상위 {len(data['keywords'])}개 수집")
            except Exception as e:
                print(f"[{name}] 실패: {e}", file=sys.stderr)

        browser.close()

    today = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUT_DIR, f"keywords_{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n저장: {out_path}\n")
    for cat in all_results:
        print(f"## {cat['category']} ({cat['date']})")
        for item in cat["keywords"]:
            mark = " (기존제작)" if item["keyword"] in known else ""
            print(f"  {item['rank']:>3}. {item['keyword']}{mark}")
        print()


if __name__ == "__main__":
    main()
