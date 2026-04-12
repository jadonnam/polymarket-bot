"""
threads_auto.py — 스레드 자동 포스팅 시스템

자영업 (@omniflow_kr): 하루 7개 공감글
자돈남 (@jadonnam_money): TOP5 3개 + 경제 단신 4개 (뉴스 2개 + 개념/정보 2개)

Railway 환경변수:
- OPENAI_API_KEY
- JADONNAM_THREADS_USERNAME
- JADONNAM_THREADS_PASSWORD
- OMNIFLOW_THREADS_USERNAME
- OMNIFLOW_THREADS_PASSWORD
"""

from __future__ import annotations
import os
import random
from openai import OpenAI

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
JADONNAM_USERNAME = (os.getenv("JADONNAM_THREADS_USERNAME") or "").strip()
JADONNAM_PASSWORD = (os.getenv("JADONNAM_THREADS_PASSWORD") or "").strip()
OMNIFLOW_USERNAME = (os.getenv("OMNIFLOW_THREADS_USERNAME") or "").strip()
OMNIFLOW_PASSWORD = (os.getenv("OMNIFLOW_THREADS_PASSWORD") or "").strip()

client = OpenAI(api_key=OPENAI_API_KEY)


def post_to_threads(username: str, password: str, text: str) -> bool:
    try:
        from threadspy import ThreadsAPI
        api = ThreadsAPI(username=username, password=password)
        api.publish(caption=text)
        print(f"[Threads] 업로드 성공: {username}")
        return True
    except Exception as e:
        print(f"[Threads] 업로드 실패: {repr(e)}")
        return False


# ── 자영업 ───────────────────────────────────────────────────

OMNIFLOW_TOPICS = [
    "배달앱 수수료가 올라갈수록 사장님 몫이 줄어드는 구조",
    "알바를 구하기 힘든 현실",
    "단골손님이 줄어드는 이유",
    "임대료 인상 압박",
    "매출은 있는데 남는 게 없는 구조",
    "폐업하는 가게들의 공통점",
    "사장님 혼자 다 해야 하는 현실",
    "원가는 오르는데 가격은 못 올리는 딜레마",
    "SNS 마케팅 해봤는데 효과없는 현실",
    "직원 관리가 더 힘든 이유",
    "손님이 줄었는데 고정비는 그대로인 상황",
    "주말에도 쉬지 못하는 자영업자",
    "박리다매가 더 이상 안 되는 이유",
    "카드 수수료 구조의 현실",
    "경기 탓인지 내 탓인지 모르겠는 상황",
    "가게 하나 차리는 데 드는 진짜 비용",
    "매출 1000만원인데 실수령이 200인 이유",
    "자영업 폐업률이 높은 진짜 이유",
    "배달 전문점이 늘어나는 이유",
    "프랜차이즈가 유리한 이유와 함정",
    "단골 한 명이 신규 열 명보다 나은 이유",
    "가격 올리면 손님 빠질까봐 못 올리는 상황",
    "점심 장사만 되고 저녁은 텅 빈 이유",
    "배달 수수료 빼면 남는 게 없는 구조",
    "사장님이 아프면 가게가 멈추는 현실",
    "직원 한 명 뽑으면 인건비가 얼마인지",
    "재료비 아끼다가 맛이 변하는 악순환",
    "리뷰 하나에 매출이 달라지는 시대",
    "자영업자가 느끼는 외로움",
    "열심히 하는데 왜 안 되는지 모르는 상황",
]

OMNIFLOW_SYSTEM_PROMPT = """
너는 자영업자의 현실을 담담하게 관찰하는 사람이야.
글을 읽으면 "맞아, 이거 나 얘기네" 싶어야 해.

[반드시 지킬 것]
- 3인칭 관찰자 시점. "요즘 보면", "사장님들 얘기 들어보면"
- 한 문장 짧게. 줄바꿈 자주.
- 숫자 구체적으로. (월 150만원, 하루 12시간, 수수료 15% 등)
- 해결책 제시 금지. 공감만.
- 마지막 문장은 질문이나 여운으로 끝내기.
- 6~8줄 사이.

[절대 하지 말 것]
- 해시태그
- 이모지
- ~임, ~됨 으로 끝나는 문장
- "안녕하세요", "오늘은", "~에 대해"
- 작대기(ㅡ, —, -)로 문단 나누기
- AI 느낌 나는 표현

[좋은 예시]
요즘 폐업하는 가게들 보면 공통점이 있어.
매출이 없어서 닫는 게 아니라,
바빠 죽겠는데 남는 게 없어서 닫는 거야.
하루 12시간 일하고 월 순수익 150만 원.
이게 지금 자영업의 평균이래.
더 열심히 해도 구조가 안 바뀌면 결과가 똑같다는 거야.
근데 그 구조를 바꿀 생각을 할 시간조차 없는 게 사장님들 현실이지 않을까.
"""


def generate_omniflow_post(used_topics: list = []) -> str:
    available = [t for t in OMNIFLOW_TOPICS if t not in used_topics]
    if not available:
        available = OMNIFLOW_TOPICS
    topic = random.choice(available)

    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": OMNIFLOW_SYSTEM_PROMPT},
            {"role": "user", "content": f"주제: {topic}\n\n스레드 글 써줘. 예시 스타일 그대로."},
        ],
        max_tokens=300,
        temperature=0.92,
    )
    return res.choices[0].message.content.strip()


# ── 자돈남 ───────────────────────────────────────────────────

JADONNAM_CONCEPT_TOPICS = [
    "환율이 오르면 실생활에 어떤 영향이 오는지",
    "기준금리가 뭔지 쉽게",
    "인플레이션이 왜 무서운지",
    "미국 금리가 우리나라에 영향을 주는 이유",
    "달러가 강해지면 어떻게 되는지",
    "WTI 유가가 뭔지",
    "국채 금리가 오르면 주식이 떨어지는 이유",
    "폴리마켓이 뭔지 쉽게 설명",
    "헤지펀드가 뭔지",
    "경기침체 신호를 미리 보는 법",
    "안전자산이 뭔지 금 달러 국채",
    "무역적자가 환율에 미치는 영향",
    "연준이 왜 중요한지",
    "CPI가 뭔지 소비자물가지수",
    "비트코인이 금이랑 비교되는 이유",
    "관세가 뭔지 트럼프 관세 영향",
    "스태그플레이션이 뭔지",
    "장단기 금리 역전이 왜 불황 신호인지",
    "외환보유고가 뭔지",
    "원달러 환율 1400원 넘으면 어떻게 되는지",
]

JADONNAM_SYSTEM_PROMPT = """
너는 경제를 친구한테 설명해주는 사람이야.
어려운 말 없이, 카톡 보내듯 편하게 써.

[반드시 지킬 것]
- 짧은 문장. 줄바꿈 자주.
- 숫자 구체적으로.
- 마지막에 "이게 나한테 어떤 영향인지" 한 줄.
- 5~7줄.

[절대 하지 말 것]
- 해시태그
- 이모지
- ~임, ~됨 으로 끝나는 문장
- "안녕하세요", "오늘은", "~에 대해 알아보겠습니다"
- 작대기(ㅡ, —, -)로 문단 나누기
- AI 느낌 나는 딱딱한 표현
- 번호 매기기 (1. 2. 3.)

[좋은 예시]
기름값 또 올랐어.
WTI 기준 배럴당 85달러 넘었대.
중동 긴장이 풀릴 기미가 없으니까.
근데 정작 시장은 생각보다 덤덤해.
이미 가격에 다 반영됐다는 얘기지.
주유소 가격은 2주 뒤쯤 반응 올 것 같아.
"""


def generate_jadonnam_news_post(top_news: list) -> str:
    if not top_news:
        return generate_jadonnam_concept_post()

    news = random.choice(top_news[:3])
    label = news.get("label", "")
    title = news.get("title", "")

    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"오늘 주요 이슈: {label}\n관련 뉴스: {title}\n\n이 내용 기반으로 스레드 글 써줘."},
        ],
        max_tokens=300,
        temperature=0.85,
    )
    return res.choices[0].message.content.strip()


def generate_jadonnam_concept_post() -> str:
    topic = random.choice(JADONNAM_CONCEPT_TOPICS)
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"주제: {topic}\n\n스레드 글 써줘."},
        ],
        max_tokens=300,
        temperature=0.85,
    )
    return res.choices[0].message.content.strip()


def generate_jadonnam_top5_separate(news_items: list, poly_items: list, market_items: list) -> list:
    """뉴스/폴리마켓/시장반응 각각 별도 글 3개 반환"""
    results = []

    # 뉴스 TOP5
    news_labels = "\n".join([f"{i+1}위 {item['label']}" for i, item in enumerate(news_items[:5])])
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"오늘 뉴스 TOP5야.\n\n{news_labels}\n\n이걸 친구한테 얘기하듯 정리해줘. '오늘 뉴스 흐름 봤어?' 이런 느낌으로 시작해."},
        ],
        max_tokens=350,
        temperature=0.8,
    )
    results.append(res.choices[0].message.content.strip())

    # 폴리마켓 TOP5
    poly_labels = "\n".join([f"{i+1}위 {item['label']}" for i, item in enumerate(poly_items[:5])])
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"오늘 폴리마켓 베팅 TOP5야.\n\n{poly_labels}\n\n외국인들이 돈 걸고 있는 거 친구한테 얘기하듯 정리해줘. 폴리마켓 설명 없이 바로 내용으로."},
        ],
        max_tokens=350,
        temperature=0.8,
    )
    results.append(res.choices[0].message.content.strip())

    # 시장반응 TOP5
    market_labels = "\n".join([f"{i+1}위 {item['label']}" for i, item in enumerate(market_items[:5])])
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
            {"role": "user", "content": f"오늘 시장 반응 TOP5야.\n\n{market_labels}\n\n돈이 어디로 흘렀는지 친구한테 얘기하듯 정리해줘."},
        ],
        max_tokens=350,
        temperature=0.8,
    )
    results.append(res.choices[0].message.content.strip())

    return results


# ── 실행 함수 ────────────────────────────────────────────────

def run_omniflow_posts(count: int = 7):
    if not OMNIFLOW_USERNAME or not OMNIFLOW_PASSWORD:
        print("[자영업] 환경변수 없음")
        return
    used = []
    for i in range(count):
        print(f"[자영업] {i+1}/{count} 생성 중...")
        text = generate_omniflow_post(used)
        used.append(text[:30])
        print(f"[자영업] 생성:\n{text}\n")
        post_to_threads(OMNIFLOW_USERNAME, OMNIFLOW_PASSWORD, text)


def run_omniflow_single():
    if not OMNIFLOW_USERNAME or not OMNIFLOW_PASSWORD:
        print("[자영업] 환경변수 없음")
        return
    print("[자영업] 공감글 생성 중...")
    text = generate_omniflow_post()
    print(f"[자영업] 생성:\n{text}\n")
    post_to_threads(OMNIFLOW_USERNAME, OMNIFLOW_PASSWORD, text)


def run_jadonnam_midday_post(top_news: list = [], is_news_turn: bool = False):
    if not JADONNAM_USERNAME or not JADONNAM_PASSWORD:
        print("[자돈남] 환경변수 없음")
        return
    print("[자돈남] 경제 단신 생성 중...")
    if is_news_turn and top_news:
        text = generate_jadonnam_news_post(top_news)
    else:
        text = generate_jadonnam_concept_post()
    print(f"[자돈남] 생성:\n{text}\n")
    post_to_threads(JADONNAM_USERNAME, JADONNAM_PASSWORD, text)


def run_jadonnam_top5_post(news_items: list, poly_items: list, market_items: list):
    if not JADONNAM_USERNAME or not JADONNAM_PASSWORD:
        print("[자돈남] 환경변수 없음")
        return
    print("[자돈남] TOP5 3개 글 생성 중...")
    texts = generate_jadonnam_top5_separate(news_items, poly_items, market_items)
    labels = ["뉴스", "폴리마켓", "시장반응"]
    ok_count = 0
    for i, text in enumerate(texts):
        print(f"[자돈남 {labels[i]}]\n{text}\n")
        ok = post_to_threads(JADONNAM_USERNAME, JADONNAM_PASSWORD, text)
        if ok:
            ok_count += 1
    print(f"[자돈남 스레드 TOP5 결과] 성공 {ok_count}/{len(texts)}")


if __name__ == "__main__":
    print("=== 자영업 공감글 테스트 ===")
    print(generate_omniflow_post())
    print("\n=== 자돈남 개념 글 테스트 ===")
    print(generate_jadonnam_concept_post())
