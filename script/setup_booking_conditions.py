#!/usr/bin/env python3
"""
기본 예약 조건 설정 스크립트 (텍스트 형식)
모든 서비스 옵션에 텍스트 기반 예약 조건을 설정합니다.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ServiceOption, db
from app import create_app
import json

def setup_default_booking_conditions():
    app = create_app()
    
    with app.app_context():
        # 기본 예약 방법 (텍스트 형식)
        default_booking_method = """위에 보이는 작품명, 컨셉수, 제작비와 소요시간을 확인합니다.
대략적으로 촬영을 원하는 시기를 정합니다.
스타일그래퍼 카카오채널에 문의 내용을 남깁니다.
예약 변경 및 환불 규정을 확인합니다.
담당자와 상담 후 예약이 확정되면 계약금(제작비의 20%)를 아래의 계좌에 예약자 명의로 입금합니다.
스타일그래퍼 카카오채널에 성함과 전화번호를 남깁니다."""

        # 기본 결제 방식 (텍스트 형식)
        default_payment_info = """제작비는 모두 3회로 분할 결제하실 수 있습니다.
계약금: 제작비의 20% (최초 계약 시 결제)
중도금: 제작비의 30% (사전미팅 시 결제)
잔금: 제작비의 50% (촬영일 결제)"""

        # 기본 안내 사항 (텍스트 형식)
        default_guide_info = """촬영일 약 한달-최소 2주 전에 한시간 가량의 사전미팅을 갖게 됩니다.
사전미팅에 오시기 전에 시도해 보시고 싶으신 컨셉, 마음에 드셨던 셀럽 화보 등 고객님의 취향을 파악할 수 있는 자료들을 최대한 스크랩해서 가져와 주시면 저희가 컨셉을 잡아 드리는데 도움이 됩니다:)"""

        # 기본 환불 규정 텍스트
        default_refund_policy_text = """계약금을 결제하시면 촬영일 예약이 확정됩니다.
예약 변경: 촬영 날짜/시간 변경은 촬영일 기준 30일전까지만 가능합니다.
환불 기준은 다음과 같습니다."""

        # 기본 환불 테이블 데이터
        default_refund_policy_table = """촬영일 30일 전|100%|전액환불
촬영일 15~29일 전|50%|50% 환불
촬영일 14일 이내|0%|환불 불가"""

        # 모든 서비스 옵션 조회
        options = ServiceOption.query.all()
        
        updated_count = 0
        for option in options:
            # 기존 HTML 형식 데이터를 새로운 텍스트 형식으로 변환 또는 기본값 설정
            if not option.booking_method or '<ul' in (option.booking_method or ''):
                option.booking_method = default_booking_method
                
            if not option.payment_info or '<ul' in (option.payment_info or ''):
                option.payment_info = default_payment_info
                
            if not option.guide_info or '<p>' in (option.guide_info or ''):
                option.guide_info = default_guide_info
                
            # 새로운 필드들 설정
            if not option.refund_policy_text:
                option.refund_policy_text = default_refund_policy_text
                
            if not option.refund_policy_table:
                option.refund_policy_table = default_refund_policy_table
                
            updated_count += 1
            
        db.session.commit()
        print(f"✅ 총 {updated_count}개 서비스 옵션에 텍스트 기반 예약 조건 설정 완료")
        
        # 설정된 옵션들 확인
        print("\n📋 설정된 서비스 옵션들:")
        for option in options:
            print(f"  - {option.name} (서비스: {option.service.name})")
            print(f"    예약 방법: {'✅ 설정됨' if option.booking_method else '❌ 미설정'}")
            print(f"    결제 방식: {'✅ 설정됨' if option.payment_info else '❌ 미설정'}")
            print(f"    안내 사항: {'✅ 설정됨' if option.guide_info else '❌ 미설정'}")
            print(f"    환불 규정 텍스트: {'✅ 설정됨' if option.refund_policy_text else '❌ 미설정'}")
            print(f"    환불 규정 테이블: {'✅ 설정됨' if option.refund_policy_table else '❌ 미설정'}")
            print()

if __name__ == '__main__':
    setup_default_booking_conditions() 