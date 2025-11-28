"""
번역된 데이터에서 화폐 단위를 KRW로 통일하는 스크립트
"""
import os
import re
from dotenv import load_dotenv
from pymongo import MongoClient

# .env 파일 로드
load_dotenv()

# MongoDB 연결
mongo_uri = os.environ.get('MONGO_URI')

if not mongo_uri:
    print("❌ MONGO_URI 환경 변수가 설정되지 않았습니다!")
    exit(1)

print(f"MongoDB에 연결 중...")
mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=30000)
mongo_db = mongo_client['STG-DB']
translations_collection = mongo_db['translations']

print("✅ MongoDB 연결 성공!")

# 화폐 단위 패턴 (다양한 언어의 "원" 표현)
currency_patterns = [
    r'원',           # 한국어
    r'ウォン',        # 일본어
    r'円',           # 일본어 (엔 표기)
    r'韓元',          # 중국어
    r'元',           # 중국어 (간체)
    r'won(?:es)?',   # 스페인어/영어 (won/wones) - 단어 경계 없이
    r'KRW',          # 이미 KRW인 경우
]

def replace_currency_in_text(text):
    """
    텍스트에서 화폐 단위를 KRW로 변경
    예: "22,000원" -> "22,000 KRW"
    """
    if not text:
        return text
    
    # 리스트인 경우 각 항목 처리
    if isinstance(text, list):
        return [replace_currency_in_text(item) if isinstance(item, str) else 
                (replace_currency_in_dict(item) if isinstance(item, dict) else item) 
                for item in text]
    
    # 딕셔너리인 경우
    if isinstance(text, dict):
        return replace_currency_in_dict(text)
    
    # 문자열이 아닌 경우 그대로 반환
    if not isinstance(text, str):
        return text
    
    # 숫자 + 화폐단위 패턴 찾기
    # 예: "22,000원", "22,000 ウォン", "22,000 KRW"
    for pattern in currency_patterns:
        # 숫자(콤마 포함) + 공백(선택) + 화폐단위
        regex = r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*' + pattern
        text = re.sub(regex, r'\1 KRW', text)
    
    return text

def replace_currency_in_dict(d):
    """딕셔너리 내의 모든 값에서 화폐 단위 변경"""
    if not isinstance(d, dict):
        return d
    result = {}
    for key, value in d.items():
        if isinstance(value, str):
            result[key] = replace_currency_in_text(value)
        elif isinstance(value, list):
            result[key] = replace_currency_in_text(value)
        elif isinstance(value, dict):
            result[key] = replace_currency_in_dict(value)
        else:
            result[key] = value
    return result

def update_translations():
    """모든 번역 데이터에서 화폐 단위를 KRW로 업데이트"""
    
    # 모든 번역 문서 조회
    all_translations = translations_collection.find({})
    updated_count = 0
    
    for doc in all_translations:
        updated = False
        fields = doc.get('fields', {})
        
        for field_name, field_data in fields.items():
            # 가격 관련 필드만 처리
            if field_name in ['overtime_charge_table', 'refund_policy_table', 'packages', 'price']:
                translations = field_data.get('translations', {})
                
                for lang, translated_text in translations.items():
                    if translated_text:
                        new_text = replace_currency_in_text(translated_text)
                        if new_text != translated_text:
                            translations[lang] = new_text
                            updated = True
                            if isinstance(translated_text, str):
                                print(f"  [{lang}] {translated_text[:50]}... -> {new_text[:50] if isinstance(new_text, str) else str(new_text)[:50]}...")
                            else:
                                print(f"  [{lang}] (리스트/딕셔너리 데이터 업데이트됨)")
                
                # original 필드도 업데이트
                original = field_data.get('original', '')
                if original:
                    new_original = replace_currency_in_text(original)
                    if new_original != original:
                        field_data['original'] = new_original
                        updated = True
        
        if updated:
            # MongoDB 업데이트
            translations_collection.update_one(
                {'_id': doc['_id']},
                {'$set': {'fields': fields}}
            )
            updated_count += 1
            print(f"✅ 업데이트: {doc.get('source_type')}_{doc.get('source_id')}")
    
    return updated_count

if __name__ == '__main__':
    print("\n=== 번역 데이터 화폐 단위 업데이트 ===\n")
    
    # 현재 번역 데이터 확인
    count = translations_collection.count_documents({})
    print(f"총 {count}개의 번역 문서 발견\n")
    
    # 업데이트 실행
    updated = update_translations()
    
    print(f"\n=== 완료: {updated}개의 문서가 업데이트됨 ===\n")

