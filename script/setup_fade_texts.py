#!/usr/bin/env python3
"""
기본 Fade Text 데이터를 데이터베이스에 추가하는 스크립트
"""

import sys
import os

# 현재 스크립트의 상위 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db
from models import CollageText

def setup_default_fade_texts():
    """기본 Fade Text 데이터를 설정합니다."""
    
    app = create_app()
    
    with app.app_context():
        try:
            # 기존 fade text 데이터 확인
            existing_texts = CollageText.query.count()
            
            if existing_texts > 0:
                print(f"이미 {existing_texts}개의 Fade Text가 존재합니다.")
                user_input = input("기존 데이터를 모두 삭제하고 새로 만드시겠습니까? (y/N): ")
                if user_input.lower() != 'y':
                    print("작업을 취소했습니다.")
                    return
                
                # 기존 데이터 삭제
                CollageText.query.delete()
                print("기존 Fade Text 데이터를 삭제했습니다.")
            
            # 기본 Fade Text 데이터 생성
            default_texts = [
                {"text": "스타일그래퍼와 함께", "order": 1},
                {"text": "나를 찾아가는 여정", "order": 2}
            ]
            
            for text_data in default_texts:
                fade_text = CollageText(
                    text=text_data["text"],
                    order=text_data["order"]
                )
                db.session.add(fade_text)
            
            # 변경사항 저장
            db.session.commit()
            
            print(f"✅ {len(default_texts)}개의 기본 Fade Text를 성공적으로 생성했습니다:")
            for text_data in default_texts:
                print(f"   - {text_data['text']} (순서: {text_data['order']})")
            
            print("\n📝 Admin 패널에서 추가 텍스트를 관리할 수 있습니다:")
            print("   http://localhost:5001/admin/fade-texts")
            
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            db.session.rollback()
            return False
            
    return True

if __name__ == "__main__":
    print("🚀 Fade Text 기본 데이터 설정을 시작합니다...")
    print("-" * 50)
    
    success = setup_default_fade_texts()
    
    if success:
        print("-" * 50)
        print("✅ 설정이 완료되었습니다!")
    else:
        print("-" * 50)
        print("❌ 설정 중 오류가 발생했습니다.")
        sys.exit(1) 