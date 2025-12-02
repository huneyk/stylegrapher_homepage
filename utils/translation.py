"""
다국어 번역 시스템 유틸리티

MongoDB에 번역된 텍스트를 저장하고 관리하는 모듈
OpenAI GPT API를 사용하여 자동 번역 지원

성능 최적화: JSON 파일 캐싱 시스템
- MongoDB 데이터를 JSON 파일로 캐싱하여 읽기 성능 향상
- admin에서 데이터 수정 시 JSON 캐시 자동 업데이트
- JSON 캐시에 데이터가 없으면 MongoDB fallback
"""

import os
import json
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from pymongo import MongoClient
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path

# .env 파일 로드
load_dotenv()

# JSON 캐시 파일 경로
TRANSLATIONS_CACHE_DIR = Path(__file__).parent.parent / 'static' / 'data'
TRANSLATIONS_CACHE_FILE = TRANSLATIONS_CACHE_DIR / 'translations.json'

# 메모리 캐시 (JSON 파일 읽기 최소화)
_translations_memory_cache = None
_cache_lock = threading.Lock()
_cache_last_modified = None

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

# MongoDB 연결 (fork-safe)
mongo_uri = os.environ.get('MONGO_URI')
mongo_client = None
mongo_db = None
translations_collection = None
_translation_connection_pid = None  # 연결이 생성된 프로세스 ID 추적


# ==========================================
# JSON 캐시 시스템 함수들
# ==========================================

def ensure_cache_dir():
    """캐시 디렉토리 생성"""
    TRANSLATIONS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_translations_cache() -> Dict:
    """
    JSON 캐시 파일에서 번역 데이터 로드
    
    메모리 캐시를 사용하여 파일 I/O 최소화
    파일이 변경되면 자동으로 리로드
    
    Returns:
        번역 데이터 딕셔너리 (없으면 빈 딕셔너리)
    """
    global _translations_memory_cache, _cache_last_modified
    
    with _cache_lock:
        # 캐시 파일이 없으면 빈 딕셔너리 반환
        if not TRANSLATIONS_CACHE_FILE.exists():
            return {}
        
        # 파일 수정 시간 확인
        file_mtime = TRANSLATIONS_CACHE_FILE.stat().st_mtime
        
        # 메모리 캐시가 있고 파일이 변경되지 않았으면 메모리 캐시 반환
        if _translations_memory_cache is not None and _cache_last_modified == file_mtime:
            return _translations_memory_cache
        
        # 파일에서 로드
        try:
            with open(TRANSLATIONS_CACHE_FILE, 'r', encoding='utf-8') as f:
                _translations_memory_cache = json.load(f)
                _cache_last_modified = file_mtime
                return _translations_memory_cache
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 번역 캐시 로드 실패: {str(e)}")
            return {}


def save_translations_cache(data: Dict) -> bool:
    """
    번역 데이터를 JSON 캐시 파일로 저장
    
    Args:
        data: 저장할 번역 데이터
    
    Returns:
        성공 여부
    """
    global _translations_memory_cache, _cache_last_modified
    
    with _cache_lock:
        try:
            ensure_cache_dir()
            
            # JSON 파일로 저장 (들여쓰기 없이 compact하게)
            with open(TRANSLATIONS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            
            # 메모리 캐시 업데이트
            _translations_memory_cache = data
            _cache_last_modified = TRANSLATIONS_CACHE_FILE.stat().st_mtime
            
            print(f"✅ 번역 캐시 저장 완료: {len(data)} 항목")
            return True
        except IOError as e:
            print(f"❌ 번역 캐시 저장 실패: {str(e)}")
            return False


def invalidate_memory_cache():
    """메모리 캐시 무효화 (파일 리로드 강제)"""
    global _translations_memory_cache, _cache_last_modified
    with _cache_lock:
        _translations_memory_cache = None
        _cache_last_modified = None


def get_translation_from_cache(source_type: str, source_id: int, field_name: str, lang: str) -> Optional[str]:
    """
    JSON 캐시에서 번역된 텍스트 조회
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
        field_name: 필드명
        lang: 조회할 언어 코드
    
    Returns:
        번역된 텍스트 또는 None (캐시에 없는 경우)
    """
    cache = load_translations_cache()
    
    doc_key = f"{source_type}_{source_id}"
    
    if doc_key not in cache:
        return None
    
    doc = cache[doc_key]
    
    if "fields" not in doc or field_name not in doc["fields"]:
        return None
    
    field_data = doc["fields"][field_name]
    
    # 원본 언어인 경우
    if lang == 'ko':
        return field_data.get("original")
    
    # 번역된 언어인 경우
    translations = field_data.get("translations", {})
    return translations.get(lang)


def get_all_translations_from_cache(source_type: str, source_id: int) -> Optional[Dict]:
    """
    JSON 캐시에서 특정 데이터의 모든 번역 조회
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
    
    Returns:
        모든 필드의 번역 데이터 또는 None
    """
    cache = load_translations_cache()
    
    doc_key = f"{source_type}_{source_id}"
    
    if doc_key not in cache:
        return None
    
    return cache[doc_key].get("fields", {})


def export_mongodb_to_cache() -> bool:
    """
    MongoDB의 모든 번역 데이터를 JSON 캐시 파일로 내보내기
    
    서버 시작 시 또는 전체 데이터 동기화가 필요할 때 호출
    
    Returns:
        성공 여부
    """
    if translations_collection is None:
        if not init_mongodb():
            return False
    
    try:
        # MongoDB에서 모든 번역 데이터 조회
        all_docs = translations_collection.find()
        
        cache_data = {}
        for doc in all_docs:
            doc_key = doc.get('_id')
            if doc_key:
                # _id 필드 제외하고 저장 (중복 방지)
                doc_copy = {k: v for k, v in doc.items() if k != '_id'}
                
                # datetime 객체를 문자열로 변환
                doc_copy = _convert_datetime_to_string(doc_copy)
                
                cache_data[doc_key] = doc_copy
        
        return save_translations_cache(cache_data)
    
    except Exception as e:
        print(f"❌ MongoDB 캐시 내보내기 실패: {str(e)}")
        return False


def update_cache_entry(source_type: str, source_id: int, field_name: str, 
                       original_text: str, translations: Dict[str, str]) -> bool:
    """
    JSON 캐시의 특정 항목 업데이트
    
    MongoDB 저장 후 호출하여 캐시 동기화
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
        field_name: 필드명
        original_text: 원본 텍스트
        translations: 번역된 텍스트 딕셔너리
    
    Returns:
        성공 여부
    """
    cache = load_translations_cache()
    
    doc_key = f"{source_type}_{source_id}"
    
    # 기존 문서가 없으면 새로 생성
    if doc_key not in cache:
        cache[doc_key] = {
            "source_type": source_type,
            "source_id": source_id,
            "fields": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    # 필드 업데이트
    cache[doc_key]["fields"][field_name] = {
        "original": original_text,
        "translations": translations,
        "updated_at": datetime.utcnow().isoformat()
    }
    cache[doc_key]["updated_at"] = datetime.utcnow().isoformat()
    
    return save_translations_cache(cache)


def delete_cache_entry(source_type: str, source_id: int) -> bool:
    """
    JSON 캐시에서 특정 항목 삭제
    
    Args:
        source_type: 데이터 타입
        source_id: 원본 데이터의 ID
    
    Returns:
        성공 여부
    """
    cache = load_translations_cache()
    
    doc_key = f"{source_type}_{source_id}"
    
    if doc_key in cache:
        del cache[doc_key]
        return save_translations_cache(cache)
    
    return True


def _convert_datetime_to_string(obj: Any) -> Any:
    """
    딕셔너리 내의 datetime 객체를 ISO 문자열로 변환
    
    Args:
        obj: 변환할 객체
    
    Returns:
        datetime이 문자열로 변환된 객체
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_datetime_to_string(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetime_to_string(item) for item in obj]
    return obj


# ==========================================
# MongoDB 연결 및 기존 함수들
# ==========================================

def init_mongodb():
    """MongoDB 연결 초기화 (fork-safe)"""
    global mongo_client, mongo_db, translations_collection, _translation_connection_pid
    
    current_pid = os.getpid()
    
    # fork 이후 새 프로세스에서 호출된 경우 연결 재생성
    if _translation_connection_pid is not None and _translation_connection_pid != current_pid:
        print(f"번역 시스템: Fork 감지 (기존 PID: {_translation_connection_pid}, 현재 PID: {current_pid}), 연결 재생성")
        mongo_client = None
        mongo_db = None
        translations_collection = None
    
    # 이미 연결되어 있으면 재사용
    if translations_collection is not None:
        return True
    
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
        
        # 연결 생성 시 PID 저장
        _translation_connection_pid = current_pid
        
        # 인덱스 생성
        translations_collection.create_index([("source_type", 1), ("source_id", 1)], unique=True)
        translations_collection.create_index("updated_at")
        
        print(f"✅ 번역 시스템 MongoDB 연결 성공! (PID: {current_pid})")
        return True
    except Exception as e:
        print(f"❌ 번역 시스템 MongoDB 연결 실패: {str(e)}")
        return False


# 초기 연결 제거 - fork-safe를 위해 lazy 초기화로 변경
# init_mongodb() 는 필요할 때 자동으로 호출됨


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
    번역된 텍스트를 MongoDB에 저장하고 JSON 캐시도 업데이트
    
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
        
        # JSON 캐시도 업데이트
        update_cache_entry(source_type, source_id, field_name, original_text, translations)
        
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
    번역 데이터 삭제 (MongoDB + JSON 캐시)
    
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
        
        # JSON 캐시에서도 삭제
        delete_cache_entry(source_type, source_id)
        
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


def translate_multi_table_packages(packages_data: Dict) -> Dict[str, Dict]:
    """
    다중 테이블 형식의 패키지 데이터 번역 {'tables': [...]} 형식
    
    Args:
        packages_data: {'tables': [{'title': ..., 'packages': [...]}]} 형식의 데이터
    
    Returns:
        언어별 번역된 다중 테이블 패키지 데이터
    """
    result = {'ko': packages_data}
    
    tables = packages_data.get('tables', [])
    if not tables:
        return result
    
    # 모든 문자열 값 추출
    all_strings = []
    string_map = []  # (table_idx, 'title' or ('packages', pkg_idx, key)) 매핑
    
    for table_idx, table in enumerate(tables):
        # 테이블 제목
        if table.get('title') and table['title'].strip():
            all_strings.append(table['title'])
            string_map.append((table_idx, 'title'))
        
        # 패키지 내용
        for pkg_idx, pkg in enumerate(table.get('packages', [])):
            for key, value in pkg.items():
                if isinstance(value, str) and value.strip():
                    all_strings.append(value)
                    string_map.append((table_idx, ('packages', pkg_idx, key)))
    
    if not all_strings:
        return result
    
    # 각 언어로 번역
    for lang_code in SUPPORTED_LANGUAGES.keys():
        if lang_code == 'ko':
            continue
        
        translated_strings = translate_batch_gpt(all_strings, lang_code)
        
        # 번역된 문자열을 다중 테이블 구조에 다시 매핑
        import copy
        translated_data = copy.deepcopy(packages_data)
        
        for idx, mapping in enumerate(string_map):
            if idx < len(translated_strings):
                table_idx, key_info = mapping
                if key_info == 'title':
                    translated_data['tables'][table_idx]['title'] = translated_strings[idx]
                else:
                    # ('packages', pkg_idx, key) 형식
                    _, pkg_idx, key = key_info
                    translated_data['tables'][table_idx]['packages'][pkg_idx][key] = translated_strings[idx]
        
        result[lang_code] = translated_data
    
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
    
    # packages (JSON 배열 또는 다중 테이블 형식)
    if option.packages:
        try:
            packages_data = json.loads(option.packages)
            
            # 새로운 다중 테이블 형식: {'tables': [...]}
            if isinstance(packages_data, dict) and 'tables' in packages_data:
                translated_packages = translate_multi_table_packages(packages_data)
                save_translation('service_option', option.id, 'packages', 
                               option.packages, translated_packages)
            # 기존 단순 배열 형식
            elif isinstance(packages_data, list) and packages_data:
                translated_packages = translate_packages(packages_data)
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
