"""
다국어 번역 시스템 유틸리티

MongoDB에 번역된 텍스트를 저장하고 관리하는 모듈
OpenAI GPT API를 사용하여 자동 번역 지원
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from pymongo import MongoClient
from dotenv import load_dotenv
from openai import OpenAI

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
_openai_client = None

def get_openai_client():
    """OpenAI 클라이언트 싱글톤 반환"""
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if api_key:
            _openai_client = OpenAI(api_key=api_key)
    return _openai_client

# 지원하는 언어 목록
SUPPORTED_LANGUAGES = {
    'ko': '한국어',
    'en': 'English',
    'ja': '日本語',
    'zh': '中文',
    'es': 'Español'
}

# 언어별 전체 이름 (GPT 프롬프트용)
LANGUAGE_NAMES = {
    'ko': 'Korean',
    'en': 'English',
    'ja': 'Japanese',
    'zh': 'Chinese (Simplified)',
    'es': 'Spanish'
}

# MongoDB 연결
mongo_uri = os.environ.get('MONGO_URI')
mongo_client = None
mongo_db = None
translations_collection = None


def init_mongodb():
    """MongoDB 연결 초기화"""
    global mongo_client, mongo_db, translations_collection
    
    if not mongo_uri:
        print("⚠️ MONGO_URI 환경 변수가 설정되지 않았습니다!")
        return False
    
    try:
        mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
            retryWrites=True,
            retryReads=True,
            w='majority',
            readPreference='primaryPreferred'
        )
        mongo_client.server_info()
        mongo_db = mongo_client['STG-DB']
        translations_collection = mongo_db['translations']
        
        # 인덱스 생성
        translations_collection.create_index([("source_type", 1), ("source_id", 1)], unique=True)
        translations_collection.create_index("updated_at")
        
        print("✅ 번역 시스템 MongoDB 연결 성공!")
        return True
    except Exception as e:
        print(f"❌ 번역 시스템 MongoDB 연결 실패: {str(e)}")
        return False


# 초기 연결
init_mongodb()


def translate_text_gpt(text: str, target_lang: str, source_lang: str = 'ko') -> Optional[str]:
    """
    OpenAI GPT API를 사용하여 텍스트 번역
    
    Args:
        text: 번역할 텍스트
        target_lang: 대상 언어 코드 (en, ja, zh, es)
        source_lang: 원본 언어 코드 (기본값: ko)
    
    Returns:
        번역된 텍스트 또는 None (실패 시)
    """
    if not text or not text.strip():
        return text
    
    if target_lang == source_lang:
        return text
    
    client = get_openai_client()
    if not client:
        print("⚠️ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다!")
        return None
    
    try:
        source_name = LANGUAGE_NAMES.get(source_lang, 'Korean')
        target_name = LANGUAGE_NAMES.get(target_lang, 'English')
        
        # GPT-4o-mini 모델 사용 (비용 효율적)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional translator specializing in beauty, fashion, and styling services.
Translate the following text from {source_name} to {target_name}.
Keep the original formatting, line breaks, and special characters.
For brand names, technical terms, or proper nouns that should remain in the original language, keep them as is.
Maintain a professional yet friendly tone suitable for a premium styling service website.
Only return the translated text without any explanations or notes."""
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=4096
        )
        
        translated_text = response.choices[0].message.content.strip()
        return translated_text
        
    except Exception as e:
        print(f"❌ GPT 번역 오류: {str(e)}")
        return None


def translate_batch_gpt(texts: List[str], target_lang: str, source_lang: str = 'ko') -> List[str]:
    """
    여러 텍스트를 한 번에 번역 (API 호출 최적화)
    
    Args:
        texts: 번역할 텍스트 리스트
        target_lang: 대상 언어 코드
        source_lang: 원본 언어 코드
    
    Returns:
        번역된 텍스트 리스트
    """
    if not texts:
        return texts
    
    if target_lang == source_lang:
        return texts
    
    client = get_openai_client()
    if not client:
        print("⚠️ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다!")
        return texts
    
    try:
        source_name = LANGUAGE_NAMES.get(source_lang, 'Korean')
        target_name = LANGUAGE_NAMES.get(target_lang, 'English')
        
        # 텍스트를 JSON 배열로 전달
        texts_json = json.dumps(texts, ensure_ascii=False)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional translator specializing in beauty, fashion, and styling services.
Translate the following JSON array of texts from {source_name} to {target_name}.
Keep the original formatting and special characters within each text.
Return ONLY a JSON array with the translated texts in the same order.
Maintain a professional yet friendly tone suitable for a premium styling service website."""
                },
                {
                    "role": "user",
                    "content": texts_json
                }
            ],
            temperature=0.3,
            max_tokens=4096
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 파싱
        try:
            # 코드 블록 제거
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            
            translated_texts = json.loads(result_text)
            if isinstance(translated_texts, list) and len(translated_texts) == len(texts):
                return translated_texts
        except json.JSONDecodeError:
            pass
        
        # JSON 파싱 실패 시 개별 번역
        return [translate_text_gpt(t, target_lang, source_lang) or t for t in texts]
        
    except Exception as e:
        print(f"❌ GPT 배치 번역 오류: {str(e)}")
        return texts


def translate_to_all_languages(text: str, source_lang: str = 'ko') -> Dict[str, str]:
    """
    텍스트를 모든 지원 언어로 번역
    
    Args:
        text: 번역할 텍스트
        source_lang: 원본 언어 코드
    
    Returns:
        언어 코드별 번역된 텍스트 딕셔너리
    """
    translations = {source_lang: text}
    
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code != source_lang:
            translated = translate_text_gpt(text, lang_code, source_lang)
            translations[lang_code] = translated if translated else text
    
    return translations


def translate_to_all_languages_batch(texts: List[str], source_lang: str = 'ko') -> Dict[str, List[str]]:
    """
    여러 텍스트를 모든 지원 언어로 번역 (배치 처리)
    
    Args:
        texts: 번역할 텍스트 리스트
        source_lang: 원본 언어 코드
    
    Returns:
        언어 코드별 번역된 텍스트 리스트 딕셔너리
    """
    translations = {source_lang: texts}
    
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code != source_lang:
            translations[lang_code] = translate_batch_gpt(texts, lang_code, source_lang)
    
    return translations


def save_translation(source_type: str, source_id: int, field_name: str, 
                    original_text: str, translations: Dict[str, str] = None) -> bool:
    """
    번역된 텍스트를 MongoDB에 저장
    
    Args:
        source_type: 데이터 타입 (service, service_option, collage_text 등)
        source_id: 원본 데이터의 ID
        field_name: 필드명 (name, description 등)
        original_text: 원본 텍스트 (한국어)
        translations: 번역된 텍스트 딕셔너리 (없으면 자동 번역)
    
    Returns:
        성공 여부
    """
    if translations_collection is None:
        if not init_mongodb():
            return False
    
    try:
        # 자동 번역이 필요한 경우
        if translations is None:
            translations = translate_to_all_languages(original_text)
        
        # 문서 키 생성
        doc_key = f"{source_type}_{source_id}"
        
        # 기존 문서 조회
        existing = translations_collection.find_one({"_id": doc_key})
        
        if existing:
            # 기존 문서 업데이트
            update_data = {
                f"fields.{field_name}": {
                    "original": original_text,
                    "translations": translations,
                    "updated_at": datetime.utcnow()
                },
                "updated_at": datetime.utcnow()
            }
            translations_collection.update_one(
                {"_id": doc_key},
                {"$set": update_data}
            )
        else:
            # 새 문서 생성
            new_doc = {
                "_id": doc_key,
                "source_type": source_type,
                "source_id": source_id,
                "fields": {
                    field_name: {
                        "original": original_text,
                        "translations": translations,
                        "updated_at": datetime.utcnow()
                    }
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            translations_collection.insert_one(new_doc)
        
        print(f"✅ 번역 저장 완료: {source_type}_{source_id}.{field_name}")
        return True
        
    except Exception as e:
        print(f"❌ 번역 저장 오류: {str(e)}")
        return False


def get_translation(source_type: str, source_id: int, field_name: str, 
                   lang: str = 'ko') -> Optional[str]:
    """
    MongoDB에서 번역된 텍스트 조회
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
        field_name: 필드명
        lang: 조회할 언어 코드
    
    Returns:
        번역된 텍스트 또는 None
    """
    if translations_collection is None:
        if not init_mongodb():
            return None
    
    try:
        doc_key = f"{source_type}_{source_id}"
        doc = translations_collection.find_one({"_id": doc_key})
        
        if doc and "fields" in doc and field_name in doc["fields"]:
            field_data = doc["fields"][field_name]
            
            # 원본 언어인 경우
            if lang == 'ko':
                return field_data.get("original")
            
            # 번역된 언어인 경우
            translations = field_data.get("translations", {})
            return translations.get(lang, field_data.get("original"))
        
        return None
        
    except Exception as e:
        print(f"❌ 번역 조회 오류: {str(e)}")
        return None


def get_all_translations(source_type: str, source_id: int) -> Optional[Dict]:
    """
    특정 데이터의 모든 번역 조회
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
    
    Returns:
        모든 필드의 번역 데이터
    """
    if translations_collection is None:
        if not init_mongodb():
            return None
    
    try:
        doc_key = f"{source_type}_{source_id}"
        doc = translations_collection.find_one({"_id": doc_key})
        
        if doc:
            return doc.get("fields", {})
        
        return None
        
    except Exception as e:
        print(f"❌ 번역 조회 오류: {str(e)}")
        return None


def get_translated_object(source_type: str, source_id: int, lang: str = 'ko') -> Optional[Dict]:
    """
    특정 언어로 번역된 전체 객체 조회
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
        lang: 조회할 언어 코드
    
    Returns:
        번역된 필드 값들의 딕셔너리
    """
    all_translations = get_all_translations(source_type, source_id)
    
    if not all_translations:
        return None
    
    result = {}
    for field_name, field_data in all_translations.items():
        if lang == 'ko':
            result[field_name] = field_data.get("original")
        else:
            translations = field_data.get("translations", {})
            result[field_name] = translations.get(lang, field_data.get("original"))
    
    return result


def delete_translation(source_type: str, source_id: int) -> bool:
    """
    번역 데이터 삭제
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
    
    Returns:
        성공 여부
    """
    if translations_collection is None:
        if not init_mongodb():
            return False
    
    try:
        doc_key = f"{source_type}_{source_id}"
        result = translations_collection.delete_one({"_id": doc_key})
        
        if result.deleted_count > 0:
            print(f"✅ 번역 삭제 완료: {doc_key}")
            return True
        return False
        
    except Exception as e:
        print(f"❌ 번역 삭제 오류: {str(e)}")
        return False


def translate_service(service) -> bool:
    """
    Service 모델의 모든 텍스트 필드 번역 및 저장
    
    Args:
        service: Service 모델 객체
    
    Returns:
        성공 여부
    """
    fields_to_translate = ['name', 'description', 'category']
    success = True
    
    for field in fields_to_translate:
        value = getattr(service, field, None)
        if value and isinstance(value, str) and value.strip():
            if not save_translation('service', service.id, field, value):
                success = False
    
    # details (JSON 배열)
    if service.details:
        try:
            details_list = json.loads(service.details)
            if isinstance(details_list, list) and details_list:
                all_translations = translate_to_all_languages_batch(details_list)
                save_translation('service', service.id, 'details', 
                               service.details, all_translations)
        except json.JSONDecodeError:
            pass
    
    # packages (JSON 배열)
    if service.packages:
        try:
            packages_list = json.loads(service.packages)
            if isinstance(packages_list, list) and packages_list:
                translated_packages = translate_packages(packages_list)
                save_translation('service', service.id, 'packages', 
                               service.packages, translated_packages)
        except json.JSONDecodeError:
            pass
    
    return success


def translate_packages(packages_list: List[Dict]) -> Dict[str, List[Dict]]:
    """
    패키지 리스트 번역 (모든 문자열 필드)
    
    Args:
        packages_list: 패키지 정보 리스트
    
    Returns:
        언어별 번역된 패키지 리스트
    """
    result = {'ko': packages_list}
    
    # 모든 문자열 값 추출
    all_strings = []
    string_map = []  # (pkg_idx, key) 매핑
    
    for pkg_idx, pkg in enumerate(packages_list):
        for key, value in pkg.items():
            if isinstance(value, str) and value.strip():
                all_strings.append(value)
                string_map.append((pkg_idx, key))
    
    if not all_strings:
        return result
    
    # 각 언어로 번역
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code == 'ko':
            continue
        
        translated_strings = translate_batch_gpt(all_strings, lang_code)
        
        # 번역된 문자열을 패키지 구조에 다시 매핑
        translated_packages = []
        for pkg in packages_list:
            translated_pkg = pkg.copy()
            translated_packages.append(translated_pkg)
        
        for idx, (pkg_idx, key) in enumerate(string_map):
            if idx < len(translated_strings):
                translated_packages[pkg_idx][key] = translated_strings[idx]
        
        result[lang_code] = translated_packages
    
    return result


def translate_service_option(option) -> bool:
    """
    ServiceOption 모델의 모든 텍스트 필드 번역 및 저장
    
    Args:
        option: ServiceOption 모델 객체
    
    Returns:
        성공 여부
    """
    fields_to_translate = [
        'name', 'description', 'detailed_description',
        'booking_method', 'payment_info', 'guide_info',
        'refund_policy', 'refund_policy_text'
    ]
    success = True
    
    for field in fields_to_translate:
        value = getattr(option, field, None)
        if value and isinstance(value, str) and value.strip():
            if not save_translation('service_option', option.id, field, value):
                success = False
    
    # details (JSON 배열)
    if option.details:
        try:
            details_list = json.loads(option.details)
            if isinstance(details_list, list) and details_list:
                all_translations = translate_to_all_languages_batch(details_list)
                save_translation('service_option', option.id, 'details', 
                               option.details, all_translations)
        except json.JSONDecodeError:
            pass
    
    # packages (JSON 배열)
    if option.packages:
        try:
            packages_list = json.loads(option.packages)
            if isinstance(packages_list, list) and packages_list:
                translated_packages = translate_packages(packages_list)
                save_translation('service_option', option.id, 'packages', 
                               option.packages, translated_packages)
        except json.JSONDecodeError:
            pass
    
    # refund_policy_table (파이프 구분 텍스트)
    if option.refund_policy_table and option.refund_policy_table.strip():
        translated_table = translate_pipe_separated_table(option.refund_policy_table)
        save_translation('service_option', option.id, 'refund_policy_table', 
                       option.refund_policy_table, translated_table)
    
    # overtime_charge_table (파이프 구분 텍스트)
    if option.overtime_charge_table and option.overtime_charge_table.strip():
        translated_table = translate_pipe_separated_table(option.overtime_charge_table)
        save_translation('service_option', option.id, 'overtime_charge_table', 
                       option.overtime_charge_table, translated_table)
    
    return success


def translate_pipe_separated_table(table_text: str) -> Dict[str, str]:
    """
    파이프(|)로 구분된 테이블 텍스트를 모든 지원 언어로 번역
    
    Args:
        table_text: 파이프로 구분된 테이블 텍스트 (예: "촬영일 30일 전|100%|전액환불")
    
    Returns:
        언어별 번역된 테이블 텍스트
    """
    result = {'ko': table_text}
    
    if not table_text or not table_text.strip():
        return result
    
    # 각 행을 파싱
    lines = table_text.strip().split('\n')
    all_cells = []
    cell_map = []  # (line_idx, cell_idx) 매핑
    
    for line_idx, line in enumerate(lines):
        if '|' in line:
            parts = line.split('|')
            for cell_idx, part in enumerate(parts):
                cell = part.strip()
                if cell:
                    all_cells.append(cell)
                    cell_map.append((line_idx, cell_idx, len(parts)))
    
    if not all_cells:
        return result
    
    # 각 언어로 번역
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code == 'ko':
            continue
        
        translated_cells = translate_batch_gpt(all_cells, lang_code)
        
        # 번역된 셀을 다시 테이블 구조로 조립
        translated_lines = lines.copy()
        cell_idx = 0
        
        for orig_line_idx, orig_cell_idx, num_parts in cell_map:
            if cell_idx < len(translated_cells):
                # 해당 라인을 파싱하여 셀 교체
                orig_parts = translated_lines[orig_line_idx].split('|')
                if orig_cell_idx < len(orig_parts):
                    orig_parts[orig_cell_idx] = translated_cells[cell_idx]
                    translated_lines[orig_line_idx] = '|'.join(orig_parts)
            cell_idx += 1
        
        result[lang_code] = '\n'.join(translated_lines)
    
    return result


def translate_json_to_all_languages(data: Any) -> Dict[str, Any]:
    """
    JSON 데이터를 모든 지원 언어로 번역
    
    Args:
        data: JSON 데이터
    
    Returns:
        언어별 번역된 JSON 데이터
    """
    result = {'ko': data}
    
    # 모든 문자열 추출
    all_strings = []
    string_paths = []
    
    def extract_strings(obj, path=""):
        if isinstance(obj, str) and obj.strip():
            all_strings.append(obj)
            string_paths.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                extract_strings(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                extract_strings(item, f"{path}[{i}]")
    
    extract_strings(data)
    
    if not all_strings:
        return result
    
    # 각 언어로 번역
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code == 'ko':
            continue
        
        translated_strings = translate_batch_gpt(all_strings, lang_code)
        
        # 번역된 문자열을 JSON 구조에 다시 매핑
        import copy
        translated_data = copy.deepcopy(data)
        
        def set_value_at_path(obj, path, value):
            parts = []
            current = ""
            i = 0
            while i < len(path):
                if path[i] == '.':
                    if current:
                        parts.append(current)
                        current = ""
                elif path[i] == '[':
                    if current:
                        parts.append(current)
                        current = ""
                    j = i + 1
                    while j < len(path) and path[j] != ']':
                        j += 1
                    parts.append(int(path[i+1:j]))
                    i = j
                else:
                    current += path[i]
                i += 1
            if current:
                parts.append(current)
            
            target = obj
            for p in parts[:-1]:
                target = target[p]
            target[parts[-1]] = value
        
        for idx, path in enumerate(string_paths):
            if idx < len(translated_strings):
                try:
                    set_value_at_path(translated_data, path, translated_strings[idx])
                except (KeyError, IndexError, TypeError):
                    pass
        
        result[lang_code] = translated_data
    
    return result


def translate_collage_text(collage_text) -> bool:
    """
    CollageText 모델의 텍스트 필드 번역 및 저장
    
    Args:
        collage_text: CollageText 모델 객체
    
    Returns:
        성공 여부
    """
    if collage_text.text and collage_text.text.strip():
        return save_translation('collage_text', collage_text.id, 'text', collage_text.text)
    return True


def translate_gallery_group(gallery_group) -> bool:
    """
    GalleryGroup 모델의 텍스트 필드 번역 및 저장
    
    Args:
        gallery_group: GalleryGroup 모델 객체
    
    Returns:
        성공 여부
    """
    if gallery_group.title and gallery_group.title.strip():
        return save_translation('gallery_group', gallery_group.id, 'title', gallery_group.title)
    return True


def translate_terms_of_service(terms) -> bool:
    """
    TermsOfService 모델의 content 필드 번역 및 저장
    
    Args:
        terms: TermsOfService 모델 객체
    
    Returns:
        성공 여부
    """
    if terms.content and terms.content.strip():
        return save_translation('terms_of_service', terms.id, 'content', terms.content)
    return True


def translate_privacy_policy(policy) -> bool:
    """
    PrivacyPolicy 모델의 content 필드 번역 및 저장
    
    Args:
        policy: PrivacyPolicy 모델 객체
    
    Returns:
        성공 여부
    """
    if policy.content and policy.content.strip():
        return save_translation('privacy_policy', policy.id, 'content', policy.content)
    return True


def migrate_all_translations():
    """
    SQLite의 모든 텍스트 데이터를 번역하여 MongoDB에 저장
    
    이 함수는 초기 마이그레이션 시 한 번만 실행
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from models import Service, ServiceOption, CollageText, GalleryGroup, TermsOfService, PrivacyPolicy
    from app import create_app
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("🌐 다국어 번역 마이그레이션 시작 (GPT 사용)")
        print("=" * 60)
        
        # Service 번역
        print("\n📦 Service 데이터 번역 중...")
        services = Service.query.all()
        for service in services:
            print(f"  - Service #{service.id}: {service.name}")
            translate_service(service)
        print(f"  ✅ {len(services)}개 Service 번역 완료")
        
        # ServiceOption 번역
        print("\n📦 ServiceOption 데이터 번역 중...")
        options = ServiceOption.query.all()
        for option in options:
            print(f"  - ServiceOption #{option.id}: {option.name}")
            translate_service_option(option)
        print(f"  ✅ {len(options)}개 ServiceOption 번역 완료")
        
        # CollageText 번역
        print("\n📦 CollageText 데이터 번역 중...")
        collage_texts = CollageText.query.all()
        for ct in collage_texts:
            print(f"  - CollageText #{ct.id}: {ct.text[:30]}...")
            translate_collage_text(ct)
        print(f"  ✅ {len(collage_texts)}개 CollageText 번역 완료")
        
        # GalleryGroup 번역
        print("\n📦 GalleryGroup 데이터 번역 중...")
        gallery_groups = GalleryGroup.query.all()
        for gg in gallery_groups:
            print(f"  - GalleryGroup #{gg.id}: {gg.title}")
            translate_gallery_group(gg)
        print(f"  ✅ {len(gallery_groups)}개 GalleryGroup 번역 완료")
        
        # TermsOfService 번역
        print("\n📦 TermsOfService 데이터 번역 중...")
        terms = TermsOfService.query.first()
        if terms:
            print(f"  - TermsOfService #{terms.id}")
            translate_terms_of_service(terms)
            print("  ✅ TermsOfService 번역 완료")
        
        # PrivacyPolicy 번역
        print("\n📦 PrivacyPolicy 데이터 번역 중...")
        policy = PrivacyPolicy.query.first()
        if policy:
            print(f"  - PrivacyPolicy #{policy.id}")
            translate_privacy_policy(policy)
            print("  ✅ PrivacyPolicy 번역 완료")
        
        print("\n" + "=" * 60)
        print("🎉 다국어 번역 마이그레이션 완료!")
        print("=" * 60)


# CLI 명령어로 실행 가능
if __name__ == "__main__":
    migrate_all_translations()
