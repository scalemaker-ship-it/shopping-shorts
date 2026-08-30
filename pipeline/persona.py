#!/usr/bin/env python3
"""페르소나 컷 빌더 — 고정 페르소나('란이') 스틸을 모션 클립으로 만든다.

prd §2-1 (페르소나) 구현.  하이브리드 방식:
  · 페르소나 컷 = 훅/고민/사용법/CTA 등 지정한 나레이션 줄에만 삽입
  · 나머지 줄 = 기존 틱톡 소재 1-2-3 인터리브 (4_edit.py)

사용법:
    python3 pipeline/persona.py <slug> clips     # persona/*.png → persona/clips/*.mp4
    python3 pipeline/persona.py <slug> plan      # persona/plan.json 기본값 생성

폴더 규약:
    work/<slug>/persona/
        p1.png … pN.png        # codex-image 등으로 만든 9:16 스틸
        clips/p1.mp4 …          # 이 스크립트가 생성 (켄번스 모션)
        plan.json               # {"1": "p1", "2": "p3", "5": "p2", "9": "p4"}
                                #  key = 나레이션 줄 번호(1-base), value = 컷 이름
"""
import sys, os, json, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
CLIP_DUR = 3.0          # 스틸 1장에서 뽑는 모션 클립 길이(초). 세그먼트보다 길게 잡아 여유.
ZOOM_MAX = 1.14         # 켄번스 최대 배율

def base(slug): return os.path.join(ROOT, "work", slug)
def pdir(slug):  return os.path.join(base(slug), "persona")

# 얼굴 최소·손 위주 (2026-08-28 확정) — 9줄 대본 기준 기본 배치
DEFAULT_PLAN = {
    "1": "p1",   # ① 어텐션 훅        — 유일한 얼굴 컷
    "2": "p3",   # ② 내 고민 고백      — 손(문제 상황)
    "5": "p2",   # ⑤ 사용법           — 손(제품 조작)
    "9": "p4",   # ⑨ CTA             — 손(제품 제시)
}


def make_plan(slug, force=False):
    d = pdir(slug)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "plan.json")
    if os.path.exists(p) and not force:
        print(f"[plan] 이미 있음: {p}")
        return p
    json.dump(DEFAULT_PLAN, open(p, "w"), ensure_ascii=False, indent=2)
    print(f"[plan] 생성: {p}\n{json.dumps(DEFAULT_PLAN, ensure_ascii=False)}")
    return p


def _kenburns(src_png, out_mp4, idx):
    """스틸 → 켄번스 모션 클립. 홀수는 줌인, 짝수는 줌아웃 + 미세 팬."""
    frames = int(CLIP_DUR * FPS)
    zoom_in = (idx % 2 == 1)
    step = (ZOOM_MAX - 1.0) / frames
    if zoom_in:
        z = f"min(zoom+{step:.6f},{ZOOM_MAX})"
    else:
        # 시작을 최대배율로 두고 줄여나간다
        z = f"max({ZOOM_MAX}-on*{step:.6f},1.0)"
    # 중앙 기준 + 프레임 진행에 따른 아주 약한 수평 드리프트
    drift = 12 if zoom_in else -12
    x = f"iw/2-(iw/zoom/2)+{drift}*on/{frames}"
    y = f"ih/2-(ih/zoom/2)"
    vf = (f"scale={W*3}:{H*3}:force_original_aspect_ratio=increase,"
          f"crop={W*3}:{H*3},"
          f"zoompan=z='{z}':d={frames}:x='{x}':y='{y}':s={W}x{H}:fps={FPS},"
          f"setsar=1")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", src_png,
           "-t", str(CLIP_DUR), "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-r", str(FPS), out_mp4]
    subprocess.run(cmd, check=True)


def build_clips(slug):
    d = pdir(slug)
    outdir = os.path.join(d, "clips")
    os.makedirs(outdir, exist_ok=True)
    pngs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
    if not pngs:
        sys.exit(f"[persona] {d} 에 스틸 PNG 가 없습니다.")
    made = []
    for i, fn in enumerate(pngs, 1):
        name = os.path.splitext(fn)[0]
        out = os.path.join(outdir, f"{name}.mp4")
        _kenburns(os.path.join(d, fn), out, i)
        made.append(out)
        print(f"[persona] {fn} → {os.path.relpath(out, ROOT)}  ({CLIP_DUR}s)")
    return made


def load_plan(slug):
    """{줄번호(int): 클립 절대경로} 반환. plan.json 없거나 persona 폴더 없으면 {}."""
    d = pdir(slug)
    p = os.path.join(d, "plan.json")
    if not os.path.exists(p):
        return {}
    raw = json.load(open(p, encoding="utf-8"))
    out = {}
    for line_no, name in raw.items():
        clip = os.path.join(d, "clips", f"{name}.mp4")
        if os.path.exists(clip):
            out[int(line_no)] = clip
        else:
            print(f"[persona] ⚠️ 클립 없음, 건너뜀: {clip}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    slug, step = sys.argv[1], sys.argv[2]
    if step == "clips":
        build_clips(slug)
    elif step == "plan":
        make_plan(slug, force="--force" in sys.argv)
    else:
        sys.exit(f"unknown step: {step}")
