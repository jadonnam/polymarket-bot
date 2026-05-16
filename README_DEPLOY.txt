카드뉴스 전용 자동화 배포 가이드

최종 정책:
- **단일 카드 1장** — BoA 레퍼런스(`ref_photo_bank.png` 레이아웃) photo 고정, 캐러셀·릴스 없음
- Telegram 저장 채널 (JPEG 1장 + 짧은 캡션) 또는 텍스트 브리핑 폴백
- 인스타 자동업로드 없음 (연동 시 upload_instagram 별도)
- 카드 배경: urlToImage 미사용, ref + assets/fallbacks
- 한글 제목·부제: OPENAI_API_KEY + CARD_HEADLINE_OPENAI=auto 권장

0) 워커 동작
- `python main_instagram.py`는 `CHECK_INTERVAL`(초)마다 `main()`을 반복 실행합니다.
- 기본(`SIGNAL_DRIVEN_SEND=true`): **KST 아침/저녁 슬롯 없이**, 뉴스 후보 점수·전송 쿨다운·URL 중복만 보고 전송 여부를 정합니다.
- `SIGNAL_DRIVEN_SEND=false`이면 예전처럼 정규 슬롯(`REGULAR_POST_MINUTE_WINDOW`) + 오프슬롯 이슈 조합을 사용합니다.
- 정규 전송만 쓸 때: KST 08:10·19:10 시작 이후 `REGULAR_POST_MINUTE_WINDOW`(기본 120분) 안에서만 시도(`OFF_SCHEDULE_*`와 병행).
- 루트 `nixpacks.toml`로 Railway(Nixpacks) 빌드 시 `fonts-noto-cjk`를 깔면 Linux에서 한글 카드 폰트가 안정적입니다.
- 상세 변수 설명은 `.env.example` 참고.

1) Railway Variables (필수 — 단일 카드·브리핑 경로)
- NEWS_API_KEY (NewsAPI.org — 뉴스 수집·단일 카드 후보)
- CHECK_INTERVAL=1800 (주기마다 뉴스·신호 재평가; 더 자주내려면 예: 600)
- TEXT_BRIEFING_ONLY=true
- TELEGRAM_SINGLE_CARD=true (false면 텍스트 브리핑만)
- ENABLE_TELEGRAM_STORAGE=true
- TELEGRAM_BOT_TOKEN
- TELEGRAM_STORAGE_CHAT_ID
- SIGNAL_DRIVEN_SEND=true (기본, 슬롯 무시·이슈 위주)
- OFF_SCHEDULE_MIN_SCORE / OFF_SCHEDULE_COOLDOWN_MINUTES (전송 민감도·쿨다운)
- CONTENT_MODE=auto 또는 briefing / market_fact / 엔진 키(korea_close 등); 신호 모드에서는 슬롯 없이 브리핑 톤만 매핑
- CARD_NEWS_MODE=false (true면 레거시 5장 카드 경로 쪽 리소스·분기가 켜짐; 단일 카드만 쓸 때는 false 권장)
- FORCE_REGULAR_NOW=false
- SKIP_BREAKING_CHECK=true

2) Deprecated / 미사용 변수 (현재 정책에서 사용 안 함)
- STATIC_REEL_MODE
- STATIC_REEL_FORMAT
- ENABLE_INSTAGRAM_UPLOAD
- ENABLE_OPENAI_IMAGE
- ENABLE_OPENAI_STATIC_IMAGE
- FORCE_REGENERATE_STATIC_BG
- OPENAI_API_KEY
- USE_REEL_STORY_V2
- USE_CACHED_NEWS
- SKIP_POLYMARKET

3) 생성물
- 단일 카드(Telegram): `output_telegram_card/` 아래 JPEG 1장 + 캡션(코드에서 조합)
- `CARD_TEMPLATE=photo`: 배경은 `TELEGRAM_CARD_USE_NEWS_IMAGE`·urlToImage 또는 **`assets/fallbacks/*.jpg`**(키워드 매칭) → BoA/삼성형(전면 사진 + 하단 그라데이션 + 좌측 헤드라인)
- 레거시 5장 모드(CARD_NEWS_MODE=true 등): `output_cardnews/` 또는 `output_marketfact/` 등 기존 경로

4) 전송 정책
- 저장 채널(`TELEGRAM_STORAGE_CHAT_ID`) 전송만 사용 (`send_storage_*`)
- 정보방용 `TELEGRAM_CHAT_ID` 경로는 현재 파이프라인에서 쓰지 않음
- 릴스/인스타 자동 업로드 금지

5) 디자인 레퍼런스 PNG
- `assets/card_references/README.txt` — `CARD_TEMPLATE`(photo/badge/quote)별 참고 이미지 위치 안내 (런타임 미사용)

6) 운영 스케줄 제안
- 기본은 신호 전송: `CHECK_INTERVAL`마다 점수·쿨다운·중복만 검사해 바로 전송 후보를 판단합니다.
- `SIGNAL_DRIVEN_SEND=false`로 두고 `REGULAR_POST_MINUTE_WINDOW`를 쓰면 KST 08:10·19:10 근처 슬롯 전송으로 되돌릴 수 있습니다.
- 텍스트 브리핑 톤은 `CONTENT_MODE`·`effective_briefing_summary_mode()` 조합으로 결정됩니다.
