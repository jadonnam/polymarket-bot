"""
instagram_v2.py — Instagram Graph API 자동 업로드 (CTA 강화)

필요한 환경변수:
- INSTAGRAM_ACCESS_TOKEN
- INSTAGRAM_ACCOUNT_ID
- IMGBB_API_KEY (imgbb.com 무료 발급)
"""

import os
import time
import base64
import requests

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
ACCOUNT_ID   = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")

GRAPH_URL = "https://graph.facebook.com/v19.0"

# ── 토픽별 해시태그 ──────────────────────────────────────────
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

# ── 토픽별 CTA (저장/댓글 유도) ─────────────────────────────
CTA_LINES = {
    "OIL": [
        "저장해두면 다음 유가 흐름을 볼 때 도움됩니다",
        "유가 뉴스는 생활비와 연결되니 저장해두는 편이 좋습니다",
        "이런 흐름은 계속 체크하는 편이 좋습니다",
    ],
    "BTC": [
        "저장해두면 다음 코인 흐름을 볼 때 도움됩니다",
        "코인 변동성은 숫자와 함께 보는 편이 좋습니다",
        "이런 흐름은 계속 체크하는 편이 좋습니다",
    ],
    "GOLD": [
        "저장해두면 다음 금값 흐름을 볼 때 도움됩니다",
        "불안한 장에서는 금 흐름도 함께 보는 편이 좋습니다",
        "안전자산 흐름은 계속 체크하는 편이 좋습니다",
    ],
    "RATE": [
        "저장해두면 다음 금리 흐름을 볼 때 도움됩니다",
        "금리 이슈는 달러와 주식까지 함께 흔듭니다",
        "금리 흐름은 계속 체크하는 편이 좋습니다",
    ],
    "TRUMP": [
        "저장해두면 다음 정책 이슈를 볼 때 도움됩니다",
        "정책 뉴스는 결국 가격표로 번지는 경우가 많습니다",
        "정책 흐름은 계속 체크하는 편이 좋습니다",
    ],
    "GENERAL": [
        "저장해두면 다음 흐름을 볼 때 도움됩니다",
        "숫자부터 보면 시장 반응이 더 잘 보입니다",
        "이런 흐름은 계속 체크하는 편이 좋습니다",
    ],
}


def _pick_cta(key, seed=""):
    import hashlib
    lines = CTA_LINES.get(key, CTA_LINES["GENERAL"])
    if seed:
        h = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16)
        return lines[h % len(lines)]
    return lines[0]


def build_caption(rewritten, topic_key="GENERAL", is_breaking=False):
    """인스타 캡션 생성 (CTA + 해시태그 포함)"""
    title1 = rewritten.get("title1", "")
    title2 = rewritten.get("title2", "")
    eyebrow = rewritten.get("eyebrow", "")
    desc1  = rewritten.get("desc1", "")
    desc2  = rewritten.get("desc2", "")

    hashtags = HASHTAGS.get(topic_key, HASHTAGS["GENERAL"])
    cta = _pick_cta(topic_key, seed=title1)

    # 폴리마켓 소스면 확률 표기 추가
    prob = rewritten.get("_prob", "")
    vol  = rewritten.get("_volume", "")

    extra = ""
    if prob and vol:
        extra = f"\n📊 폴리마켓 예측 확률 {prob} | 거래대금 {vol}"
    elif prob:
        extra = f"\n📊 폴리마켓 예측 확률 {prob}"

    breaking_tag = "🚨 속보 — " if is_breaking else ""

    caption = f"""{breaking_tag}{eyebrow}

{title1}
{title2}

{desc1}
{desc2}{extra}

━━━━━━━━━━━━━━
{cta}

지갑에 영향 오는 이슈만 매일 정리합니다.
저장해두면 다음 흐름을 볼 때 도움됩니다.

{hashtags} #jadonnam #폴리마켓 #예측시장"""

    return caption.strip()


def upload_to_imgbb(image_path):
    """imgbb.com에 이미지 업로드 → 퍼블릭 URL 반환"""
    if not IMGBB_API_KEY:
        raise RuntimeError("IMGBB_API_KEY 없음. imgbb.com에서 무료 발급 필요")

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
    """캐러셀 아이템 컨테이너 생성"""
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
    """캐러셀 메인 컨테이너 생성"""
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
    print(f"[Instagram] 포스팅 완료! {data['id']}")
    return data["id"]


def upload_single(image_path, caption):
    """단일 이미지 업로드"""
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
    """
    캐러셀 (3장) 업로드
    image_paths: [card1.png, card2.png, card3.png]
    """
    if not ACCESS_TOKEN or not ACCOUNT_ID:
        print("[Instagram] 토큰 없음 → 스킵")
        return None

    try:
        # 1. 각 이미지 imgbb 업로드
        urls = []
        for p in image_paths:
            url = upload_to_imgbb(p)
            urls.append(url)
            time.sleep(1)

        # 2. 각 이미지 캐러셀 아이템 컨테이너 생성
        item_ids = []
        for url in urls:
            iid = create_carousel_item(url)
            item_ids.append(iid)
            time.sleep(1)

        # 3. 캐러셀 메인 컨테이너
        cid = create_carousel_container(item_ids, caption)

        # 4. 처리 대기
        wait_ready(cid)

        # 5. 발행
        return publish(cid)

    except Exception as e:
        print(f"[Instagram carousel ERROR] {e}")
        # 폴백: 첫 번째 이미지만 단일 업로드
        print("[Instagram] 폴백: 단일 이미지 업로드 시도")
        return upload_single(image_paths[0], caption)
