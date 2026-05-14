카드뉴스 전용 자동화 배포 가이드

최종 정책:
- 릴스 자동화 중단
- Telegram 저장 채널 위주 (단일 카드 1장 + 캡션, 또는 텍스트 브리핑 폴백)
- 인스타 자동업로드 없음
- OpenAI 이미지 생성 없음
- 템플릿 고정 + 데이터만 변경

0) 워커 동작
- `python main_instagram.py`는 `CHECK_INTERVAL`(초)마다 `main()`을 반복 실행합니다.
- 정규 전송은 KST 08:10·19:10 시작 이후 `REGULAR_POST_MINUTE_WINDOW`(기본 120분) 안에만 시도되며, 그 밖에는 고득점 뉴스가 있을 때만 오프슬롯 전송이 가능합니다(`OFF_SCHEDULE_*`).
- 루트 `nixpacks.toml`로 Railway(Nixpacks) 빌드 시 `fonts-noto-cjk`를 깔면 Linux에서 한글 카드 폰트가 안정적입니다.
- 상세 변수 설명은 `.env.example` 참고.

1) Railway Variables (필수 — 단일 카드·브리핑 경로)
- NEWS_API_KEY (NewsAPI.org — 뉴스 수집·단일 카드 후보)
- CHECK_INTERVAL=1800 (30분마다 슬롯 재검사; 더 촘촘히 하려면 예: 600)
- TEXT_BRIEFING_ONLY=true
- TELEGRAM_SINGLE_CARD=true (false면 텍스트 브리핑만)
- ENABLE_TELEGRAM_STORAGE=true
- TELEGRAM_BOT_TOKEN
- TELEGRAM_STORAGE_CHAT_ID
- CONTENT_MODE=auto (권장: 아침 슬롯→브리핑 톤, 저녁 슬롯→저장형 톤; 엔진 키로 자동 매핑) 또는 briefing / market_fact
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
- 레거시 5장 모드(CARD_NEWS_MODE=true 등): `output_cardnews/` 또는 `output_marketfact/` 등 기존 경로

4) 전송 정책
- 저장 채널(`TELEGRAM_STORAGE_CHAT_ID`) 전송만 사용 (`send_storage_*`)
- 정보방용 `TELEGRAM_CHAT_ID` 경로는 현재 파이프라인에서 쓰지 않음
- 릴스/인스타 자동 업로드 금지

5) 디자인 레퍼런스 PNG
- `assets/card_references/README.txt` — `CARD_TEMPLATE`(photo/badge/quote)별 참고 이미지 위치 안내 (런타임 미사용)

6) 운영 스케줄 제안
- 워커가 `CHECK_INTERVAL`마다 돌아야 KST 08:10·19:10 슬롯을 안정적으로 잡을 수 있음.
- `CONTENT_MODE=auto`이면 아침 슬롯은 `us_preopen` 톤, 저녁 슬롯은 `sector_focus` 톤으로 텍스트 브리핑이 생성됨(코드: `effective_briefing_summary_mode()`).
- 아침/저녁을 서비스 두 개로 나누려면 각각 다른 `CONTENT_MODE`를 두면 됨.
