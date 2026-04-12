
"""
threads_auto.py — 스레드 자동 포스팅 시스템
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
    except Exception as e:
        print(f"[Threads] 모듈 로드 실패: {repr(e)}")
        return False

    try:
        api = ThreadsAPI(username=username, password=password)
        api.publish(caption=text)
        print(f"[Threads] 업로드 성공: {username}")
        return True
    except Exception as e:
        print(f"[Threads] 업로드 실패: {repr(e)}")
        return False


OMNIFLOW_TOPICS = [
    "배달앱 수수료가 올라갈수록 사장님 몫이 줄어드는 구조",
    "알바를 구하기 힘든 현실",
    "단골손님이 줄어드는 이유",
    "임대료 인상 압박",
    "매출은 있는데 남는 게 없는 구조",
]

OMNIFLOW_SYSTEM_PROMPT = """
너는 자영업자의 현실을 담담하게 관찰하는 사람이야.
글을 읽으면 "맞아, 이거 나 얘기네" 싶어야 해.
짧은 문장. 줄바꿈 자주. 해결책 제시 금지. 6~8줄.
"""

def generate_omniflow_post(used_topics: list = []) -> str:
    available = [t for t in OMNIFLOW_TOPICS if t not in used_topics] or OMNIFLOW_TOPICS
    topic = random.choice(available)
    res = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": OMNIFLOW_SYSTEM_PROMPT},
            {"role": "user", "content": f"주제: {topic}\n\n스레드 글 써줘."},
        ],
        max_tokens=300,
        temperature=0.92,
    )
    return res.choices[0].message.content.strip()


JADONNAM_CONCEPT_TOPICS = [
    "환율이 오르면 실생활에 어떤 영향이 오는지",
    "기준금리가 뭔지 쉽게",
    "인플레이션이 왜 무서운지",
    "미국 금리가 우리나라에 영향을 주는 이유",
]

JADONNAM_SYSTEM_PROMPT = """
너는 경제를 친구한테 설명해주는 사람이야.
어려운 말 없이, 카톡 보내듯 편하게 써.
짧은 문장. 줄바꿈 자주. 마지막에 나한테 어떤 영향인지 한 줄. 5~7줄.
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
    results = []
    labels_sets = [
        ("뉴스 TOP5", news_items),
        ("폴리마켓 TOP5", poly_items),
        ("시장반응 TOP5", market_items),
    ]
    for name, items in labels_sets:
        labels = "\n".join([f"{i+1}위 {item['label']}" for i, item in enumerate(items[:5])])
        res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": JADONNAM_SYSTEM_PROMPT},
                {"role": "user", "content": f"오늘 {name}야.\n\n{labels}\n\n친구한테 얘기하듯 짧게 정리해줘."},
            ],
            max_tokens=350,
            temperature=0.8,
        )
        results.append(res.choices[0].message.content.strip())
    return results


def run_omniflow_single():
    if not OMNIFLOW_USERNAME or not OMNIFLOW_PASSWORD:
        print("[자영업] 환경변수 없음")
        return
    text = generate_omniflow_post()
    ok = post_to_threads(OMNIFLOW_USERNAME, OMNIFLOW_PASSWORD, text)
    print(f"[자영업 스레드 결과] {'성공' if ok else '실패'}")


def run_jadonnam_midday_post(top_news: list = [], is_news_turn: bool = False):
    if not JADONNAM_USERNAME or not JADONNAM_PASSWORD:
        print("[자돈남] 환경변수 없음")
        return
    text = generate_jadonnam_news_post(top_news) if is_news_turn and top_news else generate_jadonnam_concept_post()
    ok = post_to_threads(JADONNAM_USERNAME, JADONNAM_PASSWORD, text)
    print(f"[자돈남 중간 스레드 결과] {'성공' if ok else '실패'}")


def run_jadonnam_top5_post(news_items: list, poly_items: list, market_items: list):
    if not JADONNAM_USERNAME or not JADONNAM_PASSWORD:
        print("[자돈남] 환경변수 없음")
        return
    texts = generate_jadonnam_top5_separate(news_items, poly_items, market_items)
    ok_count = 0
    labels = ["뉴스", "폴리마켓", "시장반응"]
    for i, text in enumerate(texts):
        print(f"[자돈남 {labels[i]} 생성]\n{text}\n")
        ok = post_to_threads(JADONNAM_USERNAME, JADONNAM_PASSWORD, text)
        if ok:
            ok_count += 1
    print(f"[자돈남 스레드 TOP5 결과] 성공 {ok_count}/{len(texts)}")
