#!/usr/bin/env python3
"""공통 설정 로더 — 레포 루트의 .env 와 환경변수를 합쳐서 읽는다.

개인 계정 정보(채널 ID, API 키, 업로드 순서)는 코드에 박지 않고 전부 여기를 통한다.
포크한 사람은 `cp .env.example .env` 후 .env 만 채우면 된다.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dotenv(path=None):
    """KEY=VALUE 형식 파일을 dict 로 읽는다. 없으면 빈 dict."""
    path = path or os.path.join(ROOT, ".env")
    d = {}
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    return d


_FILE = dotenv()


def get(key, default=None):
    """환경변수 우선, 없으면 .env, 없으면 default."""
    v = os.environ.get(key) or _FILE.get(key)
    return v if v else default


def require(key, hint=""):
    v = get(key)
    if not v:
        raise SystemExit(f"{key} 가 없습니다. .env 에 설정하세요.{(' ' + hint) if hint else ''}\n"
                         f"  (cp .env.example .env)")
    return v


def channel_id():
    """업로드 대상 유튜브 채널 ID. 오업로드 방지 가드에 쓰인다."""
    return require("YT_CHANNEL_ID", "유튜브 → 설정 → 고급 설정에서 확인할 수 있습니다.")


def publish_hour():
    return int(get("YT_PUBLISH_HOUR", "19"))


def upload_order():
    """업로드 순서(slug 목록). 미지정이면 work/ 안의 폴더를 이름순으로."""
    raw = get("YT_UPLOAD_ORDER")
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    work = os.path.join(ROOT, "work")
    if not os.path.isdir(work):
        return []
    return sorted(n for n in os.listdir(work)
                  if not n.startswith((".", "_"))
                  and os.path.isdir(os.path.join(work, n)))
