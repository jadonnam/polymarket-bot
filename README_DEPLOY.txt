자돈남 최종 배포 체크리스트

1) 네가 직접 넣어야 하는 파일
- 없음 (인스타 세션 파일 미사용)

2) Railway Variables에 넣어야 하는 값
- NEWS_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_STORAGE_CHAT_ID
- ENABLE_TELEGRAM_STORAGE=true
- CARD_NEWS_MODE=true
- USE_REEL_STORY_V2=false
- FORCE_REGULAR_NOW=false
- CHECK_INTERVAL=1800
- DRY_RUN_PIPELINE=false
- SKIP_BREAKING_CHECK=true
- USE_CACHED_NEWS=true
- ENABLE_OPENAI_IMAGE=false

3) 배포 전 확인
- fonts/Pretendard-Bold.ttf 존재
- fonts/Pretendard-Regular.ttf 존재
- Procfile이 worker: python main_instagram.py 인지 확인

4) 테스트 순서
- Railway Variables에서 FORCE_REGULAR_NOW=true 로 1회 테스트
- 실행 로그에서 카드뉴스 5장 + 무음 릴스 생성 확인
- 생성 파일 확인:
  - output_cardnews/card_01.jpg
  - output_cardnews/card_02.jpg
  - output_cardnews/card_03.jpg
  - output_cardnews/card_04.jpg
  - output_cardnews/card_05.jpg
  - output_cardnews/reel_output.mp4
  - output_cardnews/caption.txt
- 텔레그램 저장 채널 전송 확인:
  - 카드 5장 media group
  - 릴스 mp4
  - caption 텍스트 메시지
- 테스트 후 FORCE_REGULAR_NOW=false 로 원복

5) Git 명령어
이미 git 연결 안 되어 있으면:
git init
git add .
git commit -m "final deploy setup"
git branch -M main
git remote add origin <깃허브 레포 주소>
git push -u origin main

이미 git 연결되어 있으면:
git add .
git commit -m "final deploy update"
git push origin main

6) 현재 코드 동작 요약
- 30분마다 실행 권장
- 속보: 기본 비활성화(SKIP_BREAKING_CHECK=true)
- 정규시간(08:10, 19:10 KST):
  - CARD_NEWS_MODE=true: 카드뉴스 5장 + 무음 릴스(카드 영상화) 생성
  - CARD_NEWS_MODE=false: 기존 저비용 TOP5 구조 유지
- 전송 대상: 비공개 Telegram 저장 채널 전용(정보방/인스타 자동업로드 비활성화)
