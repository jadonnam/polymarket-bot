from openai import OpenAI
from datetime import datetime, timezone

client = OpenAI()

def format_volume_krw(volume_usd):
    try:
        volume_usd = float(volume_usd)
        krw = volume_usd * 1350
        if krw >= 100000000:
            return f"{krw/100000000:.0f}억"
        elif krw >= 10000:
            return f"{krw/10000:.0f}만"
        return f"{int(krw)}원"
    except:
        return None

def format_percent(price):
    try:
        p = float(price) * 100
        if p >= 99.5:
            return "99.6%"
        if p >= 10:
            return f"{p:.0f}%"
        return f"{p:.1f}%"
    except:
        return None

def format_deadline(end_date):
    if not end_date:
        return None

    try:
        dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = dt - now
        days = delta.days

        if days >= 0:
            return f"D-{days}"
        return "마감 지남"
    except:
        return None

def rewrite_poly(question, volume, yes_price, end_date=None):
    percent = format_percent(yes_price)
    volume_krw = format_volume_krw(volume)
    dday = format_deadline(end_date)

    prompt = f"""
너는 한국 인스타 경제/폴리마켓 카드뉴스 카피라이터다.

아래 Polymarket 시장 정보를 보고
짧고 강한 카드뉴스 문구를 만들어라.

조건:
- 무조건 한국어
- 카드용이라 짧게
- 제목1: 8~12자
- 제목2: 10~14자
- 설명1/2: 12~18자
- 질문을 그대로 번역하지 말 것
- "지금 돈이 어디 몰리는지" 느낌으로 쓸 것
- 숫자가 있으면 적극 활용할 것
- 확률이 있으면 제목1에 우선 사용
- 거래량이 있으면 제목2 또는 설명에 자연스럽게 반영
- 날짜가 있으면 설명에 D-day 느낌으로 활용 가능
- 너무 딱딱한 뉴스체 금지
- 사람 이름 나열 금지
- 저장/공유되고 싶은 문장으로 만들기
- "주목하자", "가능성", "전망" 같은 약한 표현 금지
- 100%로 단정하지 말 것. 거의 확실해도 99.6% 같이 쓰기

시장 질문:
{question}

참고 숫자:
확률: {percent}
거래량(원화 환산): {volume_krw}
D-day: {dday}

좋은 예시:
제목1: 미군 개입 99.6%
제목2: 509억 몰렸다
설명1: D-23 긴장감 커지고
설명2: 돈도 같이 움직인다

제목1: 이란 변수 급등
제목2: 지금 돈 몰린다
설명1: 중동 긴장 커질수록
설명2: 시장 먼저 흔들린다

제목1: 트럼프 변수 72%
제목2: 지금 베팅 커진다
설명1: 확률 오를수록
설명2: 자금도 빨리 붙는다

출력 형식:
제목1: ...
제목2: ...
설명1: ...
설명2: ...
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )

    text = res.choices[0].message.content.strip().split("\n")

    result = {
        "title1": "확률 다시 뛴다",
        "title2": "지금 돈 몰린다",
        "desc1": "시장 긴장 커질수록",
        "desc2": "베팅 자금도 반응한다"
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

    return result