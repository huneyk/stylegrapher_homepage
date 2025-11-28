"""
SQLite 데이터베이스의 원본 데이터에서 화폐 단위를 KRW로 통일하는 스크립트
"""
import os
import re
import sys

# Flask 앱 경로 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from models import ServiceOption

# Flask 앱 생성
app = create_app()

# 화폐 단위 패턴 (다양한 언어의 "원" 표현)
currency_patterns = [
    r'원',           # 한국어
    r'ウォン',        # 일본어
    r'円',           # 일본어 (엔 표기)
    r'韓元',          # 중국어
    r'元',           # 중국어 (간체)
    r'wones?',       # 스페인어 (won/wones)
]

def replace_currency_in_text(text):
    """텍스트에서 화폐 단위를 KRW로 변경"""
    if not text:
        return text
    
    for pattern in currency_patterns:
        # 숫자(콤마 포함) + 공백(선택) + 화폐단위
        regex = r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*' + pattern
        text = re.sub(regex, r'\1 KRW', text)
    
    return text

def update_service_options():
    """모든 ServiceOption의 가격 관련 필드 업데이트"""
    
    with app.app_context():
        options = ServiceOption.query.all()
        updated_count = 0
        
        for option in options:
            updated = False
            
            # overtime_charge_table 업데이트
            if option.overtime_charge_table:
                new_value = replace_currency_in_text(option.overtime_charge_table)
                if new_value != option.overtime_charge_table:
                    print(f"  [overtime_charge_table] {option.name}:")
                    print(f"    Before: {option.overtime_charge_table[:80]}...")
                    print(f"    After:  {new_value[:80]}...")
                    option.overtime_charge_table = new_value
                    updated = True
            
            # refund_policy_table 업데이트
            if option.refund_policy_table:
                new_value = replace_currency_in_text(option.refund_policy_table)
                if new_value != option.refund_policy_table:
                    print(f"  [refund_policy_table] {option.name}:")
                    print(f"    Before: {option.refund_policy_table[:80]}...")
                    print(f"    After:  {new_value[:80]}...")
                    option.refund_policy_table = new_value
                    updated = True
            
            # packages 업데이트 (JSON 형식)
            if option.packages:
                new_value = replace_currency_in_text(option.packages)
                if new_value != option.packages:
                    print(f"  [packages] {option.name}:")
                    print(f"    Before: {option.packages[:80]}...")
                    print(f"    After:  {new_value[:80]}...")
                    option.packages = new_value
                    updated = True
            
            if updated:
                updated_count += 1
        
        # 변경사항 저장
        if updated_count > 0:
            db.session.commit()
            print(f"\n✅ {updated_count}개의 서비스 옵션이 업데이트됨")
        else:
            print("\n변경할 데이터가 없습니다.")
        
        return updated_count

if __name__ == '__main__':
    print("\n=== SQLite 데이터베이스 화폐 단위 업데이트 ===\n")
    updated = update_service_options()
    print(f"\n=== 완료 ===\n")

