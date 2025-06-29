#!/usr/bin/env python3
"""
현재 구축된 서비스 옵션들에 대해 상세 페이지 정보를 설정하는 스크립트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import ServiceOption
import json

def setup_service_option_details():
    app = create_app()
    
    with app.app_context():
        print("서비스 옵션 상세 정보 설정 시작...")
        
        # 개인화보 설정
        personal_photo = ServiceOption.query.filter_by(name='개인화보').first()
        if personal_photo:
            personal_photo.has_detail_page = True
            personal_photo.detailed_description = "셀럽을 전담하는 팀이 일반 고객님들께 셀럽과 동일한 토탈 스타일링 서비스로 셀럽의 화보 같은 사진을 남겨드립니다."
            
            details = [
                "전문 포토그래퍼의 1:1 촬영",
                "헤어메이크업 서비스 포함", 
                "온라인 갤러리 제공",
                "고해상도 원본 파일 제공"
            ]
            personal_photo.details = json.dumps(details, ensure_ascii=False)
            
            packages = [
                {
                    "name": "개인화보 1컨셉",
                    "description": "소요시간 3시간, 원본, 고해상 보정본 2컷",
                    "price": "2,200,000 원"
                },
                {
                    "name": "개인화보 2컨셉", 
                    "description": "소요시간 5시간, 원본, 고해상 보정본 4컷",
                    "price": "2,750,000 원"
                },
                {
                    "name": "개인화보 3컨셉",
                    "description": "소요시간 7시간, 원본, 고해상 보정본 6컷", 
                    "price": "3,300,000 원"
                },
                {
                    "name": "개인화보 4컨셉",
                    "description": "소요시간 9시간, 원본, 고해상 보정본 8컷",
                    "price": "3,850,000 원"
                },
                {
                    "name": "커플 화보 1컨셉",
                    "description": "소요시간 5시간, 원본, 고해상 보정본 5컷",
                    "price": "4,400,000 원"
                },
                {
                    "name": "커플 화보 2컨셉",
                    "description": "소요시간 8시간, 원본, 고해상 보정본 10컷",
                    "price": "6,050,000 원"
                }
            ]
            personal_photo.packages = json.dumps(packages, ensure_ascii=False)
            print("✓ 개인화보 상세 정보 설정 완료")
        
        # 프로필 설정
        profile = ServiceOption.query.filter_by(name='프로필').first()
        if profile:
            profile.has_detail_page = True
            profile.detailed_description = "스타일그래퍼와 강성으로 메이크업, 헤어 스타일링 후 남겨드리는 high quality 프로필 촬영 서비스입니다."
            
            details = [
                "프로필 전문 촬영",
                "프로페셔널 메이크업 및 헤어 스타일링",
                "다양한 컨셉 촬영 가능",
                "비즈니스 프로필 최적화"
            ]
            profile.details = json.dumps(details, ensure_ascii=False)
            
            packages = [
                {
                    "name": "기본 프로필",
                    "description": "소요시간 2시간, 메이크업 + 헤어 + 촬영, 보정본 3컷",
                    "price": "1,500,000 원"
                },
                {
                    "name": "프리미엄 프로필",
                    "description": "소요시간 3시간, 메이크업 + 헤어 + 촬영, 보정본 5컷",
                    "price": "2,000,000 원"
                }
            ]
            profile.packages = json.dumps(packages, ensure_ascii=False)
            print("✓ 프로필 상세 정보 설정 완료")
        
        # 퍼스널 컬러 진단 설정
        personal_color = ServiceOption.query.filter_by(name='퍼스널 컬러 진단').first()
        if personal_color:
            personal_color.has_detail_page = True
            personal_color.detailed_description = "색의 체계를 주는 천년의 아니, 어떨 게 될 더 맞는 색을 활용할 수 있는가를 퍼스널 컬러 진단입니다."
            
            details = [
                "전문적인 퍼스널 컬러 분석",
                "개인 맞춤 컬러 팔레트 제공",
                "메이크업 컬러 추천",
                "패션 컬러 코디네이션 가이드"
            ]
            personal_color.details = json.dumps(details, ensure_ascii=False)
            
            packages = [
                {
                    "name": "기본 퍼스널 컬러 진단",
                    "description": "소요시간 1시간, 컬러 분석 + 팔레트 제공",
                    "price": "150,000 원"
                },
                {
                    "name": "종합 퍼스널 컬러 진단",
                    "description": "소요시간 2시간, 컬러 분석 + 메이크업 + 스타일링 가이드",
                    "price": "250,000 원"
                }
            ]
            personal_color.packages = json.dumps(packages, ensure_ascii=False)
            print("✓ 퍼스널 컬러 진단 상세 정보 설정 완료")
        
        # 메이크업 레슨 설정
        makeup_lesson = ServiceOption.query.filter_by(name='메이크업 레슨').first()
        if makeup_lesson:
            makeup_lesson.has_detail_page = True
            makeup_lesson.detailed_description = "나만의 아름다움을 비는 메이크업 방법을 배우는 시간입니다. 나에게 적한한 베이스 방법부터 나에게 어울리는 눈썹, 아이라인, 색조까지 모든 앞딘다."
            
            details = [
                "개인 맞춤 메이크업 기법 교육",
                "기초부터 고급 테크닉까지",
                "제품 선택 및 활용법 안내",
                "실습 위주의 체계적 학습"
            ]
            makeup_lesson.details = json.dumps(details, ensure_ascii=False)
            
            packages = [
                {
                    "name": "기초 메이크업 레슨",
                    "description": "소요시간 2시간, 베이스 메이크업 + 기본 포인트 메이크업",
                    "price": "200,000 원"
                },
                {
                    "name": "종합 메이크업 레슨",
                    "description": "소요시간 3시간, 전체 메이크업 + 개인 스타일 분석",
                    "price": "300,000 원"
                }
            ]
            makeup_lesson.packages = json.dumps(packages, ensure_ascii=False)
            print("✓ 메이크업 레슨 상세 정보 설정 완료")
        
        # 변경사항 저장
        db.session.commit()
        print("\n✅ 모든 서비스 옵션 상세 정보 설정이 완료되었습니다!")
        
        # 설정된 서비스 옵션 확인
        detailed_options = ServiceOption.query.filter_by(has_detail_page=True).all()
        print(f"\n📋 상세 페이지가 있는 서비스 옵션: {len(detailed_options)}개")
        for option in detailed_options:
            print(f"  - {option.name} (ID: {option.id})")

if __name__ == "__main__":
    setup_service_option_details() 
 