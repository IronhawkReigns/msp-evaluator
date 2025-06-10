import datetime

def fix_korean_encoding(text):
    """Fix Korean character encoding issues"""
    if not isinstance(text, str):
        return str(text)
    
    if not text or text in ["nan", "None"]:
        return ""
    
    try:
        # If text contains replacement characters, try to fix
        if '�' in text:
            # Try common Korean encodings
            for encoding in ['euc-kr', 'cp949']:
                try:
                    # Encode as latin-1 then decode as Korean encoding
                    fixed = text.encode('latin-1').decode(encoding)
                    return fixed
                except:
                    continue
        
        # Ensure it's properly UTF-8 encoded
        return text.encode('utf-8').decode('utf-8')
        
    except:
        return text

def map_group_to_category(group):
    """Map group names to main categories"""
    if not group or group in ["Unknown", "unknown", "미분류", ""]:
        return "미분류"
    
    group_lower = group.lower()
    
    # Exact matches first
    group_mapping = {
        "AI 전문 인력 구성": "인적역량",
        "프로젝트 경험 및 성공 사례": "인적역량", 
        "지속적인 교육 및 학습": "인적역량",
        "프로젝트 관리 및 커뮤니케이션": "인적역량",
        "AI 윤리 및 책임 의식": "인적역량",
        "AI 기술 연구 능력": "AI기술역량",
        "AI 모델 개발 능력": "AI기술역량",
        "AI 플랫폼 및 인프라 구축 능력": "AI기술역량", 
        "데이터 처리 및 분석 능력": "AI기술역량",
        "AI 기술의 융합 및 활용 능력": "AI기술역량",
        "AI 기술의 특허 및 인증 보유 현황": "AI기술역량",
        "다양성 및 전문성": "솔루션 역량",
        "안정성": "솔루션 역량", 
        "확장성 및 유연성": "솔루션 역량",
        "사용자 편의성": "솔루션 역량",
        "보안성": "솔루션 역량",
        "기술 지원 및 유지보수": "솔루션 역량",
        "차별성 및 경쟁력": "솔루션 역량",
        "개발 로드맵 및 향후 계획": "솔루션 역량"
    }
    
    if group in group_mapping:
        return group_mapping[group]
    
    # Keyword matching as fallback
    if any(keyword in group_lower for keyword in ["인력", "교육", "학습", "관리", "커뮤니케이션", "윤리", "프로젝트", "경험"]):
        return "인적역량"
    elif any(keyword in group_lower for keyword in ["ai", "기술", "모델", "플랫폼", "인프라", "데이터", "융합", "특허", "연구"]):
        return "AI기술역량"
    elif any(keyword in group_lower for keyword in ["솔루션", "다양성", "안정성", "확장성", "편의성", "보안", "지원", "차별성", "로드맵"]):
        return "솔루션 역량"
    
    return "미분류"
