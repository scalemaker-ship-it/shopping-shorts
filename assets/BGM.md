# BGM 넣기

음원 저작권 때문에 BGM 파일은 레포에 포함하지 않았습니다.

**레포 루트에 `bgm/` 폴더를 만들고 mp3 파일을 넣으면** `pipeline/4_edit.py` 가
자동으로 찾아서 나레이션에 사이드체인 덕킹으로 믹스합니다. (파일이 없으면 나레이션만 나갑니다.)

```
shorts/
└── bgm/
    └── 아무거나.mp3
```

무료 음원 소스:
- [YouTube 오디오 보관함](https://studio.youtube.com) — Studio → 오디오 보관함 (수익 창출 가능 트랙 필터)
- [Pixabay Music](https://pixabay.com/music/)
- [Free Music Archive](https://freemusicarchive.org/)

볼륨은 `4_edit.py` 의 `mix_audio(bgm_vol=0.28)` 로 조절합니다.
