#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import create_app
from models import ServiceOption, db

def setup_overtime_charge_data():
    """모든 ServiceOption에 기본 시간외 업차지 데이터 설정"""
    
    # 기본 시간외 업차지 데이터 (time_slots.csv 기준)
    default_overtime_charge_data = [
        "오전 9시 이전 예약|22,000원|AM 8:00~8:59",
        "오전 8시 이전 예약|33,000원|AM 7:00~7:59",
        "오전 7시 이전 예약|44,000원|AM 6:00~6:59",
        "오전 6시 이전 예약|55,000원|AM 5:00~5:59",
        "오후 6시 이후 예약|22,000원|PM 6:00~6:59",
        "오후 7시 이후 예약|33,000원|PM 7:00~7:59",
        "오후 8시 이후 예약|44,000원|PM 8:00~8:59"
    ]
    
    overtime_charge_table_text = '\n'.join(default_overtime_charge_data)
    
    app = create_app()
    with app.app_context():
        try:
            # 모든 ServiceOption 가져오기
            options = ServiceOption.query.all()
            
            print(f"총 {len(options)}개의 서비스 옵션을 업데이트합니다...")
            
            updated_count = 0
            for option in options:
                # 모든 서비스 옵션의 시간외 업차지 데이터를 새로운 CSV 데이터로 업데이트
                old_data = option.overtime_charge_table
                option.overtime_charge_table = overtime_charge_table_text
                updated_count += 1
                
                if old_data and old_data.strip():
                    print(f"  - 옵션 ID {option.id} ({option.name}) 기존 데이터 교체 완료")
                else:
                    print(f"  - 옵션 ID {option.id} ({option.name}) 새 데이터 설정 완료")
            
            # 변경사항 저장
            db.session.commit()
            print(f"\n✅ 성공적으로 {updated_count}개의 서비스 옵션에 시간외 업차지 데이터를 업데이트했습니다!")
            
            # 설정된 데이터 출력
            print("\n📋 새로 설정된 시간외 업차지 데이터 (time_slots.csv 기준):")
            for i, data in enumerate(default_overtime_charge_data, 1):
                parts = data.split('|')
                print(f"  {i}. {parts[0]} → {parts[1]} ({parts[2]})")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            db.session.rollback()

if __name__ == "__main__":
    setup_overtime_charge_data() 