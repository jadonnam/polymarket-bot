자돈남 최종 배포 체크리스트

1) 네가 직접 넣어야 하는 파일
- instagram_session.json  -> 프로젝트 루트에 넣기

2) Railway Variables에 넣어야 하는 값
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- INSTAGRAM_USERNAME
- INSTAGRAM_PASSWORD
- INSTAGRAM_SESSION_PATH=instagram_session.json
- NEWS_API_KEY
- USE_INSTAGRAM_FOR_BREAKING=false
- FORCE_REGULAR_NOW=false
- CHECK_INTERVAL=1800

3) 배포 전 확인
- fonts/Pretendard-Bold.ttf 존재
- fonts/Pretendard-Regular.ttf 존재
- requirements.txt에 instagrapi 존재
- Procfile이 worker: python main_master_v3.py 인지 확인

4) 테스트 순서
- Railway Variables에서 FORCE_REGULAR_NOW=true 로 1회 테스트
- 실행 로그에서 텔레그램 카드 3장 + 릴스 생성 확인
- 인스타 릴스 업로드 확인
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
- 속보: 텔레그램 자동 전송
- 정규시간(08:00, 19:00 KST): 랭크 카드 + 릴스 자동 생성
- 정규 릴스: 인스타 자동 업로드
- 속보 인스타 자동 업로드: USE_INSTAGRAM_FOR_BREAKING=true 일 때만 동작
