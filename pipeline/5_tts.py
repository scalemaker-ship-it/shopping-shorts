#!/usr/bin/env python3
"""[5] Typecast TTS — script.json 의 문장별로 서현(Seohyeon) 목소리 생성 + 타이밍 계산.

사용: python3 pipeline/5_tts.py <slug> [--gap 0.01] [--emotion normal]
산출:
  work/<slug>/tts/line_{n}.wav      문장별 음성
  work/<slug>/tts/narration.wav     전체 나레이션(문장 사이 gap 포함)
  work/<slug>/tts/timing.json       문장별 start/end/dur (자막·컷 싱크용)
"""
import sys, os, json, subprocess, urllib.request, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = "https://api.typecast.ai/v1/text-to-speech"
# 2026-08-31: 남/여 나레이션 2트랙 — script.json 의 "voice" 필드("sehee"|"piljae")로 편별 선택.
# 여=세희("남편이~" 제3자 표현) / 남=필재("와이프가~" 제3자 표현). 미지정 시 세희.
VOICES = {
    "sehee":  "tc_611c3f692fac944dff493a04",   # 세희(SeHee, 여) — 이전 기본(민지→현지→효은→서현→문정→세희)
    "piljae": "tc_68257f68bc6e3c161ab5078d",   # 필재(Piljae, 남)
}
VOICE_ID = VOICES["sehee"]  # 기본값 (main()에서 script.json voice 로 덮어씀)
MODEL = "ssfm-v30"


def load_key():
    env = os.path.join(ROOT, ".env")
    key = os.environ.get("TYPECAST_API_KEY")
    if not key and os.path.exists(env):
        for ln in open(env):
            if ln.startswith("TYPECAST_API_KEY="):
                key = ln.split("=", 1)[1].strip()
    if not key:
        # .env.example fallback (개발용)
        ex = os.path.join(ROOT, ".env.example")
        for ln in open(ex):
            if ln.startswith("TYPECAST_API_KEY="):
                key = ln.split("=", 1)[1].strip()
    return key


def tts(text, out_wav, key, emotion="normal", retries=3):
    body = json.dumps({
        "voice_id": VOICE_ID, "text": text, "model": MODEL,
        "language": "kor", "emotion": emotion,
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "X-API-KEY": key, "Content-Type": "application/json"})
    for a in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with open(out_wav, "wb") as f:
                f.write(data)
            return
        except Exception as e:
            if a == retries - 1:
                raise
            time.sleep(2)


def dur(wav):
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", wav]).decode().strip())


def trim_silence(wav, pad=0.02, thresh="-45dB"):
    # ⚠️ 2026-08-31 재조정: -25dB/0.12s 는 저음량 음절까지 잘라 나레이션이 끊겼다(cast_pan 사고).
    # 끝단은 -45dB 로 '진짜 무음'만, 내부 압축은 0.35s 넘는 구간만 0.2s 로 줄인다.
    """앞뒤 무음 제거(양끝) — 문장 사이 늘어짐 최소화. pad만큼만 여유 남김."""
    tmp = wav + ".trim.wav"
    filt = (f"silenceremove=start_periods=1:start_silence={pad}:start_threshold={thresh}:"
            f"detection=peak,areverse,"
            f"silenceremove=start_periods=1:start_silence={pad}:start_threshold={thresh}:"
            f"detection=peak,areverse,"
            # 문장 내부 무음 압축: 0.35s 넘는 무음만 0.2s 로 — 음절 보호(2026-08-31 재조정)
            f"silenceremove=stop_periods=-1:stop_duration=0.35:stop_silence=0.2:stop_threshold=-45dB")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
                    "-af", filt, tmp], check=True)
    os.replace(tmp, wav)


def normalize_loudness(wav, target_i=-16.0):
    """문장별 볼륨 평준화(2026-08-31) — loudnorm 측정 후 선형 게인만 적용.
    (클립이 짧아 loudnorm 다이내믹 모드를 쓰면 문장 안에서 출렁임 → 측정+volume 게인이 안전)"""
    import re as _re
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", wav, "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = _re.search(r'"input_i"\s*:\s*"(-?[\d.]+)"', out)
    if not m:
        return
    gain = target_i - float(m.group(1))
    tmp = wav + ".norm.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
                    "-af", f"volume={gain:.2f}dB", "-ar", "44100", tmp], check=True)
    os.replace(tmp, wav)


def main():
    args = sys.argv[1:]
    slug = args[0]
    gap = float(args[args.index("--gap") + 1]) if "--gap" in args else 0.01
    emotion = args[args.index("--emotion") + 1] if "--emotion" in args else "happy"
    key = load_key()
    assert key, "TYPECAST_API_KEY 없음"
    base = os.path.join(ROOT, "work", slug)
    script = json.load(open(os.path.join(base, "script.json")))
    global VOICE_ID
    vkey = (script.get("voice") or "sehee").lower()
    VOICE_ID = VOICES.get(vkey, VOICES["sehee"])
    print(f"[voice] {vkey} ({VOICE_ID})")
    ttsdir = os.path.join(base, "tts")
    os.makedirs(ttsdir, exist_ok=True)

    # --wavs 모드: Typecast 대신 이미 준비된 wav(예: 클론 목소리) 사용
    wav_override = None
    if "--wavs" in args:
        wav_override = [p for p in args[args.index("--wavs") + 1].split(",") if p]
        assert len(wav_override) == len(script["lines"]), "wav 개수 불일치"

    timing, t = [], 0.0
    concat_parts = []
    for i, line in enumerate(script["lines"], 1):
        wav = os.path.join(ttsdir, f"line_{i}.wav")
        if wav_override:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_override[i - 1],
                            "-ar", "44100", "-ac", "1", wav], check=True)
        else:
            tts(line["tts"], wav, key, emotion)
        trim_silence(wav)   # 앞뒤 무음 제거
        normalize_loudness(wav)   # 문장별 볼륨 일정하게(2026-08-31)
        d = dur(wav)
        timing.append({"n": i, "tts": line["tts"], "sub": line.get("sub", ""),
                       "sub_text": line.get("sub_text"),
                       "scene": line.get("scene", ""),
                       "start": round(t, 3), "end": round(t + d, 3), "dur": round(d, 3)})
        concat_parts.append((wav, d))
        t += d + gap
        print(f"[{i}] {d:5.2f}s  {line.get('sub',''):10s}  {line['tts']}")

    # 전체 나레이션 합치기 (문장 사이 gap 무음)
    filt, inputs, idx = [], [], 0
    for wav, d in concat_parts:
        inputs += ["-i", wav]
        filt.append(f"[{idx}:a]")
        idx += 1
        # gap silence
        filt.append(f"aevalsrc=0:d={gap}:s=44100[g{idx}];[g{idx}]")
    narr = os.path.join(ttsdir, "narration.wav")
    # 간단히: 각 wav + gap 을 concat
    seg = ttsdir + "/_concat.txt"
    # 무음 gap 파일 생성
    silence = ttsdir + "/_gap.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anullsrc=r=44100:cl=mono", "-t", str(gap), silence], check=True)
    with open(seg, "w") as f:
        for i, (wav, d) in enumerate(concat_parts):
            f.write(f"file '{os.path.abspath(wav)}'\n")
            if i < len(concat_parts) - 1:
                f.write(f"file '{os.path.abspath(silence)}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", seg, "-c", "copy", narr], check=True)

    total = dur(narr)
    json.dump({"total": round(total, 3), "gap": gap, "emotion": emotion, "lines": timing},
              open(os.path.join(ttsdir, "timing.json"), "w"), ensure_ascii=False, indent=2)
    print(f"\n나레이션 총 {total:.2f}s → {narr}")
    print(f"timing.json 저장 완료")


if __name__ == "__main__":
    main()
