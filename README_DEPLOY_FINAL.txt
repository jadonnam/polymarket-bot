최종 배포 체크리스트

1) 덮어쓰기 파일
- rank_card_v3.py
- main_master_v3.py

2) 폰트 위치 확인
- fonts/Pretendard-Bold.ttf
- fonts/Pretendard-Regular.ttf

3) 로컬 테스트
- python rank_card_v3.py
- output_rank 폴더에 3장 생성 확인
- python main_master_v3.py

4) Render / 서버 실행 명령
- python main_master_v3.py

5) 기존 캐시/출력 정리 권장
- output_rank/*.jpg 삭제
- __pycache__ 삭제

6) git 배포
- git add .
- git commit -m "final finance ranking card deploy"
- git push

7) 핵심 구조
- 속보: 기존처럼 즉시 업로드
- 정규 업로드: 오전 8시 / 오후 7시
- 정규 카드: 뉴스 / 폴리마켓 / 시장 반응 3장
