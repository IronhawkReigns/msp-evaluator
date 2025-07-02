"""
네이버 검색 서버
"""

import json
import sys
import urllib.parse
import urllib.request
import os
import re
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def clean_html_tags(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정리"""
    if not text:
        return ""
    
    text = text.replace('<b>', '').replace('</b>', '')
    text = text.replace('&quot;', '"').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

def extract_company_name_simple(question: str) -> str:
    """간단한 회사명 추출"""
    import re
    
    patterns = [
        r'([가-힣A-Za-z0-9\s]+)에\s*대해',
        r'([가-힣A-Za-z0-9\s]+)의\s*뉴스',
        r'([가-힣A-Za-z0-9\s]+)\s*뉴스',
        r'([가-힣A-Za-z0-9\s]+)\s*최근',
        r'([가-힣A-Za-z0-9\s]+)\s*소식'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            company_name = match.group(1).strip()
            if company_name not in ['회사', '기업', '그', '이', '그것', '뉴스', '소식']:
                return company_name
    
    words = question.split()
    for word in words:
        if len(word) > 2 and word not in ['뉴스', '소식', '정보', '알려줘', '어떤', '어떻게']:
            return word
    
    return question.strip()

def naver_news_search(query: str, max_results: int = 10):
    """네이버 뉴스 검색"""
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://openapi.naver.com/v1/search/news.json?query={encoded_query}&display={max_results}&sort=sim"
        
        headers = {
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                return f"네이버 API 오류: {response.status}"
            
            data = json.loads(response.read().decode("utf-8"))
        
        if "items" not in data or not data["items"]:
            return f"'{query}'에 대한 뉴스 기사를 찾을 수 없습니다."
        
        # 결과 포맷팅 (기존 msp_core와 호환)
        results = []
        for i, item in enumerate(data["items"], 1):
            title = clean_html_tags(item.get("title", ""))
            description = clean_html_tags(item.get("description", ""))
            pub_date = item.get("pubDate", "")[:10] if item.get("pubDate") else "날짜 없음"
            link = item.get("originallink", item.get("link", ""))
            
            result_text = f"""📰 뉴스 {i}
제목: {title}
날짜: {pub_date}
세부내용: {description}
링크: {link}
"""
            results.append(result_text)
        
        final_result = f"""🔍 '{query}' 뉴스 검색 결과 ({len(data['items'])}건)

{chr(10).join(results)}

검색 통계:
- 총 검색 결과: {data.get('total', 0)}건
- 표시된 결과: {len(data['items'])}건"""
        
        return final_result
        
    except Exception as e:
        return f"뉴스 검색 중 오류 발생: {str(e)}"

def naver_web_search(query: str, max_results: int = 5):
    """네이버 웹 검색"""
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://openapi.naver.com/v1/search/webkr.json?query={encoded_query}&display={max_results}&sort=sim"
        
        headers = {
            "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
            "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET")
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                return f"네이버 API 오류: {response.status}"
            
            data = json.loads(response.read().decode("utf-8"))
        
        if "items" not in data or not data["items"]:
            return f"'{query}'에 대한 웹 문서를 찾을 수 없습니다."
        
        # 결과 포맷팅
        results = []
        for i, item in enumerate(data["items"], 1):
            title = clean_html_tags(item.get("title", ""))
            description = clean_html_tags(item.get("description", ""))
            link = item.get("link", "")
            
            result_text = f"""🌐 웹문서 {i}
제목: {title}
요약: {description}
링크: {link}
"""
            results.append(result_text)
        
        final_result = f"""🔍 '{query}' 웹 검색 결과 ({len(data['items'])}건)

{chr(10).join(results)}

검색 통계:
- 총 검색 결과: {data.get('total', 0)}건
- 표시된 결과: {len(data['items'])}건"""
        
        return final_result
        
    except Exception as e:
        return f"웹 검색 중 오류 발생: {str(e)}"

def company_news_summary(question: str):
    """회사 종합 정보 검색"""
    company_name = extract_company_name_simple(question)
    
    news_result = naver_news_search(company_name, 8)
    web_result = naver_web_search(company_name, 5)
    
    final_result = f"""🏢 {company_name} 종합 정보 요약

질문: {question}

{news_result}

{web_result}

요약:
- 회사명: {company_name}
- 뉴스 검색 완료
- 웹 문서 검색 완료
- AI 분석을 위한 데이터 수집 완료

활용 방안:
- 이 데이터를 Claude/GPT에 전달하여 상세 분석 가능
- 실시간 최신 정보 기반 인사이트 제공"""
    
    return final_result

def main():
    """CLI 인터페이스"""
    if len(sys.argv) < 3:
        print("""
사용법:
  python naver_search_server.py news [회사명] [개수]
  python naver_search_server.py web [회사명] [개수]  
  python naver_search_server.py extract [질문]
  python naver_search_server.py summary [질문]
        """)
        return
    
    command = sys.argv[1]
    
    if command == "news":
        query = sys.argv[2]
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        result = naver_news_search(query, max_results)
        
    elif command == "web":
        query = sys.argv[2]
        max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        result = naver_web_search(query, max_results)
        
    elif command == "extract":
        question = sys.argv[2]
        company_name = extract_company_name_simple(question)
        result = f"추출된 회사명: {company_name}"
        
    elif command == "summary":
        question = sys.argv[2]
        result = company_news_summary(question)
        
    else:
        result = "지원되지 않는 명령어입니다."
    
    print(result)

if __name__ == "__main__":
    main()
