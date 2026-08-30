#!/usr/bin/env python3
"""[8] 유튜브 업로드 — 란빵🐣(@eggbread0) 채널에 예약 업로드.

  python3 pipeline/8_upload.py auth                 # 1회 인증(브라우저에서 '란빵' 채널 선택 후 허용)
  python3 pipeline/8_upload.py whoami               # 연결된 채널 확인
  python3 pipeline/8_upload.py schedule             # work/<slug>/output.mp4 를 하루 1개씩 19:00 KST 예약
      [--start 2026-08-26] [--hour 19] [--dry-run]

예약은 유튜브 자체 기능(status.publishAt)을 쓴다. 업로드는 지금 한 번에 다 하고,
공개만 하루 간격으로 자동으로 풀린다 → 매일 실행되는 크론이 필요 없다.
기본 공개 시각 = **19:00 KST**(2026-08-25 확정).

⚠️ 유튜브 쇼핑 태그는 공개 API가 없어 **Studio에서 수동**으로 붙여야 한다(prd §0 참조).
"""
import os, sys, json, argparse, webbrowser, datetime as dt
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEC_DIR = os.path.join(ROOT, ".secrets")
TOKEN = os.path.join(SEC_DIR, "yt_token.json")
UPLOADER_ENV = os.path.join(ROOT, "..", "uploader", ".env")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/youtube"]
REDIRECT = "http://localhost:3000/auth/youtube/callback"

CHANNEL_ID = "UCxQK4IBAJ1t-dPImmMinCng"      # 란빵🐣 / @eggbread0 — 오업로드 방지 가드
KST = dt.timezone(dt.timedelta(hours=9))
CATEGORY_HOWTO = "26"                         # 26 = 노하우/스타일

# 업로드 순서 (prd §0 — 태그 가능한 청소용품과 생활용품을 번갈아 배치)
ORDER = ["silicone_mold", "hood_degreaser", "faucet_polish", "washer_gasket", "aircon_kit",
         "drill_brush", "window_brush", "food_waste", "vacuum_seal", "lint_roller"]


def _env(path):
    d = {}
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1); d[k.strip()] = v.strip()
    return d


def _client_config():
    e = _env(UPLOADER_ENV)
    cid = e.get("GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    csec = e.get("GOOGLE_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    if not cid or not csec:
        raise SystemExit("GOOGLE_CLIENT_ID/SECRET 없음 (uploader/.env 확인)")
    return {"web": {"client_id": cid, "client_secret": csec,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT]}}, cid, csec


class _CB(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if "code" in q:
            _CB.code = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>인증 완료. 이 창을 닫아도 됩니다.</h2>".encode())
        else:
            self.send_response(400); self.end_headers()
    def log_message(self, *a): pass


def do_auth():
    import time
    from google_auth_oauthlib.flow import Flow
    cfg, cid, csec = _client_config()
    flow = Flow.from_client_config(cfg, scopes=SCOPES, redirect_uri=REDIRECT)
    url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                    include_granted_scopes="true")
    srv = HTTPServer(("127.0.0.1", 3000), _CB); srv.timeout = 5
    print("\n▶ 브라우저에서 열고 **란빵🐣(@eggbread0)** 채널을 선택해 '허용'하세요:")
    print(url + "\n", flush=True)
    try: webbrowser.open(url)
    except Exception: pass
    deadline = time.time() + 3600   # 1시간 대기(사람이 브라우저에서 누를 시간)
    while _CB.code is None and time.time() < deadline:
        srv.handle_request()
    srv.server_close()
    if not _CB.code:
        raise SystemExit("인증 코드 미수신 (1시간 초과 또는 취소) — auth 를 다시 실행하세요")
    flow.fetch_token(code=_CB.code)
    c = flow.credentials
    os.makedirs(SEC_DIR, exist_ok=True)
    json.dump({"token": c.token, "refresh_token": c.refresh_token,
               "token_uri": c.token_uri, "client_id": cid, "client_secret": csec,
               "scopes": SCOPES}, open(TOKEN, "w"))
    os.chmod(TOKEN, 0o600)
    print(f"토큰 저장: {TOKEN}")
    whoami()


def get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    if not os.path.exists(TOKEN):
        raise SystemExit("토큰 없음 → 먼저 `python3 pipeline/8_upload.py auth` 실행")
    d = json.load(open(TOKEN))
    creds = Credentials(d["token"], refresh_token=d.get("refresh_token"),
                        token_uri=d["token_uri"], client_id=d["client_id"],
                        client_secret=d["client_secret"], scopes=d["scopes"])
    if not creds.valid:
        creds.refresh(Request())
        d["token"] = creds.token; json.dump(d, open(TOKEN, "w"))
    return build("youtube", "v3", credentials=creds)


def whoami(yt=None):
    yt = yt or get_service()
    items = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
    for it in items:
        mark = "  ✅ 목표 채널" if it["id"] == CHANNEL_ID else "  ⚠️ 다른 채널"
        print(f"채널: {it['snippet']['title']} ({it['snippet'].get('customUrl','')}) id={it['id']}{mark}")
    return items


def _guard(yt):
    """엉뚱한 채널(예: @스케일메이커)에 올라가는 사고 방지."""
    items = whoami(yt)
    if not items or items[0]["id"] != CHANNEL_ID:
        raise SystemExit(f"중단: 연결된 채널이 란빵🐣({CHANNEL_ID})이 아닙니다. auth 를 다시 하세요.")


def _meta(slug):
    """work/<slug>/upload.json 에서 제목/본문/태그를 읽는다."""
    b = os.path.join(ROOT, "work", slug)
    up = json.load(open(os.path.join(b, "upload.json"), encoding="utf-8"))
    title = up.get("title") or up.get("youtube_title") or slug
    desc = up.get("description") or up.get("body") or ""
    if not desc:
        draft = json.load(open(os.path.join(b, "upload_draft.json"), encoding="utf-8"))
        desc = "\n".join(draft.get("body_lines", [])) + "\n\n" + " ".join(draft.get("hashtags", []))
    tags = [t.lstrip("#") for t in (up.get("hashtags") or [])]
    if not tags:
        draft = json.load(open(os.path.join(b, "upload_draft.json"), encoding="utf-8"))
        tags = [t.lstrip("#") for t in draft.get("hashtags", [])]
    return title.strip()[:100], desc.strip()[:4900], tags[:15]


def upload(yt, file, title, desc, tags, publish_at):
    from googleapiclient.http import MediaFileUpload
    body = {"snippet": {"title": title, "description": desc, "tags": tags,
                        "categoryId": CATEGORY_HOWTO, "defaultLanguage": "ko"},
            "status": {"privacyStatus": "private", "publishAt": publish_at,
                       "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(file, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"    …{int(st.progress()*100)}%", flush=True)
    return resp["id"]


def schedule(start, hour, dry, slugs=None):
    day = dt.datetime.strptime(start, "%Y-%m-%d").replace(hour=hour, minute=0, second=0,
                                                          microsecond=0, tzinfo=KST)
    plan = []
    for i, slug in enumerate(slugs or ORDER):
        f = os.path.join(ROOT, "work", slug, "output.mp4")
        if not os.path.exists(f):
            raise SystemExit(f"영상 없음: {f}")
        when = day + dt.timedelta(days=i)
        title, desc, tags = _meta(slug)
        plan.append((slug, f, title, desc, tags, when))

    print(f"\n예약 계획 ({len(plan)}편 / 매일 {hour:02d}:00 KST)")
    for slug, _, title, _, _, when in plan:
        print(f"  {when.strftime('%m/%d(%a) %H:%M')}  {slug:16s} {title.splitlines()[0][:44]}")
    if dry:
        print("\n--dry-run 이라 업로드하지 않았습니다."); return

    yt = get_service(); _guard(yt)
    done = []
    log = os.path.join(ROOT, "work", "_upload_log.json")
    for slug, f, title, desc, tags, when in plan:
        pub = when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n▶ {slug} → {when.strftime('%m/%d %H:%M KST')}")
        vid = upload(yt, f, title, desc, tags, pub)
        print(f"  https://youtu.be/{vid}")
        done.append({"slug": slug, "video_id": vid, "publish_at_kst": when.isoformat(),
                     "url": f"https://youtu.be/{vid}"})
        json.dump(done, open(log, "w"), ensure_ascii=False, indent=2)
    print(f"\n{len(done)}편 예약 완료 → {log}")
    print("⚠️ 유튜브 쇼핑 태그는 Studio에서 수동으로 붙이세요(공개 API 없음).")


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    if a[0] == "auth": return do_auth()
    if a[0] == "whoami": return whoami() and None
    if a[0] == "schedule":
        ap = argparse.ArgumentParser()
        ap.add_argument("--start", default=(dt.datetime.now(KST) + dt.timedelta(days=1)).strftime("%Y-%m-%d"))
        ap.add_argument("--hour", type=int, default=19)
        ap.add_argument("--dry-run", action="store_true")
        ap.add_argument("--slugs", default=None, help="쉼표 구분 슬러그 목록(기본: ORDER)")
        p = ap.parse_args(a[1:])
        return schedule(p.start, p.hour, p.dry_run,
                        [s for s in (p.slugs or "").split(",") if s] or None)
    print(__doc__)


if __name__ == "__main__":
    main()
