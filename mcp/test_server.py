#!/usr/bin/env python3
"""
네이버 검색 서버 테스트
"""

import subprocess
import os

def test_naver_server():
    """서버 기능 테스트"""
    
    print("🧪 네이버 검색 서버 테스트 시작...")
    print()
    
    tests = [
        {
            "name": "회사명 추출 테스트",
            "command": ["python3", "naver_mcp_server.py", "extract", "베스핀글로벌 최근 뉴스 알려줘"],
            "expected_keywords": ["베스핀글로벌"]
        },
        {
            "name": "뉴스 검색 테스트",
            "command": ["python3", "naver_mcp_server.py", "news", "베스핀글로벌", "3"],
            "expected_keywords": ["뉴스", "검색 결과"]
        },
        {
            "name": "웹 검색 테스트", 
            "command": ["python3", "naver_mcp_server.py", "web", "베스핀글로벌", "2"],
            "expected_keywords": ["웹문서", "검색 결과"]
        },
        {
            "name": "종합 검색 테스트",
            "command": ["python3", "naver_mcp_server.py", "summary", "베스핀글로벌에 대해 알려줘"],
            "expected_keywords": ["종합 정보", "뉴스", "웹문서"]
        }
    ]
    
    for i, test in enumerate(tests, 1):
        print(f"📋 테스트 {i}: {test['name']}")
        
        try:
            result = subprocess.run(
                test["command"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                # 키워드 체크
                success = all(keyword in output for keyword in test["expected_keywords"])
                
                if success:
                    print(f"✅ 성공")
                    print(f"📄 결과 미리보기: {output[:150]}...")
                else:
                    print(f"⚠️  부분 성공 (키워드 부족)")
                    print(f"📄 결과: {output[:200]}...")
            else:
                print(f"❌ 실패: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ 타임아웃 (30초 초과)")
        except Exception as e:
            print(f"🔥 예외 발생: {str(e)}")
        
        print()
    
    print("🎯 테스트 완료!")
    print()
    print("💡 다음 단계:")
    print("1. .env 파일에 네이버 API 키 설정")
    print("2. msp_core.py에 통합 함수 추가")
    print("3. 전체 시스템 테스트")

if __name__ == "__main__":
    test_naver_server()
