import os
import time
import base64
import hashlib
import requests

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")

GRAPH_URL = "https://graph.facebook.com/v19.0"

HASHTAGS = {
    "OIL":     "#유가 #기름값 #원유 #wti #물가 #경제뉴스 #재테크 #돈공부 #경제정보 #투자공부",
    "BTC":     "#비트코인 #코인 #bitcoin #암호화폐 #가상화폐 #코인투자 #재테크 #돈공부 #코인시장",
    "ETH":     "#이더리움 #ethereum #알트코인 #코인투자 #암호화폐 #재테크 #돈공부 #코인시장",
    "GOLD":    "#금값 #금투자 #안전자산 #골드 #재테크 #경제뉴스 #돈공부 #실물자산",
    "RATE":    "#금리 #연준 #fed #나스닥 #미국주식 #경제뉴스 #재테크 #돈공부 #미장",
    "CPI":     "#cpi #물가 #인플레이션 #금리 #경제뉴스 #재테크 #돈공부 #미국경제",
    "BOND":    "#채권 #국채금리 #연준 #미국주식 #경제뉴스 #재테크 #돈공부 #미장",
    "TRUMP":   "#트럼프 #관세 #미국경제 #무역 #달러 #경제뉴스 #재테크 #돈공부",
    "DEAL":    "#무역협상 #트럼프 #달러 #경제뉴스 #재테크 #돈공부 #미국경제",
    "TRADE":   "#관세 #무역전쟁 #물가 #경제뉴스 #재테크 #돈공부 #글로벌경제",
    "STOCK":   "#미국주식 #나스닥 #s&p500 #미장 #주식투자 #경제뉴스 #재테크 #돈공부",
    "MIDEAST": "#중동 #유가 #지정학 #원유 #경제뉴스 #재테크 #돈공부 #글로벌경제",
    "GENERAL": "#경제뉴스 #재테크 #돈공부 #시장분석 #투자 #경제정보 #머니",
}

CTA_LINES = {
    "OIL": [
        "저장해두면 다음 유가 뉴스와 비교해서 보기 쉽다",
        "유가 이슈는 체감이 늦어도 돈은 먼저 움직인다",
        "기름값 뉴스는 결국 생활비와 연결된다",
    ],
    "BTC": [
        "비트 흐름은 코인판 전체 분위기를 읽는 데 도움됩니다",
        "코인을 하는 사람은 저장해두면 방향 체크에 유리하다",
        "숫자를 함께 보면 감정 매매를 줄이기 쉽다",
    ],
    "ETH": [
        "이더는 알트 분위기를 빠르게 보여주는 편이다",
        "알트장 흐름은 이더와 함께 보면 더 잘 보인다",
        "저장해두면 비트와 비교해서 보기 좋다",
    ],
    "GOLD": [
        "금값은 시장 공포를 읽는 쉬운 신호 중 하나다",
        "안전자산 흐름은 저장해두고 비교해서 보는 편이 낫다",
        "불안한 장에서는 금 흐름을 같이 봐야 한다",
    ],
    "RATE": [
        "금리 뉴스는 내 투자에 늦게라도 거의 다 연결된다",
        "연준 이슈는 저장해두고 흐름을 비교하는 것이 좋다",
        "달러와 나스닥을 같이 보는 사람에게는 중요한 숫자다",
    ],
    "TRUMP": [
        "정책 뉴스는 정치 얘기로 끝나지 않고 가격으로 번지는 경우가 많다",
        "관세와 정책 변수는 결국 달러와 물가 기대를 흔든다",
        "저장해두면 다음 정책 뉴스와 연결해서 보기 좋다",
    ],
    "MIDEAST": [
        "중동 뉴스는 결국 유가와 금값으로 번지는 경우가 많다",
        "지정학 뉴스는 체감보다 가격에서 먼저 반응한다",
        "저장해두면 다음 전쟁 뉴스와 비교해서 보기 쉽다",
    ],
    "GENERAL": [
        "저장해두면 다음 뉴스 볼 때 흐름 연결에 도움됩니다",
        "숫자부터 보면 기사보다 시장 반응이 더 잘 보인다",
        "이런 이슈는 지나가도 다시 체감으로 돌아올 수 있다",
    ],
}


def _pick_cta(key, seed=""):
    lines = CTA_LINES.get(key, CTA_LINES["GENERAL"])
    if seed:
        h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
        return lines[h % len(lines)]
    return lines[0]


def build_caption(rewritten, topic_key="GENERAL", is_breaking=False):
    title1 = rewritten.get("title1", "")
    title2 = rewritten.get("title2", "")
    eyebrow = rewritten.get("eyebrow", "")
    desc1 = rewritten.get("desc1", "")
    desc2 = rewritten.get("desc2", "")
    prob = rewritten.get("_prob", "")
    vol = rewritten.get("_volume", "")
    price = rewritten.get("_price_usd", "")

    hashtags = HASHTAGS.get(topic_key, HASHTAGS["GENERAL"])
    cta = _pick_cta(topic_key, seed=title1 + title2)

    extra_lines = []
    if prob and vol:
        extra_lines.append(f"📊 폴리마켓 확률 {prob} · 거래대금 {vol}")
    elif prob:
        extra_lines.append(f"📊 폴리마켓 확률 {prob}")
    if price:
        extra_lines.append(f"💵 실시간 체크값 {price}")

    extra = "\n".join(extra_lines)
    breaking_tag = "🚨 속보다\n\n" if is_breaking else ""

    caption = f"""{breaking_tag}{eyebrow}

{title1}
{title2}

{desc1}
{desc2}
{extra}

━━━━━━━━━━━━━━
{cta}

지갑에 영향 오는 이슈만
핵심 숫자 위주로 정리한다.

{hashtags} #jadonnam #폴리마켓 #예측시장"""

    return "\n".join([line.rstrip() for line in caption.splitlines()]).strip()


def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        raise RuntimeError("IMGBB_API_KEY 없음")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    res = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": b64},
        timeout=30,
    )
    data = res.json()
    if not data.get("success"):
        raise RuntimeError(f"imgbb 업로드 실패: {data}")

    url = data["data"]["url"]
    print(f"[imgbb] {url}")
    return url


def create_container(image_url, caption):
    res = requests.post(
        f"{GRAPH_URL}/{ACCOUNT_ID}/media",
        params={"image_url": image_url, "caption": caption, "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    data = res.json()
    if "id" not in data:
        raise RuntimeError(f"컨테이너 생성 실패: {data}")
    print(f"[Instagram] 컨테이너: {data['id']}")
    return data["id"]


def create_carousel_item(image_url):
    res = requests.post(
        f"{GRAPH_URL}/{ACCOUNT_ID}/media",
        params={
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )
    data = res.json()
    if "id" not in data:
        raise RuntimeError(f"캐러셀 아이템 생성 실패: {data}")
    return data["id"]


def create_carousel_container(item_ids, caption):
    res = requests.post(
        f"{GRAPH_URL}/{ACCOUNT_ID}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )
    data = res.json()
    if "id" not in data:
        raise RuntimeError(f"캐러셀 컨테이너 생성 실패: {data}")
    print(f"[Instagram] 캐러셀 컨테이너: {data['id']}")
    return data["id"]


def wait_ready(container_id, max_wait=90):
    for _ in range(max_wait // 5):
        time.sleep(5)
        res = requests.get(
            f"{GRAPH_URL}/{container_id}",
            params={"fields": "status_code", "access_token": ACCESS_TOKEN},
            timeout=10,
        )
        status = res.json().get("status_code", "")
        print(f"[Instagram] 상태: {status}")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError("컨테이너 처리 오류")
    raise RuntimeError("타임아웃")


def publish(container_id):
    res = requests.post(
        f"{GRAPH_URL}/{ACCOUNT_ID}/media_publish",
        params={"creation_id": container_id, "access_token": ACCESS_TOKEN},
        timeout=30,
    )
    data = res.json()
    if "id" not in data:
        raise RuntimeError(f"발행 실패: {data}")
    print(f"[Instagram] 포스팅 완료: {data['id']}")
    return data["id"]


def upload_single(image_path, caption):
    if not ACCESS_TOKEN or not ACCOUNT_ID:
        print("[Instagram] 토큰 없음 → 스킵")
        return None
    try:
        url = upload_to_imgbb(image_path)
        cid = create_container(url, caption)
        wait_ready(cid)
        return publish(cid)
    except Exception as e:
        print(f"[Instagram ERROR] {e}")
        return None


def upload_carousel(image_paths, caption):
    if not ACCESS_TOKEN or not ACCOUNT_ID:
        print("[Instagram] 토큰 없음 → 스킵")
        return None

    try:
        urls = []
        for p in image_paths:
            urls.append(upload_to_imgbb(p))
            time.sleep(1)

        item_ids = []
        for url in urls:
            item_ids.append(create_carousel_item(url))
            time.sleep(1)

        cid = create_carousel_container(item_ids, caption)
        wait_ready(cid)
        return publish(cid)

    except Exception as e:
        print(f"[Instagram carousel ERROR] {e}")
        print("[Instagram] 폴백: 단일 이미지 업로드 시도")
        return upload_single(image_paths[0], caption)
