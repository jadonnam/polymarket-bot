적용 방법

1. 이 zip 파일을 풀어서 기존 프로젝트에 덮어쓰기
2. 아래 명령어 실행

git add .
git commit -m "visual polish and korean label fix"
git push origin main

3. Railway 재배포
4. FORCE_REGULAR_NOW=true 로 1회 테스트 후 다시 false

이번 수정 내용
- 인트로/아웃트로 배경 밝기 보정
- 텍스트 뒤 어두운 박스 제거
- build_reel(top_labels=...) 시그니처 지원
- 카드 오른쪽 중요도/증감/% 정렬 고정
- 0%도 항상 표시
- 뉴스/폴리 영어 라벨 한국어 치환 강화
