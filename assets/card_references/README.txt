카드 뉴스 레퍼런스 (디자인 기준)
==============================

이 폴더에는 “이렇게 생겨야 한다”는 **참고 PNG**를 넣어 두면 됩니다.
런타임에 이미지를 읽어 쓰지는 않으며, 기획/디자인/코드 레이아웃 맞출 때만 씁니다.

대응 레이아웃 (환경변수 CARD_TEMPLATE)
----------------------------------------
- photo  … 뱅크오브아메리카 / 삼성형 — `ref_photo_bank.png`·키워드 폴백 + **하단 BoA 그라데이션** + **흰색 2줄(외곽선 없음)**. urlToImage 미사용.
  - `ref_photo_bank.png` … 이 폴더에 두면 금융·반도체·소재 키워드 시 배경으로 사용
  - 워터마크: `assets/branding/watermark.png` 또는 `CARD_WATERMARK_PATH`
- badge  … IREN형 — 데이터센터 느낌 배경 + 중앙 그린 배지(티커) + 하단 스택 카피
- quote  … HipHub형 — 상단 브랜드 + 인용 흰 박스 + 하단 대형 헤드라인

Railway
-------
CARD_TEMPLATE=photo | badge | quote

참고 파일 예시 이름 (직접 넣기)
------------------------------
- ref_photo_bank.png
- ref_photo_samsung.png
- ref_badge_iren.png
- ref_quote_hiphub.png
