import re

def extract_numbers(text):
    """
    뉴스 원문에서 쓸만한 숫자 표현 추출
    예:
    86%
    $120
    1,535원
    April 30
    3 days
    """
    if not text:
        return []

    patterns = [
        r'[\+\-]?\d+(?:\.\d+)?%',                 # 86%
        r'\$\d+(?:,\d{3})*(?:\.\d+)?',           # $120, $1,500
        r'\d+(?:,\d{3})*(?:\.\d+)?원',            # 1,535원
        r'\d+(?:,\d{3})*(?:\.\d+)?달러',          # 1500달러
        r'\d+(?:,\d{3})*(?:\.\d+)?배',            # 3배
        r'\d+(?:,\d{3})*(?:\.\d+)?일',            # 30일
        r'\d+(?:,\d{3})*(?:\.\d+)?시간',          # 24시간
        r'\d+(?:,\d{3})*(?:\.\d+)?년',            # 2026년
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}',  # April 30
        r'\d{1,2}/\d{1,2}',                       # 4/30
    ]

    found = []
    for p in patterns:
        matches = re.findall(p, text, flags=re.IGNORECASE)
        found.extend(matches)

    # 중복 제거
    unique = []
    for item in found:
        if item not in unique:
            unique.append(item)

    return unique[:5]

def choose_best_number(text, numbers):
    """
    우선순위:
    1) %
    2) 달러/원
    3) 날짜/기한
    4) 나머지
    """
    if not numbers:
        return None

    for n in numbers:
        if "%" in n:
            return n
    for n in numbers:
        if "$" in n or "원" in n or "달러" in n:
            return n
    for n in numbers:
        low = n.lower()
        if "/" in n or "apr" in low or "may" in low or "jun" in low:
            return n

    return numbers[0]