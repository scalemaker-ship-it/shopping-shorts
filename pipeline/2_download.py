#!/usr/bin/env python3
"""[2] 틱톡 소재 다운로드 — tikwm(워터마크 제거) API 사용. 쿠키/로그인 불필요.

사용:
  python3 pipeline/2_download.py <slug> <tiktok_url> [<tiktok_url> ...]
  # 또는 후보 검수용: python3 pipeline/2_download.py <slug> --contact <url> [...]

산출: work/<slug>/sources/<name>.mp4  (+ --contact 시 프레임 콘택트시트)
"""
import sys, os, json, subprocess, urllib.parse, urllib.request, re, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.tikwm.com/api/"


def fetch_meta(url):
    q = urllib.parse.urlencode({"url": url, "hd": 1})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if d.get("code") != 0:
        raise RuntimeError(f"tikwm error: {d.get('msg')} for {url}")
    return d["data"]


def download(play_url, out_path):
    req = urllib.request.Request(play_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        f.write(r.read())
    return os.path.getsize(out_path)


def contact_sheet(mp4, out_png, cols=6):
    """영상에서 cols장 균등 추출 → 가로 콘택트시트(중국어 검수용)."""
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", mp4]).decode().strip())
    tmpdir = out_png + "_frames"
    os.makedirs(tmpdir, exist_ok=True)
    for i in range(cols):
        t = dur * (i + 0.5) / cols
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}",
                        "-i", mp4, "-frames:v", "1", "-vf", "scale=320:-1",
                        f"{tmpdir}/f{i}.png"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmpdir}/f%d.png",
                    "-filter_complex", f"tile={cols}x1", out_png], check=True)
    return out_png


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    slug = args[0]
    contact = "--contact" in args
    urls = [a for a in args[1:] if a.startswith("http")]
    srcdir = os.path.join(ROOT, "work", slug, "sources")
    os.makedirs(srcdir, exist_ok=True)
    manifest = []
    for i, url in enumerate(urls, 1):
        try:
            m = fetch_meta(url)
            user = re.search(r"@([^/]+)/", url)
            name = f"c{i}_{user.group(1) if user else 'src'}"
            play = m.get("hdplay") or m.get("play")
            mp4 = os.path.join(srcdir, name + ".mp4")
            size = download(play, mp4)
            entry = {"n": i, "url": url, "file": mp4, "title": m.get("title", ""),
                     "duration": m.get("duration"), "size_kb": size // 1024,
                     "author": m.get("author", {}).get("unique_id", "")}
            if contact:
                sheet = contact_sheet(mp4, os.path.join(srcdir, name + "_sheet.png"))
                entry["sheet"] = sheet
            manifest.append(entry)
            print(f"[OK] {name}  {m.get('duration')}s  {size//1024}KB  {m.get('title','')[:60]}")
        except Exception as e:
            print(f"[FAIL] {url}\n       {e}")
        time.sleep(1)  # tikwm rate limit
    with open(os.path.join(ROOT, "work", slug, "sources", "_manifest.json"), "w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\n{len(manifest)} downloaded → {srcdir}")


if __name__ == "__main__":
    main()
