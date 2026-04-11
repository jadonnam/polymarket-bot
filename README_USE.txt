이 ZIP 안 파일을 project 폴더에 덮어쓰기하면 됩니다.

포함 파일
- requirements.txt
- content_dispatcher.py
- rank_card_v3.py
- news.py
- reels_packager.py
- reels_maker_final.py
- main_master_v3.py
- trigger_regular_now.py

동작
1. 10분마다 main_master_v3.py 실행
2. 뉴스 속보는 1시간에 1번만 검사
3. 폴리마켓 속보는 10분마다 검사
4. 오전 8시 / 오후 7시에는
   - 카드 3장 생성
   - 릴스 mp4 생성
   - 카드 3장 + 릴스 mp4 + 텍스트 패키지 텔레그램 전송

Railway Start Command
python main_master_v3.py

지금 바로 테스트 전송
python trigger_regular_now.py
