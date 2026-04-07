import os
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

TOPIC_RULES = """
주제 고정 규칙:
- 원문 주제를 절대 바꾸지 말 것
- 전쟁/공격/미사일/이란/미군 개입/휴전 뉴스면 지정학/전쟁 리스크로만 써라
- 유가 뉴스면 유가/기름값으로만 써라
- 금 뉴스면 금값/안전자산으로만 써라
- 환율 뉴스면 환율/물가/수입비용으로만 써라
- 비트코인 뉴스면 비트코인/코인시장으로만 써라
- 원문에 없는 "정부 발표", "유류세 인상", "전기요금 인상", "부동산" 같은 내용 절대 추가 금지
- 사실을 지어내지 말 것
"""

BAD_WORDS = ["상황", "흐름", "영향", "변화", "확대", "심화", "통제", "가능성", "발생"]
GOOD_WORDS = ["급등", "급락", "공격", "공습", "개입", "휴전", "충돌", "전쟁", "붕괴", "폭등", "쏠린다", "몰렸다", "흔들린다", "튀었다", "뛴다"]

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
    if not has_good_words(result["title1"]) and "%" not in result["title1"] and "원" not in result["title1"]:
        return False
    return True

def rewrite(title, desc, mode="normal", number_hint=None, retry=0):
    if mode == "alert":
        extra = f"""
추가 조건:
- 속보 카드 스타일
- 제목1은 강하게
- 제목2는 지금 당장 체감되는 영향
- 가능하면 "급등", "폭등", "긴장", "충돌", "전쟁", "개입", "붕괴" 같은 단어 우선
- 제목1은 이미 일어난 것처럼 표현
- 제목2는 반드시 지금 당장 체감되는 결과처럼 써라
- 숫자가 있으면 최대한 제목1 또는 제목2에 자연스럽게 넣어라
- 사용할 수 있는 숫자 힌트: {number_hint if number_hint else "없음"}
"""
    else:
        extra = f"""
추가 조건:
- 제목1은 이미 일어난 것처럼 표현
- 제목2는 지금 체감 표현
- 숫자가 있으면 최대한 제목1 또는 제목2에 자연스럽게 넣어라
- 사용할 수 있는 숫자 힌트: {number_hint if number_hint else "없음"}
"""

    prompt = f"""
너는 한국 인스타 경제 카드뉴스 카피라이터다.

목표:
원문 주제를 유지한 채, 한국 사람이 바로 이해할 수 있는 짧고 강한 카드 문구를 만든다.

{TOPIC_RULES}

조건:
- 무조건 한국어
- 매우 짧게
- 제목1: 8~12자
- 제목2: 8~12자
- 설명1/2: 10~18자
- 번역투 금지
- 사람 이름 나열 금지
- 뉴스 제목 그대로 번역 금지
- 설명형 금지
- 추상 표현보다 행동/상태 표현 우선
- 제목1은 사건 자체
- 제목2는 내 돈/시장 반응
- 제목2는 가능하면 숫자 + 행동 구조를 우선
- 추상적인 단어 절대 사용 금지: 상황, 흐름, 영향, 변화, 확대, 심화, 통제, 가능성, 발생
- 반드시 눈에 보이는 사건/행동으로 표현할 것
- 제목1은 사건 자체 (폭발, 충돌, 개입, 붕괴, 급등 등)
- 제목2는 내 돈에 바로 체감되는 결과
- 허용 행동 단어:
  폭등, 급등, 급락, 붕괴, 충돌, 전쟁, 공격, 개입, 긴장, 폭발, 흔들림, 몰림, 쏠림, 휴전, 뛴다
{extra}

좋은 예시:
제목1: 유가 +18% 급등
제목2: 지금 기름값 뛴다
설명1: 중동 긴장 커지면
설명2: 에너지부터 반응

제목1: 미군 개입 86%
제목2: 지금 돈 쏠린다
설명1: 전쟁 불안 커지면
설명2: 투자 심리 먼저 꺾인다

제목1: 환율 1,535원
제목2: 지금 물가 뛴다
설명1: 달러 강세 이어지면
설명2: 수입 부담 더 커진다

제목1: 금값 계속 오른다
제목2: 지금 돈 몰린다
설명1: 불안 심리 커지면
설명2: 안전자산 먼저 간다

영어 뉴스:
제목: {title}
내용: {desc}

출력 형식:
제목1: ...
제목2: ...
설명1: ...
설명2: ...
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    text = res.choices[0].message.content.strip().split("\n")

    result = {
        "title1": "시장 크게 흔들린다",
        "title2": "지금 돈 몰린다",
        "desc1": "불안 심리 커지면",
        "desc2": "자산 가격 먼저 튄다"
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

    if retry < 2 and not is_valid_result(result):
        return rewrite(title, desc, mode=mode, number_hint=number_hint, retry=retry + 1)

    return result