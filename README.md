# 쇼핑쇼츠 자동화 파이프라인

> 제품 하나 정하면 → 대본·음성·편집·자막·업로드 메타까지 **명령어 한 줄로** 유튜브 쇼츠가 나옵니다.

한국어 쇼핑/리뷰 숏폼(9:16, 1080×1920)을 반자동으로 찍어내는 파이썬 + ffmpeg 파이프라인입니다.
실제로 유튜브 쇼츠 채널을 운영하면서 만든 것을 정리해 공개합니다.

```
제품 선정 → 틱톡 소재 3개 → 대본(JSON) → TTS → 3소스 몽타주 → 타이틀·자막 → BGM 믹스 → 업로드
```

**만들어지는 결과물**: 20~35초 세로 영상 + 제목/본문/해시태그가 채워진 `upload.json`

---

## 무엇이 자동이고, 무엇이 사람 몫인가

솔직하게 적습니다. **완전 자동이 아닙니다.**

| 단계 | 자동 | 사람이 해야 함 |
|---|:---:|---|
| 인기 키워드 수집 | ✅ | — |
| 틱톡 소재 검색 | ✅ | **소재 3개 최종 선택** (자막 박힌 영상 걸러내기) |
| 대본 작성 | ❌ | **직접 or LLM으로 작성** (`script` JSON) |
| TTS 음성 | ✅ | — |
| 영상 편집·자막·BGM | ✅ | — |
| 업로드 메타 | ✅ | 카피 초안은 사람이 |
| 유튜브 업로드·예약 | ✅ | 쇼핑 태그는 Studio에서 수동 (공개 API 없음) |

가장 손이 많이 가는 곳은 **소재 검수**입니다. 화면에 자막이 박힌 소재를 쓰면 결과물이 망가지므로
`--contact` 콘택트시트로 눈으로 확인하는 과정이 필요합니다.

---

## 1. 설치

### 1-1. 필수 프로그램

**ffmpeg** (영상 처리 전부를 담당 — 없으면 아무것도 안 됩니다)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt update && sudo apt install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

설치 확인:
```bash
ffmpeg -version && ffprobe -version
```

**Python 3.9 이상**

### 1-2. 레포 받고 패키지 설치

```bash
git clone https://github.com/scalemaker-ship-it/shopping-shorts.git
cd shopping-shorts

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 1-3. 폰트 넣기 (필수)

라이선스 때문에 폰트 파일은 레포에 없습니다. **2개만 받으면 됩니다.**

| 파일명 | 폰트 | 받는 곳 |
|---|---|---|
| `Jalnan.ttf` | 여기어때 잘난체 | [gccompany.co.kr/font](https://gccompany.co.kr/font) |
| `MemomentKkukkukk.ttf` | 메모먼트 꾹꾹체 | [눈누](https://noonnu.cc)에서 "메모먼트" 검색 |

받아서 `assets/fonts/` 에 **파일명 그대로** 넣으세요. 자세한 목록은 [`assets/fonts/README.md`](assets/fonts/README.md).

다른 폰트를 쓰려면 `pipeline/4_edit.py` 의 `TITLE_FONT` / `SUB_FONT` 경로를 바꾸면 됩니다.

### 1-4. BGM 넣기 (선택)

레포 루트에 `bgm/` 폴더를 만들고 mp3를 넣으면 자동으로 믹스됩니다. 없으면 나레이션만 나갑니다.
→ [`assets/BGM.md`](assets/BGM.md)

### 1-5. API 키 설정

```bash
cp .env.example .env
```

`.env` 를 열어 값을 채웁니다.

| 키 | 필수 | 발급처 |
|---|:---:|---|
| `TYPECAST_API_KEY` | ✅ | [typecast.ai](https://typecast.ai) — 로그인 후 API 키 발급 (**유료**) |
| `YT_CHANNEL_ID` | 업로드 시 | 유튜브 → 설정 → 고급 설정 (`UC...` 로 시작) |
| `GOOGLE_CLIENT_ID` / `_SECRET` | 업로드 시 | [Google Cloud Console](https://console.cloud.google.com) (아래 참고) |
| `ZERNIO_API_KEY` | 선택 | Google OAuth 대신 [Zernio](https://zernio.com) 쓸 때만 |

<details>
<summary><b>Google OAuth 클라이언트 만드는 법</b> (업로드 안 쓸 거면 건너뛰세요)</summary>

1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. **API 및 서비스 → 라이브러리** → `YouTube Data API v3` 검색 → **사용 설정**
3. **OAuth 동의 화면** → 외부 → 앱 이름 입력 → 본인 계정을 **테스트 사용자**로 추가
4. **사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **웹 애플리케이션**
   - 승인된 리디렉션 URI: `http://localhost:3000/auth/youtube/callback`
5. 나온 **클라이언트 ID / 보안 비밀**을 `.env` 에 붙여넣기

> YouTube Data API 는 하루 할당량(기본 10,000 units)이 있고, **업로드 1건당 약 1,600 units** 를
> 씁니다. 즉 하루 6편 정도가 한계입니다.

</details>

`TYPECAST_API_KEY` 없이도 **TTS를 뺀 나머지**(소재 다운로드, 몽타주, 자막)는 테스트할 수 있습니다.

---

## 2. 첫 영상 만들어보기

### 2-1. 제품 정하고 소재 구하기

```bash
# (선택) 네이버 데이터랩에서 오늘 인기 검색어 긁기
python3 pipeline/1_datalab_keywords.py --top 20

# 틱톡에서 소재 후보 검색
python3 pipeline/2_search.py "bathroom cleaning" --count 20
```

마음에 드는 영상 URL 을 골라 **콘택트시트로 자막 여부를 확인**합니다. 이게 제일 중요합니다.

```bash
python3 pipeline/2_download.py bath_spray --contact "https://www.tiktok.com/@user/video/123..."
```

생성된 콘택트시트 이미지를 열어보고 **화면에 자막이 박혀 있으면 버립니다.**
(어느 언어든 상관없이 전부 제외 — 합성한 우리 자막과 겹쳐서 망가집니다)

깨끗한 소재 **서로 다른 영상 3개**를 받습니다:

```bash
python3 pipeline/2_download.py bath_spray "URL1" "URL2" "URL3"
# → work/bath_spray/sources/1.mp4, 2.mp4, 3.mp4
```

> ⚠️ **한 영상을 잘라서 3개로 쓰면 안 됩니다.** 서로 다른 원본 3개를 1-2-3 순서로 교차
> 편집하는 게 이 파이프라인의 핵심입니다. `make_episode.py` 에 이를 막는 가드가 들어있습니다.

### 2-2. 대본 쓰기

`work/_specs/` 안에 **완성된 예시 spec 이 50개 넘게 들어있습니다.** 하나 복사해서 고치는 게 제일 빠릅니다.

```bash
cp work/_specs/bath_spray.json work/_specs/my_product.json
```

구조는 이렇습니다:

```jsonc
{
  "product": {
    "product": "욕실 타일 청소 스프레이",
    "slug": "my_product",              // work/<slug>/ 폴더명이 됩니다
    "category": "청소용품/욕실",
    "reference": {
      "sources": [                      // 서로 다른 원본 3개여야 통과
        { "name": "1.mp4", "origin": "계정명/영상ID" },
        { "name": "2.mp4", "origin": "다른계정/영상ID" },
        { "name": "3.mp4", "origin": "또다른계정/영상ID" }
      ]
    },
    "keywords": ["청소용품", "욕실청소", "물때제거"]
  },
  "script": {
    "title": { "line1": "욕실 바닥이", "line2": "안 닦이는 이유" },  // 2줄 궁금증 유도형
    "voice": "sehee",                  // sehee(여) | piljae(남) | leehyun(여)
    "lines": [ /* 나레이션 문장 배열 — 자막과 1:1로 붙습니다 */ ]
  },
  "upload": {
    "title": "클릭유도문구ㅣ제품명",
    "body_lines": ["..."],
    "hashtags": ["#청소템", "#생활꿀템"]
  }
}
```

**대본 규칙 요약** (자세한 건 [`prd.md`](prd.md)):
- 한 문장 = 자막 한 줄. **TTS로 읽는 문장과 자막이 정확히 같아야** 합니다.
- `*단어*` 로 감싸면 그 단어가 형광 노랑으로 강조됩니다.
- 훅 → 발견 스토리 → 사용법 → 효과 → CTA 순서가 가장 잘 먹혔습니다.

### 2-3. 한 방에 빌드

```bash
python3 pipeline/make_episode.py work/_specs/my_product.json
```

TTS → 몽타주 → 타이틀·자막 → BGM 믹스 → 업로드 메타까지 한 번에 돕니다.

**결과물**: `work/my_product/output.mp4` + `work/my_product/upload.json`

단계별로 돌리고 싶으면:

```bash
python3 pipeline/5_tts.py my_product          # 음성 + 타이밍
python3 pipeline/4_edit.py my_product montage # 3소스 몽타주
python3 pipeline/4_edit.py my_product text    # 타이틀 + 자막
python3 pipeline/4_edit.py my_product audio   # BGM 믹스 → 최종
python3 pipeline/7_upload_meta.py my_product  # 업로드 메타
```

TTS 비용을 아끼려면 `--skip-tts` 로 편집만 다시 돌릴 수 있습니다.

### 2-4. 업로드 (선택)

```bash
python3 pipeline/8_upload.py auth      # 1회 인증 — 브라우저에서 대상 채널 선택
python3 pipeline/8_upload.py whoami    # 채널이 맞게 연결됐는지 확인
python3 pipeline/8_upload.py schedule --start 2026-10-01 --dry-run   # 계획만 출력
python3 pipeline/8_upload.py schedule --start 2026-10-01             # 실제 예약
```

하루 1편씩 `YT_PUBLISH_HOUR`(기본 19시 KST) 예약 공개로 올라갑니다.
`YT_CHANNEL_ID` 와 다른 채널이 연결돼 있으면 **업로드 전에 중단**합니다 (오업로드 방지).

> 유튜브 쇼핑 태그는 공개 API가 없어서 **Studio에서 직접** 붙여야 합니다.

---

## 3. 폴더 구조

```
shopping-shorts/
├── pipeline/
│   ├── config.py               설정 로더 (.env → 전 스크립트 공통)
│   ├── 1_datalab_keywords.py   네이버 데이터랩 인기 검색어
│   ├── 2_search.py             틱톡 소재 검색 (tikwm)
│   ├── 2_download.py           소재 다운로드 + 콘택트시트
│   ├── 4_edit.py               몽타주·타이틀·자막·오디오 믹스  ← 핵심
│   ├── 5_tts.py                Typecast TTS + 문장 타이밍
│   ├── 7_upload_meta.py        제목/본문/해시태그 생성
│   ├── 8_upload.py             유튜브 직접 업로드 (Google OAuth)
│   ├── 8_upload_zernio.py      유튜브 업로드 (Zernio 경유)
│   ├── make_episode.py         원샷 빌드  ← 보통 이것만 씁니다
│   └── persona.py              페르소나 스틸 → 켄번스 모션 클립
├── work/
│   ├── _specs/*.json           실제로 만든 에피소드 spec 50여 개 (예시 겸 참고)
│   └── <slug>/                 에피소드 작업 폴더 (gitignore)
├── assets/
│   ├── fonts/                  폰트 (직접 받아 넣기)
│   └── BGM.md                  BGM 안내
├── prd.md                      전체 제작 규격 — 대본·자막·편집 규칙 상세
├── .env.example
└── requirements.txt
```

---

## 4. 기술적으로 참고할 만한 부분

직접 겪고 해결한 것들입니다. 비슷한 걸 만든다면 시간 아끼실 겁니다.

**ffmpeg 에 한글 자막을 넣을 때** — `drawtext` 나 libass 없이도 됩니다.
Pillow 로 텍스트를 투명 PNG 레이어에 렌더한 뒤 ffmpeg 으로 오버레이합니다
(`4_edit.py` 의 `_text_layer`). 폰트 빌드 의존성이 사라지고, 자간·외곽선·부분 색상 강조를
자유롭게 다룰 수 있습니다.

**BGM이 나레이션을 덮는 문제** — `sidechaincompress` 로 덕킹을 겁니다. 말할 때만 BGM이
자동으로 작아집니다 (`4_edit.py` 의 `mix_audio`).

**세로 영상에 가로 소재 넣기** — 오버스캔 크롭으로 9:16을 채우면서, 소재 하단에 박힌
워터마크나 자막을 화면 밖으로 밀어냅니다.

**TTS 문장별 볼륨 편차** — 문장마다 `-16 LUFS` 로 평준화한 뒤 이어붙입니다.

**자막 싱크** — TTS 생성 시 문장별 길이를 재서 `timing.json` 으로 떨어뜨리고, 자막과 컷 전환이
모두 이걸 참조합니다. 별도 싱크 작업이 없습니다.

---

## 5. 자주 막히는 곳

| 증상 | 원인 / 해결 |
|---|---|
| `TYPECAST_API_KEY 가 없습니다` | `cp .env.example .env` 후 키 입력 |
| `ffmpeg: command not found` | ffmpeg 미설치 → 1-1 참고 |
| 자막이 네모(□)로 나옴 | 폰트 미설치 → `assets/fonts/` 확인 |
| `소스 없음: .../sources/1.mp4` | 소재 3개를 먼저 받아야 합니다 |
| `3소스 짬뽕 규격 위반` | 한 원본을 쪼갠 경우. 서로 다른 영상 3개를 쓰세요 |
| 영상이 너무 짧음 | 화자마다 발화 속도가 달라서 그렇습니다. 대본 문장을 늘리세요 |
| 업로드가 중단됨 | `.env` 의 `YT_CHANNEL_ID` 와 인증된 채널이 다릅니다 |
| tikwm 이 빈 결과 | 무료 API라 가끔 불안정합니다. 잠시 후 재시도 |

---

## 6. 알아두실 것

- **TTS는 유료입니다.** Typecast 크레딧이 듭니다. 다른 TTS를 쓰려면 `5_tts.py` 의
  `tts()` 함수만 갈아끼우면 됩니다.
- **소재 저작권** — 틱톡 영상을 편집 소재로 쓰는 것에 대한 판단과 책임은 사용자에게 있습니다.
  각 플랫폼의 약관과 저작권법을 확인하고 쓰세요.
- **tikwm / 네이버 데이터랩**은 비공식 경로입니다. 언제든 막힐 수 있습니다.
- `prd.md` 는 개발하면서 쌓은 작업 노트라 날짜·시행착오 기록이 섞여 있습니다.
  규격의 이유가 궁금할 때 보시면 됩니다.

## 라이선스

MIT — 자유롭게 쓰시고, 고쳐서 쓰신 것도 환영합니다.
단, 폰트·BGM·소재 영상의 라이선스는 각각 따로 확인하셔야 합니다.
