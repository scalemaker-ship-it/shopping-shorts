#!/usr/bin/env python3
"""[4] 편집 — 3소스 몽타주(1-2-3 인터리브) + 타이틀/자막(PIL) + 오디오 믹스.
단계:
  python3 pipeline/4_edit.py <slug> montage   # 비주얼 몽타주만
  python3 pipeline/4_edit.py <slug> text       # 타이틀+자막 PNG 렌더 + 오버레이
  python3 pipeline/4_edit.py <slug> audio      # 나레이션+BGM 믹스 → 최종
  python3 pipeline/4_edit.py <slug> all
"""
import sys, os, json, subprocess

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
    from collections import Counter
    uses = Counter(seq)
    src_k = {1: 0, 2: 0, 3: 0}
    inputs, filt, labels = [], [], []
    for i, src in enumerate(seq):
        sd = srcdur[src]
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
TITLE_FONT = os.path.join(FONTS, "Jalnan.ttf")        # 여기어때 잘난체
SUB_FONT = os.path.join(FONTS, "Pretendard-ExtraBold.otf")
TITLE_LETTER = -2             # 타이틀 자간(px)
YEONDU = (170, 235, 60, 255)  # 연두 #AAEB3C (타이틀 강조)
WHITE = (255, 255, 255, 255)
SPEED = 1.3                    # 최종 배속


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
    for text, col in lines:
        if letter:   # 자간 적용: 글자별 렌더
            widths = [drw.textlength(ch, font=font) for ch in text]
            total = sum(widths) + letter * max(len(text) - 1, 0)
            x = (W - total) / 2
            for ch, w in zip(text, widths):
                shd.text((x + shadow[0], y + shadow[1]), ch, font=font,
                         fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
                drw.text((x, y), ch, font=font, fill=col,
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
    """문장을 어절 단위로 max_chars(공백 제외) 이내 조각들로 자연스럽게 끊음."""
    chunks, cur = [], ""
    for w in text.split(" "):
        cand = (cur + " " + w).strip()
        if len(cand.replace(" ", "")) <= max_chars or not cur:
            cur = cand
        else:
            chunks.append(cur)
            cur = w
    if cur:
        chunks.append(cur)
    return chunks


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
        chunks = _chunk(L["tts"], 10)
        total = sum(len(c.replace(" ", "")) for c in chunks) or 1
        s, e = L["start"], L["end"]
        cursor = s
        for j, c in enumerate(chunks, 1):
            d = (e - s) * len(c.replace(" ", "")) / total
            fn = f"sub_{i}_{j}.png"
            sub = _text_layer([(c, WHITE)], y_start=int(H * 0.655),
                              font_path=SUB_FONT, size=SUB_SIZE, stroke=8,
                              shadow=(0, 4), shadow_blur=5)
            sub.save(os.path.join(ov, fn))
            events.append({"file": fn, "start": round(cursor, 3),
                           "end": round(cursor + d, 3), "text": c})
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


def mix_audio(slug, bgm_vol=0.11):
    b = base(slug)
    video = os.path.join(b, "video_noaudio.mp4")
    narr = os.path.join(b, "tts", "narration.wav")
    dur = float(subprocess.check_output(["ffprobe","-v","error","-show_entries",
        "format=duration","-of","default=nk=1:nw=1", video]).decode())
    out = os.path.join(b, "output.mp4")
    bgm = _find_bgm()
    vspeed = f"[0:v]setpts=PTS/{SPEED}[v]"   # 영상 1.1배속
    if bgm:
        # BGM 루프 → 볼륨↓ → 나레이션 사이드체인 덕킹 → 믹스 → 1.1배속
        afilt = (
            f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,apad=pad_dur=0.3,"
            f"asplit=2[narrA][narrB];"
            f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={bgm_vol},"
            f"atrim=0:{dur},afade=t=out:st={dur-1.2}:d=1.2[bg];"
            f"[bg][narrA]sidechaincompress=threshold=0.04:ratio=5:attack=8:release=280[bgduck];"
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
    slug, step = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "all")
    if step in ("montage", "all"):
        build_montage(slug)
    if step in ("text", "all"):
        render_overlays(slug)
        apply_overlays(slug)
    if step in ("audio", "all"):
        mix_audio(slug)
