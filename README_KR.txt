[jadonnam 최종 한글팩]

덮어쓸 파일
- main_master_v3.py
- rank_card_v3.py
- assets/icon_news.png
- assets/icon_poly.png
- assets/icon_market.png

핵심 수정
- 2~4페이지 상단 라벨 완전 한글화
  - 뉴스
  - 폴리마켓
  - 시장 반응
- 워터마크 제거
- 빈 순위(- / 0%) 숨김
- 항목 수가 적어도 카드가 비어 보이지 않도록 자동 간격 조정
- 폰트/퍼센트/게이지 크기 키움
- 영어 잘림 최소화, 한국어 라벨 우선
- 정규 시간에는 2~4페이지만 텔레그램 전송
- 속보 자동 업로드 구조는 유지

적용 순서
1) project 폴더에 압축 해제 후 덮어쓰기
2) git add .
3) git commit -m "improve korean rank cards"
4) git push
