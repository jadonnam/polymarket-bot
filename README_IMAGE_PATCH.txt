핵심 변경
- reels_maker_final.py 인트로 이미지 생성 경로 강화
- 주제별 프롬프트 3개씩 재시도
- 생성 실패 시 검은 화면 대신 주제형 뉴스매거진 배경 생성
- assets/audio/bg.mp3 가 있으면 우선 사용
- 없으면 기존 합성 배경음 사용

권장
- Suno 파일을 assets/audio/bg.mp3 로 넣기
- FORCE_REGULAR_NOW=true 로 1회 테스트
