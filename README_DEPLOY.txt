카드뉴스 전용 자동화 배포 가이드

최종 정책:
- 릴스 자동화 중단
- 카드뉴스 자동 생성만 운영
- Telegram 저장 채널로 카드 5장 + 캡션만 전송
- 인스타 자동업로드 없음
- OpenAI 이미지 생성 없음
- 템플릿 고정 + 데이터만 변경

1) Railway Variables (필수)
- CHECK_INTERVAL=1800
- CARD_NEWS_MODE=true
- CONTENT_MODE=market_fact
- ENABLE_TELEGRAM_STORAGE=true
- TELEGRAM_BOT_TOKEN
- TELEGRAM_STORAGE_CHAT_ID
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
- briefing 모드: `output_cardnews/card_01.jpg` ~ `card_05.jpg`, `caption.txt`
- market_fact 모드: `output_marketfact/card_01.jpg` ~ `card_05.jpg`, `caption.txt`

4) 전송 정책
- 저장 채널 전송만 허용
  - 카드 5장 media group
  - caption 텍스트 메시지
- 정보방 전송 금지
- 릴스/인스타 자동 업로드 금지

5) 운영 스케줄 제안
- 08:10 KST: `CONTENT_MODE=briefing` (간단 시장 브리핑)
- 19:10 KST: `CONTENT_MODE=market_fact` (저장형 정보 콘텐츠)
