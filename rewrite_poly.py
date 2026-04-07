import os
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

BAD_WORDS = ["상황", "흐름", "영향", "변화", "확대", "심화", "통제", "가능성", "발생"]
GOOD_WORDS = ["급등", "급락", "공격", "공습", "개입", "휴전", "충돌", "전쟁", "붕괴", "폭등", "쏠린다", "몰렸다", "흔들린다", "튀었다", "뛴다", "돌파"]

REPLACE_RULES = {
    "정상화": "회복",
    "회복": "반등",
    "상승": "뛴다",
    "하락": "떨어진다",
}

def force_action_words(text):
    for k, v in REPLACE_RULES.items():
        text = text.replace(k, v)
    return text

def has_bad_words(text):
    return any(word in text for word in BAD_WORDS)

def has_good_words(text):
    return any(word in text for word in GOOD_WORDS)

def is_valid_result(result):
    if has_bad_words(result["title1"]) or has_bad_words(result["title2"]):
        return False
    if "100% 발생" in result["title1"] or "100% 발생" in result["title2"]:
        return False
    if "리스크 커진다" in result["title2"]:
        return False
    return True

def rewrite_poly(question, volume, yes_price, end_date, retry=0):
    prompt = f"""
너는 한국 인스타 경제 카드뉴스 카피라이터다.

목표:
폴리마켓 질문을 한국인이 바로 이해하는 강한 카드 문구로 바꿔라.

규칙:
- 무조건 한국어
- 매우 짧게
- 제목1: 사건/확률/숫자 중심
- 제목2: 돈/시장 반응 중심
- 설명1/2: 10~18자
- 추상 표현 금지
- 설명형 금지
- 번역투 금지
- 사람 이름 나열 금지
- 제목 그대로 번역 금지
- "상황, 흐름, 영향, 변화, 확대, 심화, 통제, 가능성, 발생" 금지
- "리스크 커진다" 같은 약한 문장 금지
- 숫자가 있으면 살려라
- 행동 단어를 우선 써라
- "$70,000" 같은 달러 표기는 자연스럽게 "7만 달러"로 바꿔도 됨
- "$200" 같은 달러 표기는 "200달러"처럼 붙여 써라

허용 행동 단어:
급등, 급락, 공격, 공습, 개입, 휴전, 충돌, 전쟁, 붕괴, 폭등, 쏠린다, 몰렸다, 흔들린다, 튄다, 돌파

좋은 예시:
제목1: 이란 휴전 34%
제목2: 14억 원 몰렸다
설명1: 불확실성 확산 중
설명2: 돈이 움직이는 시점

제목1: WTI 200달러 4%
제목2: 10억 원 몰렸다
설명1: D-22 초미의 관심
설명2: 유가 급등 예고

제목1: 비트코인 7만 돌파
제목2: 지금 돈 몰려든다
설명1: 협상 기대감 붙으면
설명2: 코인부터 먼저 뛴다

제목1: 이란 공격 100%
제목2: 지금 돈 먼저 튄다
설명1: 긴장감 높아지면
설명2: 투자 심리 흔들린다

나쁜 예시:
제목1: 이란 공격 100% 발생
제목2: 지금 전쟁 리스크 커진다

제목1: WTI 200달러 4.3%
제목2: 시장이 흔들린다

입력:
질문: {question}
거래량: {volume}
yes 확률: {yes_price}
종료일: {end_date}

출력 형식:
제목1: ...
제목2: ...
설명1: ...
설명2: ...

중요:
- 출력은 4줄만
- 제목1은 사건 자체
- 제목2는 돈/시장 반응
- "발생" 금지
- "리스크 커진다" 금지
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    text = res.choices[0].message.content.strip().split("\n")

    result = {
        "title1": "시장 34% 흔들림",
        "title2": "14억 원 몰렸다",
        "desc1": "불확실성 확산 중",
        "desc2": "돈이 움직이는 시점"
    }

    for line in text:
        line = line.strip()
        if line.startswith("제목1:"):
            result["title1"] = line.replace("제목1:", "").strip()
        elif line.startswith("제목2:"):
            result["title2"] = line.replace("제목2:", "").strip()
        elif line.startswith("설명1:"):
            result["desc1"] = line.replace("설명1:", "").strip()
        elif line.startswith("설명2:"):
            result["desc2"] = line.replace("설명2:", "").strip()

    result["title1"] = force_action_words(result["title1"])
    result["title2"] = force_action_words(result["title2"])
    result["desc1"] = force_action_words(result["desc1"])
    result["desc2"] = force_action_words(result["desc2"])

    if retry < 2 and not is_valid_result(result):
        return rewrite_poly(question, volume, yes_price, end_date, retry=retry + 1)

    return result
