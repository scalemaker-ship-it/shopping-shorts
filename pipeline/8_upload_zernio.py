#!/usr/bin/env python3
"""[8-z] Zernio API로 란빵🐣(@eggbread0) 유튜브 예약 업로드.

  python3 pipeline/8_upload_zernio.py accounts                        # 연결된 계정 확인
  python3 pipeline/8_upload_zernio.py connect                         # YouTube 연결 URL 발급
  python3 pipeline/8_upload_zernio.py schedule --start 2026-08-26 [--hour 19] [--dry-run]

work/<slug>/output.mp4 + upload.json 을 읽어 하루 1편씩 19:00 KST 예약(scheduledFor).
쇼핑 태그 5개는 API가 없어 Studio에서 수동(prd §0).
"""
import os, sys, json, argparse, mimetypes, datetime as dt
import urllib.request, urllib.error

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = "https://zernio.com/api/v1"
ENV = os.path.expanduser("~/.claude/skills/쇼핑쇼츠-업로드/.env")
CHANNEL_ID = "UCxQK4IBAJ1t-dPImmMinCng"      # 란빵🐣 — 오업로드 방지 가드
KST = dt.timezone(dt.timedelta(hours=9))
CATEGORY_HOWTO = "26"
LOG = os.path.join(ROOT, "work", "_upload_log_zernio.json")

ORDER = ["silicone_mold", "hood_degreaser", "faucet_polish", "washer_gasket", "aircon_kit",
         "drill_brush", "window_brush", "food_waste", "vacuum_seal", "lint_roller"]


def env():
    d = {}
    if os.path.exists(ENV):
        for ln in open(ENV, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1); d[k.strip()] = v.strip().strip('"').strip("'")
    key = os.environ.get("ZERNIO_API_KEY") or d.get("ZERNIO_API_KEY")
    if not key:
        raise SystemExit(f"ZERNIO_API_KEY 없음 → {ENV}")
    return key, d.get("ZERNIO_PROFILE_ID")


def api(method, path, key, body=None, raw=None, ctype=None):
    url = path if path.startswith("http") else BASE + path
    data, headers = None, {}
    if key: headers["Authorization"] = "Bearer " + key
    if body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw; headers["Content-Type"] = ctype or "application/octet-stream"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            t = r.read().decode()
            return json.loads(t) if t.strip().startswith(("{", "[")) else t
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[Zernio] {method} {url} 실패 {e.code}: {e.read().decode()[:500]}")


def _accs(key):
    r = api("GET", "/accounts", key)
    return r if isinstance(r, list) else r.get("accounts", r.get("data", []))


def accounts():
    key, _ = env()
    a = _accs(key)
    if not a: print("연결된 계정 없음 → `connect` 실행")
    for x in a:
        pd = (x.get("metadata") or {}).get("profileData") or {}
        print(f"{x.get('platform')} | {x.get('displayName')} | {pd.get('username') or pd.get('id')} "
              f"| accountId={x.get('_id')} | active={x.get('isActive')}")
    return a


def connect():
    key, pid = env()
    if not pid:
        pid = (api("GET", "/profiles", key)["profiles"][0])["_id"]
    r = api("GET", f"/connect/youtube?profileId={pid}", key)
    print("\n▶ 브라우저에서 열고 **란빵🐣(@eggbread0)** 채널을 선택해 '허용':\n")
    print(r["authUrl"])


def _yt_account(key):
    """유튜브 계정 확보 + 란빵 채널 가드."""
    yts = [x for x in _accs(key) if str(x.get("platform")).lower() == "youtube"]
    if not yts:
        raise SystemExit("연결된 유튜브 계정 없음 → `connect` 먼저 실행")
    for x in yts:
        pd = (x.get("metadata") or {}).get("profileData") or {}
        blob = json.dumps(x, ensure_ascii=False)
        if CHANNEL_ID in blob:
            print(f"✅ 대상 채널: {x.get('displayName')} ({pd.get('username','')}) accountId={x['_id']}")
            return x["_id"]
    raise SystemExit(f"중단: 연결된 유튜브 계정 중 란빵🐣({CHANNEL_ID})이 없습니다.\n"
                     "     연결된 것: " + ", ".join(str(x.get("displayName")) for x in yts))


def _meta(slug):
    b = os.path.join(ROOT, "work", slug)
    up = json.load(open(os.path.join(b, "upload.json"), encoding="utf-8"))
    title = (up.get("title") or up.get("youtube_title") or slug).strip()
    desc = (up.get("description") or up.get("body") or "").strip()
    tags = [t.lstrip("#") for t in (up.get("hashtags") or [])]
    dp = os.path.join(b, "upload_draft.json")
    if (not desc or not tags) and os.path.exists(dp):
        d = json.load(open(dp, encoding="utf-8"))
        if not desc:
            desc = ("\n".join(d.get("body_lines", [])) + "\n\n" + " ".join(d.get("hashtags", []))).strip()
        if not tags:
            tags = [t.lstrip("#") for t in d.get("hashtags", [])]
    # 유튜브 제약: 태그 개당 100자·합계 500자
    out, total = [], 0
    for t in tags:
        t = t[:100]
        if total + len(t) > 500: break
        out.append(t); total += len(t)
    return title[:100], desc[:4900], out


def upload_media(key, path):
    ct = mimetypes.guess_type(path)[0] or "video/mp4"
    pre = api("POST", "/media/presign", key, body={
        "filename": os.path.basename(path), "contentType": ct,
        "size": os.path.getsize(path)})
    with open(path, "rb") as f:
        api("PUT", pre["uploadUrl"], None, raw=f.read(), ctype=ct)
    return pre["publicUrl"]


def schedule(start, hour, dry):
    key, _ = env()
    day = dt.datetime.strptime(start, "%Y-%m-%d").replace(hour=hour, minute=0, second=0,
                                                          microsecond=0, tzinfo=KST)
    plan = []
    for i, slug in enumerate(ORDER):
        f = os.path.join(ROOT, "work", slug, "output.mp4")
        if not os.path.exists(f): raise SystemExit(f"영상 없음: {f}")
        t, d, tg = _meta(slug)
        plan.append((slug, f, t, d, tg, day + dt.timedelta(days=i)))

    print(f"\n예약 계획 ({len(plan)}편 / 매일 {hour:02d}:00 KST)")
    for slug, _, t, _, tg, w in plan:
        print(f"  {w.strftime('%m/%d(%a) %H:%M')}  {slug:16s} {t[:44]}  tags={len(tg)}")
    if dry:
        print("\n--dry-run 이라 업로드하지 않았습니다."); return

    acc = _yt_account(key)
    done = json.load(open(LOG)) if os.path.exists(LOG) else []
    seen = {x["slug"] for x in done}
    for slug, f, title, desc, tags, when in plan:
        if slug in seen:
            print(f"⏭  {slug} 이미 예약됨 — 건너뜀"); continue
        print(f"\n▶ {slug} → {when.strftime('%m/%d %H:%M KST')}")
        url = upload_media(key, f)
        print("  ✔ 미디어 업로드")
        payload = {
            "content": desc,
            "platforms": [{"platform": "youtube", "accountId": acc,
                           "platformSpecificData": {
                               "title": title, "visibility": "public",
                               "madeForKids": False, "categoryId": CATEGORY_HOWTO}}],
            "mediaItems": [{"url": url, "type": "video"}],
            "tags": tags,
            "scheduledFor": when.isoformat(),
            "timezone": "Asia/Seoul",
        }
        res = api("POST", "/posts", key, body=payload)
        pid = (res.get("post") or res).get("_id") if isinstance(res, dict) else None
        print(f"  ✔ 예약 완료 postId={pid}")
        done.append({"slug": slug, "post_id": pid, "publish_at_kst": when.isoformat(),
                     "title": title, "media_url": url})
        json.dump(done, open(LOG, "w"), ensure_ascii=False, indent=2)
    print(f"\n완료 → {LOG}")
    print("⚠️ 유튜브 쇼핑 태그 5개는 Studio에서 수동으로 붙이세요(공개 API 없음).")


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "accounts": return accounts() and None
    if a[0] == "connect": return connect()
    if a[0] == "schedule":
        ap = argparse.ArgumentParser()
        ap.add_argument("--start", default=(dt.datetime.now(KST) + dt.timedelta(days=1)).strftime("%Y-%m-%d"))
        ap.add_argument("--hour", type=int, default=19)
        ap.add_argument("--dry-run", action="store_true")
        p = ap.parse_args(a[1:])
        return schedule(p.start, p.hour, p.dry_run)
    print(__doc__)


if __name__ == "__main__":
    main()
