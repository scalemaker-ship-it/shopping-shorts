#!/usr/bin/env python3
"""[4] 편집 — 3소스 몽타주(1-2-3 인터리브) + 타이틀/자막(PIL) + 오디오 믹스.
단계:
  python3 pipeline/4_edit.py <slug> montage   # 비주얼 몽타주만
  python3 pipeline/4_edit.py <slug> text       # 타이틀+자막 PNG 렌더 + 오버레이
  python3 pipeline/4_edit.py <slug> audio      # 나레이션+BGM 믹스 → 최종
  python3 pipeline/4_edit.py <slug> all
"""
import sys, os, json, subprocess

import persona as persona_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30

def base(slug): return os.path.join(ROOT, "work", slug)

# ── 몽타주 세그먼트 스펙 (source: 1/2/3, in: 시작초, line: 매칭 나레이션 라인) ──
# 각 라인의 '시각 구간'을 소속 세그먼트가 균등 분할 → dur 은 timing.json 에서 자동 계산.
SEG_TARGET = 1.9   # 세그먼트 목표 길이(초) — 컷 전환 리듬

def build_montage(slug):
    b = base(slug)
    timing = json.load(open(os.path.join(b, "tts", "timing.json")))
    total = timing["total"]
    srcs = {i: os.path.join(b, "sources", f"{i}.mp4") for i in (1, 2, 3)}
    srcdur = {i: float(subprocess.check_output(["ffprobe","-v","error","-show_entries",
        "format=duration","-of","default=nk=1:nw=1", srcs[i]]).decode()) for i in (1,2,3)}
    # 나레이션 전체 길이를 세그먼트로 타일링(줄 수 무관). 소스 1-2-3 순환(인접중복 없음).
    n = max(6, round(total / SEG_TARGET))
    seg_dur = (total / n) * 1.02          # 살짝 여유(끝 잘림 방지)
    seq = [(k % 3) + 1 for k in range(n)]

    # ── 페르소나 컷 삽입 (prd §2-1) ──────────────────────────────
    # plan.json 이 지정한 나레이션 줄마다, 그 줄과 겹치는 첫 세그먼트를 페르소나 클립으로 교체.
    plan = persona_mod.load_plan(slug)
    pseg = {}                              # {세그먼트 index: 클립 경로}
    if plan:
        lines = timing["lines"]
        for line_no, clip in sorted(plan.items()):
            ln = next((l for l in lines if l["n"] == line_no), None)
            if ln is None:
                print(f"[persona] ⚠️ 줄 {line_no} 없음, 건너뜀"); continue
            idx = min(int(ln["start"] / seg_dur), n - 1)
            while idx in pseg and idx + 1 < n:   # 같은 세그먼트에 두 컷이 겹치면 밀어냄
                idx += 1
            pseg[idx] = clip
            srcs[f"P{idx}"] = clip
            srcdur[f"P{idx}"] = float(subprocess.check_output(["ffprobe","-v","error",
                "-show_entries","format=duration","-of","default=nk=1:nw=1", clip]).decode())
            seq[idx] = f"P{idx}"
            print(f"[persona] 줄{line_no} (t={ln['start']:.1f}s) → seg{idx} = {os.path.basename(clip)}")
    # ────────────────────────────────────────────────────────────

    from collections import Counter
    uses = Counter(seq)
    src_k = {1: 0, 2: 0, 3: 0}
    inputs, filt, labels = [], [], []
    for i, src in enumerate(seq):
        sd = srcdur[src]
        if isinstance(src, str):            # 페르소나 클립: 항상 처음부터, 여백 로직 미적용
            dur = min(seg_dur, sd - 0.02)
            inputs += ["-i", srcs[src]]
            filt.append(
                f"[{i}:v]trim=start=0:duration={dur:.3f},setpts=PTS-STARTPTS,"
                f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},fps={FPS},setsar=1[v{i}]")
            labels.append(f"[v{i}]")
            continue
        dur = min(seg_dur, sd - 0.1)
        k, nn = src_k[src], uses[src]
        m = min(sd * 0.06, 3.0)                      # 앞뒤 여백(인트로/아웃트로 텍스트 회피)
        inpt = m + (sd - dur - 2 * m) * (k / max(nn - 1, 1)) if sd > dur + 2 * m else 0.0
        inpt = max(0.0, min(inpt, sd - dur - 0.05))
        src_k[src] += 1
        inputs += ["-i", srcs[src]]
        filt.append(
            f"[{i}:v]trim=start={inpt:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"scale={int(W*1.08)}:{int(H*1.08)}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},fps={FPS},setsar=1[v{i}]")
        labels.append(f"[v{i}]")
    filt.append("".join(labels) + f"concat=n={n}:v=1:a=0[out]")
    out = os.path.join(b, "montage.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(filt), "-map", "[out]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", out]
    subprocess.run(cmd, check=True)
    d = float(subprocess.check_output(["ffprobe","-v","error","-show_entries",
        "format=duration","-of","default=nk=1:nw=1",out]).decode())
    print(f"[montage] {out}  {d:.2f}s  ({n} segments)")
    return out

FONTS = os.path.join(ROOT, "assets", "fonts")
TITLE_FONT = os.path.join(FONTS, "Jalnan.ttf")        # 여기어때 잘난체 (2026-08-31 조선굵은고딕 시도 후 같은 날 원복)
SUB_FONT = os.path.join(FONTS, "MemomentKkukkukk.ttf")   # 메모먼트 꾹꾹체 (2026-08-28)
TITLE_LETTER = 0              # 타이틀 자간(px) — 2026-08-31 -2→-1→0
SUB_LETTER = -1                # 자막 자간(px)
SUB_STROKE = 4                 # 자막 외곽선(px) — 2026-08-28 8→4 로 얇게
SUB_Y = 0.45                   # 자막 세로 위치(H 비율) — 2026-08-31 0.655→0.45 (랄리나홈 참고, 화면 중앙부)
YEONDU = (170, 235, 60, 255)  # 연두 #AAEB3C (타이틀 강조)
WHITE = (255, 255, 255, 255)
NEON_YELLOW = (255, 242, 0, 255)  # 형광 노랑 #FFF200 (자막 키워드 강조, 2026-08-31)
SPEED = 1.3                    # 최종 배속 (2026-08-31 1.4 시도 후 "너무 빠르다"로 1.3 원복)


def _text_layer(lines, y_start, font_path, size, stroke=12,
                shadow=(0, 6), shadow_blur=6, line_gap=1.06, letter=0):
    """중앙정렬 텍스트를 1080x1920 투명 레이어에 그림. lines=[(text,color)]."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    font = ImageFont.truetype(font_path, size)
    # 그림자 레이어(블러)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shd = ImageDraw.Draw(sh)
    drw = ImageDraw.Draw(img)
    y = y_start
    for line in lines:
        # line = (text, color) 또는 [(seg, color), ...] (조각별 색 — 형광 키워드용)
        segs = line if isinstance(line, list) else [line]
        text = "".join(s for s, _ in segs)
        col = segs[0][1]
        if letter or len(segs) > 1:   # 자간/멀티컬러: 글자별 렌더
            chars = [(ch, c) for s, c in segs for ch in s]
            widths = [drw.textlength(ch, font=font) for ch, _ in chars]
            total = sum(widths) + letter * max(len(chars) - 1, 0)
            x = (W - total) / 2
            for (ch, c), w in zip(chars, widths):
                shd.text((x + shadow[0], y + shadow[1]), ch, font=font,
                         fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
                drw.text((x, y), ch, font=font, fill=c,
                         stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                x += w + letter
        else:
            bbox0 = drw.textbbox((0, 0), text, font=font, stroke_width=stroke)
            x = (W - (bbox0[2] - bbox0[0])) // 2 - bbox0[0]
            shd.text((x + shadow[0], y + shadow[1]), text, font=font,
                     fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
            drw.text((x, y), text, font=font, fill=col,
                     stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        bbox = drw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        y += int((bbox[3] - bbox[1]) * line_gap) + int(size * 0.06)
    sh = sh.filter(ImageFilter.GaussianBlur(shadow_blur))
    return Image.alpha_composite(sh, img)


def _top_scrim(height=560, top_alpha=205):
    """상단 그라데이션 스크림(타이틀 가독성) — 이미지#5 스타일. 상단 진하게→아래로 사라짐."""
    from PIL import Image
    import numpy as np
    ramp = (top_alpha * (1 - (np.arange(height) / height) ** 1.35)).astype("uint8")
    arr = np.zeros((H, W, 4), dtype="uint8")
    arr[:height, :, 3] = ramp[:, None]
    return Image.fromarray(arr, "RGBA")


def _chunk(text, max_chars=10):
    """문장을 쉼표/문장부호 기준으로 먼저 끊고, 그 조각이 max_chars(공백 제외)를 넘을 때만
    어절 단위로 추가 분할. 문장 끝이나 쉼표가 아닌 곳에서 임의로 끊기지 않게 함."""
    import re
    segments = [s.strip() for s in re.split(r"(?<=[,，、])\s*", text.strip()) if s.strip()]
    chunks = []
    for seg in segments:
        if len(seg.replace(" ", "")) <= max_chars:
            chunks.append(seg)
            continue
        cur = ""
        for w in seg.split(" "):
            cand = (cur + " " + w).strip()
            if len(cand.replace(" ", "")) <= max_chars or not cur:
                cur = cand
            else:
                chunks.append(cur)
                cur = w
        if cur:
            chunks.append(cur)
    return chunks


def _parse_hl(text, base_col=WHITE, hl_col=NEON_YELLOW):
    """'*단어*' 마크업 → [(조각, 색)] 세그먼트. 강조 조각은 형광 노랑(2026-08-31)."""
    import re
    segs = []
    for part in re.split(r"(\*[^*]+\*)", text):
        if not part:
            continue
        if part.startswith("*") and part.endswith("*") and len(part) > 2:
            segs.append((part[1:-1], hl_col))
        else:
            segs.append((part.replace("*", ""), base_col))
    return segs or [(text, base_col)]


def _wrap(text, font, max_w):
    """폭 max_w 에 맞춰 어절 단위 워드랩 → 줄 리스트."""
    from PIL import ImageDraw, Image
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textbbox((0, 0), test, font=font)[2] <= max_w or not cur:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def render_overlays(slug):
    from PIL import Image
    b = base(slug)
    script = json.load(open(os.path.join(b, "script.json")))
    from PIL import ImageFont
    ov = os.path.join(b, "overlays")
    os.makedirs(ov, exist_ok=True)
    # ── 타이틀 (Pretendard-ExtraBold 크게 2줄, line1 흰색 / line2 연두, 그라데이션) ──
    t = script["title"]
    title = _top_scrim()
    layer = _text_layer([(t["line1"], WHITE), (t["line2"], YEONDU)],
                        y_start=145, font_path=TITLE_FONT, size=140,
                        stroke=13, shadow=(0, 7), shadow_blur=8, line_gap=1.04,
                        letter=TITLE_LETTER)
    title = Image.alpha_composite(title, layer)
    title.save(os.path.join(ov, "title.png"))
    # ── 자막 (나레이션을 10자 이내 조각으로 끊어 1줄씩 순차 표시) ──
    timing = json.load(open(os.path.join(b, "tts", "timing.json")))
    SUB_SIZE = 74
    events = []
    for i, L in enumerate(timing["lines"], 1):
        # 자막은 script.json 의 sub_text 가 있으면 그걸 쓴다(TTS엔 안 읽히는 "ㅎㅎ"·물결 표현용)
        chunks = _chunk(L.get("sub_text") or L["tts"], 10)
        total = sum(len(c.replace(" ", "").replace("*", "")) for c in chunks) or 1
        s, e = L["start"], L["end"]
        cursor = s
        for j, c in enumerate(chunks, 1):
            d = (e - s) * len(c.replace(" ", "").replace("*", "")) / total
            fn = f"sub_{i}_{j}.png"
            sub = _text_layer([_parse_hl(c)], y_start=int(H * SUB_Y),
                              font_path=SUB_FONT, size=SUB_SIZE, stroke=SUB_STROKE,
                              shadow=(0, 4), shadow_blur=5, letter=SUB_LETTER)
            sub.save(os.path.join(ov, fn))
            events.append({"file": fn, "start": round(cursor, 3),
                           "end": round(cursor + d, 3), "text": c.replace("*", "")})
            cursor += d
    json.dump(events, open(os.path.join(ov, "sub_events.json"), "w"),
              ensure_ascii=False, indent=2)
    print(f"[overlays] title + {len(events)} 자막조각 → {ov}")


def apply_overlays(slug):
    b = base(slug)
    ov = os.path.join(b, "overlays")
    events = json.load(open(os.path.join(ov, "sub_events.json")))
    montage = os.path.join(b, "montage.mp4")
    inputs = ["-i", montage, "-i", os.path.join(ov, "title.png")]
    for ev in events:
        inputs += ["-i", os.path.join(ov, ev["file"])]
    filt = ["[0:v][1:v]overlay=0:0[v0]"]
    prev = "v0"
    for idx, ev in enumerate(events, 1):
        inp = idx + 1  # input index of chunk png (0=montage, 1=title)
        nxt = f"v{idx}"
        filt.append(f"[{prev}][{inp}:v]overlay=0:0:enable='between(t,{ev['start']},{ev['end']})'[{nxt}]")
        prev = nxt
    out = os.path.join(b, "video_noaudio.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(filt), "-map", f"[{prev}]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", out]
    subprocess.run(cmd, check=True)
    print(f"[text] {out}")
    return out


def _find_bgm():
    d = os.path.join(ROOT, "bgm")
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, f) for f in sorted(os.listdir(d))
             if f.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))]
    return cands[0] if cands else None


def mix_audio(slug, bgm_vol=0.28, use_bgm=True):  # 2026-08-31 0.11→0.28 (BGM 안 들림 피드백)
    b = base(slug)
    video = os.path.join(b, "video_noaudio.mp4")
    narr = os.path.join(b, "tts", "narration.wav")
    dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries",
        "format=duration","-of","default=nk=1:nw=1", video]).decode())
    out = os.path.join(b, "output.mp4")
    bgm = _find_bgm() if use_bgm else None
    vspeed = f"[0:v]setpts=PTS/{SPEED}[v]"   # 영상 1.1배속
    if bgm:
        # BGM 루프 → 볼륨↓ → 나레이션 사이드체인 덕킹 → 믹스 → 1.1배속
        afilt = (
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad=pad_dur=0.3,"
            f"asplit=2[narrA][narrB];"
            f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={bgm_vol},"
            f"atrim=0:{dur},afade=t=out:st={dur-1.2}:d=1.2[bg];"
            f"[bg][narrA]sidechaincompress=threshold=0.12:ratio=3:attack=8:release=280[bgduck];"  # 덕킹 완화(2026-08-31)
            f"[bgduck][narrB]amix=inputs=2:duration=first:normalize=0,atempo={SPEED}[a]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-i", video, "-i", narr, "-stream_loop", "-1", "-i", bgm,
               "-filter_complex", f"{vspeed};{afilt}",
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", out]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", narr,
               "-filter_complex", f"{vspeed};[1:a]atempo={SPEED}[a]",
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    subprocess.run(cmd, check=True)
    print(f"[audio] BGM={'있음: '+os.path.basename(bgm) if bgm else '없음(나레이션만)'}  speed={SPEED}x  → {out}")
    return out


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--no-bgm"]
    no_bgm = "--no-bgm" in sys.argv          # BGM 없이 나레이션만 (2026-08-24 옵션 추가)
    slug, step = argv[0], (argv[1] if len(argv) > 1 else "all")
    if step in ("montage", "all"):
        build_montage(slug)
    if step in ("text", "all"):
        render_overlays(slug)
        apply_overlays(slug)
    if step in ("audio", "all"):
        mix_audio(slug, use_bgm=not no_bgm)
