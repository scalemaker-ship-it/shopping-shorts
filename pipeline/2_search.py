#!/usr/bin/env python3
"""[2-0] 틱톡 소재 후보 검색 — tikwm feed/search API.

사용:
  python3 pipeline/2_search.py "<keyword>" [--count 20] [--min-dur 5] [--max-dur 60]

중국어(간체/번체)가 제목에 섞인 결과는 표시만 남기고 [CN] 로 마킹한다.
실제 화면 자막 검수는 2_download.py --contact 콘택트시트로 한다.
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request

API = "https://www.tikwm.com/api/feed/search/"
CJK = re.compile(r"[一-鿿㐀-䶿]")


def search(kw, count, cursor=0):
    q = urllib.parse.urlencode({"keywords": kw, "count": count, "cursor": cursor})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.load(r)
            if d.get("code") == 0:
                return (d.get("data") or {}).get("videos", [])
            print(f"  ! {d.get('msg')}", file=sys.stderr)
        except Exception as e:
            print(f"  ! {e}", file=sys.stderr)
        time.sleep(2)
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keywords", nargs="+")
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--min-dur", type=int, default=5)
    ap.add_argument("--max-dur", type=int, default=90)
    a = ap.parse_args()

    for kw in a.keywords:
        print(f"\n### {kw}")
        vids = search(kw, a.count)
        for v in vids:
            dur = v.get("duration") or 0
            if not (a.min_dur <= dur <= a.max_dur):
                continue
            title = (v.get("title") or "").replace("\n", " ")
            mark = "[CN] " if CJK.search(title) else ""
            uid = v.get("author", {}).get("unique_id", "")
            url = f"https://www.tiktok.com/@{uid}/video/{v.get('video_id')}"
            print(f"{mark}{dur:>3}s {v.get('play_count',0):>9}  {url}")
            print(f"      {title[:110]}")
        time.sleep(1)


if __name__ == "__main__":
    main()
