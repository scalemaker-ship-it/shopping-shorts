#!/usr/bin/env python3
"""에피소드 원샷 빌드 (2026-08-31 신설).

spec JSON(product/script/upload_draft 를 하나로 묶은 파일)을 받아
work/<slug>/ 에 3개 json 을 쓰고 TTS→montage→text→audio→upload_meta 까지 한 번에 돈다.

  python3 pipeline/make_episode.py <spec.json> [--skip-tts]

spec 형식: {"product": {...}, "script": {...}, "upload": {...}}
※ 소스 1/2/3.mp4 는 미리 work/<slug>/sources/ 에 준비돼 있어야 한다.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    subprocess.run([sys.executable, os.path.join(ROOT, "pipeline", args[0]), *args[1:]],
                   cwd=ROOT, check=True)


def main():
    spec_path = sys.argv[1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    slug = spec["product"]["slug"]
    b = os.path.join(ROOT, "work", slug)
    os.makedirs(b, exist_ok=True)
    for key, fn in (("product", "product.json"), ("script", "script.json"),
                    ("upload", "upload_draft.json")):
        json.dump(spec[key], open(os.path.join(b, fn), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    for i in (1, 2, 3):
        f = os.path.join(b, "sources", f"{i}.mp4")
        assert os.path.exists(f), f"소스 없음: {f}"

    # ⚠️ 3소스 짬뽕 가드(2026-08-31): 한 원본을 구간분할해 채우면 저작권 변형 효과가 죽는다.
    # product.json 의 reference.sources[].origin 에서 서로 다른 틱톡 영상 ID 개수를 센다.
    import re
    ids = set()
    for s in (spec["product"].get("reference", {}) or {}).get("sources", []):
        o = str(s.get("origin", ""))
        m = re.search(r"/(\d{6,})", o)
        if m:
            ids.add(m.group(1))
    if len(ids) < 3:
        msg = (f"⚠️ 서로 다른 원본 영상이 {len(ids)}개뿐입니다(3개 필요). "
               f"구간분할로 채우면 재사용콘텐츠 리스크가 올라갑니다 — 소재를 더 찾거나 제품을 바꾸세요.")
        if "--allow-few-sources" not in sys.argv:
            raise SystemExit(msg + "\n   그래도 진행하려면 --allow-few-sources 를 붙이세요.")
        print(msg + " (--allow-few-sources 로 강행)")
    if "--skip-tts" not in sys.argv:
        run("5_tts.py", slug)
    run("4_edit.py", slug, "all")
    run("7_upload_meta.py", slug)
    out = os.path.join(b, "output.mp4")
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                       "format=duration", "-of", "default=nk=1:nw=1", out]).decode())
    # 검수용 프리뷰 시트
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", out,
                    "-vf", f"fps=12/{d},scale=270:-1,tile=6x2",
                    os.path.join(b, "preview_sheet.png")], check=True)
    print(f"[done] {slug}  {d:.1f}s  → {out}")


if __name__ == "__main__":
    main()
