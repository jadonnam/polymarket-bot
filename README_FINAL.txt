이 압축파일은 프로젝트 루트에 그대로 덮어쓰기하면 됩니다.

포함 파일
- requirements.txt
- content_dispatcher.py
- polymarket.py
- card_v3.py
- rank_card_v3.py
- reels_packager.py
- reels_maker_final.py
- news.py
- main_master_v3.py
- trigger_regular_now.py

구조
- 10분마다 main_master_v3.py 실행
- 속보: 보수 필터 + 중복 방지
- 정규 업로드: 한국시간 08:00 / 19:00
- 카드 3장 + 릴스 mp4 + 텔레그램 텍스트 패키지 전송

Railway Start Command
python main_master_v3.py

즉시 테스트
python trigger_regular_now.py

필수 환경변수
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- NEWS_API_KEY

선택 환경변수
- USE_INSTAGRAM_FOR_BREAKING=true / false
- DRY_RUN=true / false
