"""
RAG Context Module
홈페이지 콘텐츠를 수집하여 AI Agent가 응답 생성 시 참조할 수 있는 컨텍스트를 제공
"""
import json
from typing import Dict, List, Optional
from datetime import datetime


def get_services_context() -> str:
    """서비스 및 서비스 옵션 정보를 컨텍스트로 수집"""
    from utils.mongo_models import Service, ServiceOption
    
    context_parts = []
    context_parts.append("=== 스타일그래퍼 서비스 정보 ===\n")
    
    services = Service.query_all()
    
    for service in services:
        context_parts.append(f"\n## 카테고리: {service.name}")
        context_parts.append(f"설명: {service.description}")
        
        # 서비스 옵션들
        if service.options:
            for option in service.options:
                context_parts.append(f"\n### 서비스: {option.name}")
                if option.description:
                    context_parts.append(f"간단 설명: {option.description}")
                if option.detailed_description:
                    context_parts.append(f"상세 설명: {option.detailed_description}")
                
                # 상세 내용
                if option.details:
                    try:
                        details = json.loads(option.details)
                        if details:
                            context_parts.append("서비스 특징:")
                            for detail in details:
                                context_parts.append(f"  - {detail}")
                    except:
                        pass
                
                # 패키지 정보
                if option.packages:
                    try:
                        packages_data = json.loads(option.packages)
                        if isinstance(packages_data, dict) and 'tables' in packages_data:
                            for table in packages_data.get('tables', []):
                                table_title = table.get('title', '')
                                if table_title:
                                    context_parts.append(f"\n{table_title}:")
                                for pkg in table.get('packages', []):
                                    name = pkg.get('name', '')
                                    price = pkg.get('price', '')
                                    duration = pkg.get('duration', '')
                                    desc = pkg.get('description', '')
                                    notes = pkg.get('notes', '')
                                    
                                    pkg_info = f"  • {name}"
                                    if price:
                                        pkg_info += f" - {price}"
                                    if duration:
                                        pkg_info += f" ({duration})"
                                    context_parts.append(pkg_info)
                                    if desc:
                                        context_parts.append(f"    {desc}")
                                    if notes:
                                        context_parts.append(f"    참고: {notes}")
                        elif isinstance(packages_data, list):
                            context_parts.append("패키지 옵션:")
                            for pkg in packages_data:
                                name = pkg.get('name', '')
                                price = pkg.get('price', '')
                                context_parts.append(f"  • {name}: {price}")
                    except:
                        pass
                
                # 예약 조건
                if option.booking_method:
                    context_parts.append(f"예약 방법: {option.booking_method}")
                if option.payment_info:
                    context_parts.append(f"결제 방식: {option.payment_info}")
                if option.guide_info:
                    context_parts.append(f"안내 사항: {option.guide_info}")
                if option.refund_policy_text:
                    context_parts.append(f"환불 규정: {option.refund_policy_text}")
    
    return "\n".join(context_parts)


def get_company_info_context() -> str:
    """회사 기본 정보 컨텍스트"""
    context = """
=== 스타일그래퍼 회사 정보 ===

회사명: 스타일그래퍼 (Stylegrapher)
이메일: ysg.stylegrapher@gmail.com
업종: 개인 스타일링, 이미지 컨설팅, 프로필 사진 촬영

서비스 분야:
1. AI 분석 - 인공지능을 활용한 정밀 스타일 분석
2. 컨설팅 프로그램 - 전문가와 함께하는 1:1 맞춤 컨설팅
3. 원데이 스타일링 - 하루만에 완성하는 완벽한 변신
4. 프리미엄 화보 제작 - 특별한 순간을 기록하는 전문 촬영

고객 응대 원칙:
- 친절하고 전문적인 응대
- 고객의 요구사항을 정확히 파악
- 맞춤형 서비스 안내
- 신속한 답변 제공
"""
    return context


def get_terms_context() -> str:
    """이용약관 컨텍스트"""
    from utils.mongo_models import TermsOfService
    
    terms = TermsOfService.get_current_content()
    if terms and terms.content:
        return f"\n=== 이용약관 ===\n{terms.content}"
    return ""


def get_privacy_policy_context() -> str:
    """개인정보처리방침 컨텍스트"""
    from utils.mongo_models import PrivacyPolicy
    
    policy = PrivacyPolicy.get_current_content()
    if policy and policy.content:
        return f"\n=== 개인정보처리방침 ===\n{policy.content}"
    return ""


def get_full_rag_context(include_terms: bool = False) -> str:
    """
    전체 RAG 컨텍스트 수집
    
    Args:
        include_terms: 이용약관/개인정보처리방침 포함 여부 (기본: False, 토큰 절약)
    
    Returns:
        str: RAG 컨텍스트 문자열
    """
    context_parts = []
    
    # 회사 정보
    context_parts.append(get_company_info_context())
    
    # 서비스 정보
    context_parts.append(get_services_context())
    
    # 이용약관/개인정보처리방침 (선택적)
    if include_terms:
        context_parts.append(get_terms_context())
        context_parts.append(get_privacy_policy_context())
    
    return "\n\n".join(context_parts)


def get_service_specific_context(service_id: Optional[int] = None) -> str:
    """
    특정 서비스에 대한 상세 컨텍스트
    
    Args:
        service_id: 서비스 ID
    
    Returns:
        str: 특정 서비스 관련 컨텍스트
    """
    if not service_id:
        return get_services_context()
    
    from utils.mongo_models import Service, ServiceOption
    
    context_parts = []
    
    # 서비스 정보 조회
    service = Service.get_by_id(service_id)
    if service:
        context_parts.append(f"=== 문의 대상 서비스: {service.name} ===")
        context_parts.append(f"설명: {service.description}")
        
        for option in service.options:
            context_parts.append(f"\n### {option.name}")
            if option.description:
                context_parts.append(f"설명: {option.description}")
            if option.detailed_description:
                context_parts.append(f"상세: {option.detailed_description}")
            
            # 패키지 정보
            if option.packages:
                try:
                    packages_data = json.loads(option.packages)
                    if isinstance(packages_data, dict) and 'tables' in packages_data:
                        for table in packages_data.get('tables', []):
                            table_title = table.get('title', '')
                            if table_title:
                                context_parts.append(f"\n{table_title}:")
                            for pkg in table.get('packages', []):
                                name = pkg.get('name', '')
                                price = pkg.get('price', '')
                                duration = pkg.get('duration', '')
                                context_parts.append(f"  • {name}: {price}" + (f" ({duration})" if duration else ""))
                except:
                    pass
            
            # 예약 조건
            if option.booking_method:
                context_parts.append(f"예약 방법: {option.booking_method}")
            if option.payment_info:
                context_parts.append(f"결제: {option.payment_info}")
            if option.refund_policy_text:
                context_parts.append(f"환불: {option.refund_policy_text}")
    
    # 기본 회사 정보도 추가
    context_parts.append(get_company_info_context())
    
    return "\n".join(context_parts)


def get_response_guidelines() -> str:
    """AI 응답 생성 가이드라인"""
    return """
=== 응답 생성 가이드라인 ===

1. 응답 톤:
   - 친절하고 전문적인 톤 유지
   - 고객의 언어에 맞춰 응답 (한국어/영어/일본어/중국어)
   - 고객의 감정에 공감하며 응대

2. 응답 구조:
   - 인사말로 시작
   - 문의 내용에 대한 답변
   - 추가 안내 또는 다음 단계 제안
   - 마무리 인사

3. 포함해야 할 정보:
   - 문의한 서비스에 대한 명확한 안내
   - 가격 정보 (해당되는 경우)
   - 예약 방법 안내
   - 연락처 정보

4. 피해야 할 것:
   - 확인되지 않은 정보 제공
   - 약속할 수 없는 내용 언급
   - 경쟁사 언급
   - 부정적인 표현

5. 서명:
   - 항상 "스타일그래퍼 팀" 또는 "Stylegrapher Team"으로 마무리
"""



