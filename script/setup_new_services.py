#!/usr/bin/env python3
"""
새로운 2단계 서비스 구성을 위한 데이터 생성 스크립트
"""

import sys
import os
import json

# 현재 스크립트 파일의 부모 디렉토리를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app import create_app
from models import Service, ServiceOption, db

def create_new_services():
    """새로운 서비스 구성 생성"""
    
    # 기존 서비스 및 옵션 모두 삭제
    print("기존 서비스 및 옵션 삭제 중...")
    ServiceOption.query.delete()
    Service.query.delete()
    db.session.commit()
    
    # 새로운 서비스 구성 데이터
    services_data = [
        {
            "name": "STG AI 분석",
            "category": "ai_analysis",
            "description": "AI 기술을 활용한 개인 맞춤 분석 서비스",
            "details": json.dumps([
                "최신 AI 기술로 정확한 분석",
                "개인 특성에 맞춘 맞춤형 결과",
                "과학적 근거 기반 분석",
                "실시간 분석 결과 제공"
            ]),
            "packages": json.dumps([
                {
                    "name": "기본 분석 패키지",
                    "price": "150,000원",
                    "duration": "1시간",
                    "description": "AI 얼굴 분석 + AI 체형 분석"
                }
            ]),
            "options": [
                {
                    "name": "AI 얼굴 분석",
                    "description": "AI 기술을 활용한 얼굴형, 피부톤, 특징 분석",
                    "price": 80000,
                    "duration": "30분"
                },
                {
                    "name": "AI 체형 분석", 
                    "description": "AI 기술을 활용한 체형, 비율, 스타일 분석",
                    "price": 100000,
                    "duration": "40분"
                }
            ]
        },
        {
            "name": "스타일링 컨설팅",
            "category": "consulting",
            "description": "전문 스타일리스트의 1:1 맞춤 컨설팅",
            "details": json.dumps([
                "전문 스타일리스트의 개인 컨설팅",
                "체계적인 분석과 진단",
                "실무 적용 가능한 실습 교육",
                "지속적인 스타일 관리 가이드"
            ]),
            "packages": json.dumps([
                {
                    "name": "컨설팅 풀 패키지",
                    "price": "400,000원",
                    "duration": "4시간",
                    "description": "퍼스널 컬러 + 메이크업 + 헤어 + 패션 컨설팅"
                },
                {
                    "name": "기본 컨설팅",
                    "price": "200,000원", 
                    "duration": "2시간",
                    "description": "퍼스널 컬러 + 메이크업 레슨"
                }
            ]),
            "options": [
                {
                    "name": "퍼스널 컬러 진단",
                    "description": "개인에게 가장 잘 어울리는 컬러 진단 및 활용법",
                    "price": 120000,
                    "duration": "1시간"
                },
                {
                    "name": "메이크업 레슨",
                    "description": "개인 특성에 맞는 메이크업 기법 교육",
                    "price": 150000,
                    "duration": "1.5시간"
                },
                {
                    "name": "헤어 스타일링 레슨",
                    "description": "얼굴형에 맞는 헤어 스타일링 교육",
                    "price": 120000,
                    "duration": "1시간"
                },
                {
                    "name": "패션 스타일링 레슨",
                    "description": "체형과 개성에 맞는 패션 스타일링 교육",
                    "price": 180000,
                    "duration": "2시간"
                }
            ]
        },
        {
            "name": "원데이 스타일링",
            "category": "oneday",
            "description": "특별한 날을 위한 원데이 토탈 스타일링",
            "details": json.dumps([
                "특별한 날을 위한 완벽한 스타일링",
                "전문 메이크업 & 헤어 스타일링",
                "개인 맞춤 패션 코디네이션",
                "당일 완성되는 토탈 케어"
            ]),
            "packages": json.dumps([
                {
                    "name": "토탈 스타일링 패키지",
                    "price": "350,000원",
                    "duration": "3시간",
                    "description": "메이크업 + 헤어 + 패션 스타일링"
                },
                {
                    "name": "메이크업 & 헤어 패키지",
                    "price": "200,000원",
                    "duration": "2시간",
                    "description": "메이크업 + 헤어 드라이"
                }
            ]),
            "options": [
                {
                    "name": "메이크업",
                    "description": "특별한 날을 위한 완벽한 메이크업",
                    "price": 120000,
                    "duration": "1시간"
                },
                {
                    "name": "헤어 드라이",
                    "description": "스타일에 맞는 헤어 세팅",
                    "price": 100000,
                    "duration": "1시간"
                },
                {
                    "name": "패션 스타일링",
                    "description": "목적에 맞는 패션 코디네이션",
                    "price": 150000,
                    "duration": "1.5시간"
                }
            ]
        },
        {
            "name": "화보 & 프로필",
            "category": "photo",
            "description": "전문적인 화보 및 프로필 촬영 서비스",
            "details": json.dumps([
                "전문 사진작가와 함께하는 촬영",
                "촬영 전 완벽한 스타일링",
                "다양한 컨셉의 화보 진행",
                "고품질 보정 서비스 포함"
            ]),
            "packages": json.dumps([
                {
                    "name": "화보 + 프로필 패키지",
                    "price": "800,000원",
                    "duration": "4시간",
                    "description": "개인화보 + 프로필 촬영 + 스타일링"
                },
                {
                    "name": "프로필 촬영",
                    "price": "300,000원",
                    "duration": "2시간",
                    "description": "프로필 촬영 + 기본 스타일링"
                }
            ]),
            "options": [
                {
                    "name": "개인화보",
                    "description": "개인의 매력을 담은 화보 촬영",
                    "price": 500000,
                    "duration": "3시간"
                },
                {
                    "name": "프로필",
                    "description": "비즈니스 및 개인용 프로필 촬영",
                    "price": 250000,
                    "duration": "1.5시간"
                }
            ]
        }
    ]
    
    print("새로운 서비스 생성 중...")
    
    for service_data in services_data:
        # 서비스 생성
        service = Service(
            name=service_data["name"],
            category=service_data["category"],
            description=service_data["description"],
            details=service_data["details"],
            packages=service_data["packages"]
        )
        db.session.add(service)
        db.session.flush()  # ID 할당을 위해 flush
        
        # 서비스 옵션 생성
        for option_data in service_data["options"]:
            option = ServiceOption(
                service_id=service.id,
                name=option_data["name"],
                description=option_data["description"]
            )
            db.session.add(option)
        
        print(f"✓ {service_data['name']} 서비스 생성 완료")
    
    db.session.commit()
    print("\n새로운 서비스 구성 생성 완료!")
    
    # 생성된 서비스 확인
    services = Service.query.all()
    print(f"\n총 {len(services)}개의 서비스가 생성되었습니다:")
    for service in services:
        options_count = len(service.options)
        print(f"- {service.name} ({options_count}개 옵션)")

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        create_new_services() 