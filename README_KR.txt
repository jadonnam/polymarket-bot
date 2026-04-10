[jadonnam 최종 팩]

구성
- main_master_v3.py        : 전체 흐름 제어
- rank_card_v3.py         : 2~4페이지 자동 생성
- card_v3.py              : 속보 전용 카드 생성
- prompt_bank_v3.py       : 속보 이미지 주제/프롬프트 보조
- telegram_new.py         : 텔레그램 전송
- assets/                 : 상단 아이콘

최종 구조
- 속보: 자동 업로드 유지
- 정규 08시 / 19시: 2~4페이지 카드만 텔레그램 자동 전송
- 1페이지는 수동 제작
- 2페이지: 뉴스 TOP 5
- 3페이지: 폴리마켓 TOP 5
- 4페이지: 시장 반응 요약 TOP 5

중요
- 2~4페이지는 AI 이미지 비용 없음
- 속보 이미지는 image_generator_new.py 의 safe_generate_bg 사용
- 인스타 자동 업로드는 속보만 유지
- 텔레그램 채널에는 정규 시간마다 2~4페이지만 전송

필요 환경변수
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- INSTAGRAM_USERNAME
- INSTAGRAM_PASSWORD
- INSTAGRAM_SESSION_PATH (선택)
- USE_INSTAGRAM_FOR_BREAKING=true/false (선택)

적용 방법
1) project 폴더에 압축 해제 후 덮어쓰기
2) git add .
3) git commit -m "apply jadonnam final pack"
4) git push
