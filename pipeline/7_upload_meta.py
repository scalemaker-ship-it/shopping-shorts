#!/usr/bin/env python3
"""[7] 업로드 준비 — 제목/본문/해시태그 + 유튜브 쇼핑 태그 정보 생성.
사용: python3 pipeline/7_upload_meta.py <slug>

입력: work/<slug>/upload_draft.json  (사람/Claude가 미리 작성한 카피)
  { "title": "...", "body_lines": ["...", "..."], "hashtags": ["#...", ...],
    "search_query": "...", "price_range": "20,000~35,000원",
    "schedule": {"date": "8/14(금)", "time": "17:00 KST"} }
product.json 의 product/keywords 와 합쳐 shopping_tag 블록을 포함한
산출: work/<slug>/upload.json, work/<slug>/upload.txt
제목=클릭유도문구ㅣ제품명 / 본문(카피+해시태그+구매링크안내) / 해시태그 5개+ / 쇼핑태그(Studio 수동)
"""
import sys, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    slug = sys.argv[1]
    b = os.path.join(ROOT, "work", slug)
    product = json.load(open(os.path.join(b, "product.json")))
    draft_path = os.path.join(b, "upload_draft.json")
    if not os.path.exists(draft_path):
        print(f"[FAIL] {draft_path} 없음 — 먼저 카피(title/body_lines/hashtags/search_query/price_range)를 작성하세요.")
        sys.exit(1)
    draft = json.load(open(draft_path))

    hashtags = draft["hashtags"] if draft["hashtags"][-1] == "#shorts" else draft["hashtags"] + ["#shorts"]
    assert len(hashtags) >= 6, "해시태그 5개 이상 + #shorts 필요"

    description = "\n".join(draft["body_lines"]) + "\n\n" + " ".join(hashtags[:-1]) + \
        "\n\n구매 링크는 더보기란과 프로필에서 확인 👆"

    meta = {
        "title": draft["title"],
        "description": description,
        "hashtags": hashtags,
        "shopping_tag": {
            "product_name": product["product"],
            "search_query": draft["search_query"],
            "price_range": draft["price_range"],
            "note": "YouTube Studio > 이 Shorts > 관련 상품 > 쇼핑 제휴로 제품 태그 (수동)",
        },
        "keywords_for_search": product["keywords"],
    }
    if "schedule" in draft:
        meta["schedule"] = draft["schedule"]

    json.dump(meta, open(os.path.join(b, "upload.json"), "w"),
              ensure_ascii=False, indent=2)
    with open(os.path.join(b, "upload.txt"), "w") as f:
        if "schedule" in draft:
            f.write(f"[예약: {draft['schedule']['date']} {draft['schedule']['time']}]\n")
        f.write("제목: " + meta["title"] + "\n\n")
        f.write("\n".join(draft["body_lines"]) + "\n\n")
        f.write(" ".join(hashtags) + "\n\n")
        f.write("=== 쇼핑 태그(Studio 수동) ===\n")
        st = meta["shopping_tag"]
        f.write(f"제품명: {st['product_name']}\n검색어: {st['search_query']}\n"
                f"가격대: {st['price_range']}\n{st['note']}\n")
    print("=== upload.txt ===")
    print(open(os.path.join(b, "upload.txt")).read())


if __name__ == "__main__":
    main()
