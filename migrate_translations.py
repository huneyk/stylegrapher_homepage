#!/usr/bin/env python3
"""
다국어 번역 마이그레이션 스크립트

SQLite에 저장된 모든 텍스트 데이터를 GPT로 번역하여 MongoDB에 저장합니다.

사용법:
    python migrate_translations.py

환경 변수 필요:
    - OPENAI_API_KEY: OpenAI API 키
    - MONGO_URI: MongoDB 연결 URI
"""

import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

def main():
    """메인 함수"""
    
    # 환경 변수 확인
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 OPENAI_API_KEY=your-api-key 를 추가해주세요.")
        return False
    
    if not os.environ.get('MONGO_URI'):
        print("❌ MONGO_URI 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 MONGO_URI=your-mongodb-uri 를 추가해주세요.")
        return False
    
    print("✅ 환경 변수 확인 완료")
    
    # 번역 마이그레이션 실행
    from utils.translation import migrate_all_translations
    migrate_all_translations()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

