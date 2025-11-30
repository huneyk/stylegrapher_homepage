"""
번역 헬퍼 모듈

템플릿과 라우트에서 사용할 수 있는 번역 헬퍼 함수들
"""

import json
from typing import Optional, Dict, Any, List
from flask import session, request, g
from functools import wraps

from utils.translation import (
    get_translation, 
    get_all_translations, 
    get_translated_object,
    translate_service,
    translate_service_option,
    translate_collage_text,
    translate_gallery_group,
    translate_terms_of_service,
    translate_privacy_policy,
    SUPPORTED_LANGUAGES
)


def get_current_language() -> str:
    """
    현재 선택된 언어 코드 반환
    
    우선순위:
    1. URL 파라미터 (lang)
    2. 세션 저장된 언어
    3. 브라우저 Accept-Language
    4. 기본값 (ko)
    
    Returns:
        언어 코드 (ko, en, ja, zh, es)
    """
    # g 객체에 캐시되어 있으면 사용
    if hasattr(g, 'current_lang'):
        return g.current_lang
    
    # URL 파라미터
    lang = request.args.get('lang')
    if lang and lang in SUPPORTED_LANGUAGES:
        session['lang'] = lang
        g.current_lang = lang
        return lang
    
    # 세션
    if 'lang' in session and session['lang'] in SUPPORTED_LANGUAGES:
        g.current_lang = session['lang']
        return session['lang']
    
    # 브라우저 Accept-Language
    best_match = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
    if best_match:
        g.current_lang = best_match
        return best_match
    
    # 기본값
    g.current_lang = 'ko'
    return 'ko'


def t(source_type: str, source_id: int, field_name: str, fallback: str = None) -> str:
    """
    번역된 텍스트 조회 (템플릿용 단축 함수)
    
    Args:
        source_type: 데이터 타입 (service, service_option 등)
        source_id: 원본 데이터 ID
        field_name: 필드명
        fallback: 번역이 없을 때 사용할 기본값
    
    Returns:
        번역된 텍스트
    
    사용 예:
        {{ t('service_option', 1, 'name', option.name) }}
    """
    lang = get_current_language()
    translated = get_translation(source_type, source_id, field_name, lang)
    
    if translated:
        return translated
    
    return fallback if fallback is not None else ''


def get_translated_service(service, lang: str = None) -> Dict[str, Any]:
    """
    Service 객체의 번역된 버전 반환
    
    Args:
        service: Service 모델 객체
        lang: 언어 코드 (None이면 현재 언어 사용)
    
    Returns:
        번역된 필드를 포함한 딕셔너리
    """
    if lang is None:
        lang = get_current_language()
    
    # 기본 데이터
    result = {
        'id': service.id,
        'name': service.name,
        'description': service.description,
        'category': service.category,
        'details': [],
        'packages': [],
        'options': service.options if hasattr(service, 'options') else []
    }
    
    if lang == 'ko':
        # 한국어면 원본 반환
        if service.details:
            try:
                result['details'] = json.loads(service.details)
            except json.JSONDecodeError:
                pass
        if service.packages:
            try:
                result['packages'] = json.loads(service.packages)
            except json.JSONDecodeError:
                pass
        return result
    
    # 번역 데이터 조회
    translations = get_all_translations('service', service.id) or {}
    
    # 단순 텍스트 필드 - 원본이 비어있으면 번역도 비어있어야 함
    for field in ['name', 'description', 'category']:
        # 원본 필드 값 확인 (현재 모델의 값)
        original_value = getattr(service, field, None)
        
        # 원본이 비어있으면 번역도 비어있어야 함 (fallback 방지)
        if not original_value or not str(original_value).strip():
            result[field] = original_value  # 빈 값 유지
            continue
        
        # 원본에 값이 있을 때만 번역 조회
        if field in translations:
            field_data = translations[field]
            trans_dict = field_data.get('translations', {})
            # 해당 언어 번역이 있으면 사용, 없으면 원본 사용
            result[field] = trans_dict.get(lang, original_value)
    
    # details (배열) - 원본이 비어있으면 번역도 비어있어야 함
    if service.details and service.details.strip():
        if 'details' in translations:
            field_data = translations['details']
            trans_dict = field_data.get('translations', {})
            result['details'] = trans_dict.get(lang, [])
            if not result['details']:
                try:
                    result['details'] = json.loads(service.details)
                except json.JSONDecodeError:
                    pass
        else:
            try:
                result['details'] = json.loads(service.details)
            except json.JSONDecodeError:
                pass
    
    # packages (배열) - 원본이 비어있으면 번역도 비어있어야 함
    if service.packages and service.packages.strip():
        if 'packages' in translations:
            field_data = translations['packages']
            trans_dict = field_data.get('translations', {})
            result['packages'] = trans_dict.get(lang, [])
            if not result['packages']:
                try:
                    result['packages'] = json.loads(service.packages)
                except json.JSONDecodeError:
                    pass
        else:
            try:
                result['packages'] = json.loads(service.packages)
            except json.JSONDecodeError:
                pass
    
    return result


def get_translated_service_option(option, lang: str = None) -> Dict[str, Any]:
    """
    ServiceOption 객체의 번역된 버전 반환
    
    Args:
        option: ServiceOption 모델 객체
        lang: 언어 코드 (None이면 현재 언어 사용)
    
    Returns:
        번역된 필드를 포함한 딕셔너리
    """
    if lang is None:
        lang = get_current_language()
    
    # 기본 데이터
    result = {
        'id': option.id,
        'service_id': option.service_id,
        'name': option.name,
        'description': option.description,
        'detailed_description': option.detailed_description,
        'booking_method': option.booking_method,
        'payment_info': option.payment_info,
        'guide_info': option.guide_info,
        'refund_policy': option.refund_policy,
        'refund_policy_text': option.refund_policy_text,
        'refund_policy_table': option.refund_policy_table,
        'overtime_charge_table': option.overtime_charge_table,
        'details': [],
        'packages': [],
        'service': option.service if hasattr(option, 'service') else None
    }
    
    if lang == 'ko':
        # 한국어면 원본 반환
        if option.details:
            try:
                result['details'] = json.loads(option.details)
            except json.JSONDecodeError:
                pass
        if option.packages:
            try:
                result['packages'] = json.loads(option.packages)
            except json.JSONDecodeError:
                pass
        return result
    
    # 번역 데이터 조회
    translations = get_all_translations('service_option', option.id) or {}
    
    # 단순 텍스트 필드 - 원본이 비어있으면 번역도 비어있어야 함
    text_fields = [
        'name', 'description', 'detailed_description',
        'booking_method', 'payment_info', 'guide_info',
        'refund_policy', 'refund_policy_text'
    ]
    for field in text_fields:
        # 원본 필드 값 확인 (현재 모델의 값)
        original_value = getattr(option, field, None)
        
        # 원본이 비어있으면 번역도 비어있어야 함 (fallback 방지)
        if not original_value or not str(original_value).strip():
            result[field] = original_value  # 빈 값 유지
            continue
        
        # 원본에 값이 있을 때만 번역 조회
        if field in translations:
            field_data = translations[field]
            trans_dict = field_data.get('translations', {})
            # 해당 언어 번역이 있으면 사용, 없으면 원본 사용
            result[field] = trans_dict.get(lang, original_value)
    
    # details (배열) - 원본이 비어있으면 번역도 비어있어야 함
    if option.details and option.details.strip():
        if 'details' in translations:
            field_data = translations['details']
            trans_dict = field_data.get('translations', {})
            result['details'] = trans_dict.get(lang, [])
            if not result['details']:
                try:
                    result['details'] = json.loads(option.details)
                except json.JSONDecodeError:
                    pass
        else:
            try:
                result['details'] = json.loads(option.details)
            except json.JSONDecodeError:
                pass
    
    # packages (배열 또는 다중 테이블 형식) - 원본이 비어있으면 번역도 비어있어야 함
    if option.packages and option.packages.strip():
        if 'packages' in translations:
            field_data = translations['packages']
            trans_dict = field_data.get('translations', {})
            translated_packages = trans_dict.get(lang)
            if translated_packages:
                result['packages'] = translated_packages
            else:
                # 번역이 없으면 원본 사용
                try:
                    result['packages'] = json.loads(option.packages)
                except json.JSONDecodeError:
                    pass
        else:
            try:
                result['packages'] = json.loads(option.packages)
            except json.JSONDecodeError:
                pass
    
    # refund_policy_table (파이프 구분 텍스트) - 원본이 비어있으면 번역도 비어있어야 함
    if option.refund_policy_table and option.refund_policy_table.strip():
        if 'refund_policy_table' in translations:
            field_data = translations['refund_policy_table']
            trans_dict = field_data.get('translations', {})
            translated_table = trans_dict.get(lang)
            if translated_table:
                result['refund_policy_table'] = translated_table
    
    # overtime_charge_table (파이프 구분 텍스트) - 원본이 비어있으면 번역도 비어있어야 함
    if option.overtime_charge_table and option.overtime_charge_table.strip():
        if 'overtime_charge_table' in translations:
            field_data = translations['overtime_charge_table']
            trans_dict = field_data.get('translations', {})
            translated_table = trans_dict.get(lang)
            if translated_table:
                result['overtime_charge_table'] = translated_table
    
    return result


def get_translated_collage_text(collage_text, lang: str = None) -> Dict[str, Any]:
    """
    CollageText 객체의 번역된 버전 반환
    
    Args:
        collage_text: CollageText 모델 객체
        lang: 언어 코드
    
    Returns:
        번역된 필드를 포함한 딕셔너리
    """
    if lang is None:
        lang = get_current_language()
    
    result = {
        'id': collage_text.id,
        'text': collage_text.text,
        'order': collage_text.order
    }
    
    if lang == 'ko':
        return result
    
    translated = get_translation('collage_text', collage_text.id, 'text', lang)
    if translated:
        result['text'] = translated
    
    return result


def get_translated_gallery_group(gallery_group, lang: str = None) -> Dict[str, Any]:
    """
    GalleryGroup 객체의 번역된 버전 반환
    
    Args:
        gallery_group: GalleryGroup 모델 객체
        lang: 언어 코드
    
    Returns:
        번역된 필드를 포함한 딕셔너리
    """
    if lang is None:
        lang = get_current_language()
    
    result = {
        'id': gallery_group.id,
        'title': gallery_group.title,
        'display_order': gallery_group.display_order,
        'is_pinned': gallery_group.is_pinned,
        'created_at': gallery_group.created_at,
        'images': gallery_group.images if hasattr(gallery_group, 'images') else []
    }
    
    if lang == 'ko':
        return result
    
    translated = get_translation('gallery_group', gallery_group.id, 'title', lang)
    if translated:
        result['title'] = translated
    
    return result


class TranslatedModel:
    """
    모델 객체를 감싸서 번역된 속성에 접근할 수 있게 해주는 래퍼 클래스
    
    사용 예:
        option = ServiceOption.query.get(1)
        translated = TranslatedModel(option, 'service_option')
        print(translated.name)  # 현재 언어로 번역된 이름
    """
    
    def __init__(self, model, source_type: str, lang: str = None):
        self._model = model
        self._source_type = source_type
        self._lang = lang or get_current_language()
        self._translations = None
    
    def _load_translations(self):
        if self._translations is None:
            self._translations = get_all_translations(self._source_type, self._model.id) or {}
    
    def __getattr__(self, name):
        # 내부 속성
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        
        # 원본 모델의 속성 가져오기
        original_value = getattr(self._model, name, None)
        
        # 한국어면 원본 반환
        if self._lang == 'ko':
            return original_value
        
        # 번역 데이터 로드
        self._load_translations()
        
        # 번역된 값이 있으면 반환
        if name in self._translations:
            field_data = self._translations[name]
            trans_dict = field_data.get('translations', {})
            translated = trans_dict.get(self._lang)
            if translated:
                return translated
        
        # 번역이 없으면 원본 반환
        return original_value


def auto_translate_on_save(model_type: str):
    """
    모델 저장 시 자동 번역을 수행하는 데코레이터
    
    Args:
        model_type: 모델 타입 (service, service_option 등)
    
    사용 예:
        @auto_translate_on_save('service_option')
        def edit_option(option_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # 함수 실행 후 번역 수행
            # 이 부분은 라우트에서 직접 호출하는 것이 더 좋을 수 있음
            
            return result
        return wrapper
    return decorator


def trigger_translation(model_type: str, model_instance):
    """
    모델 인스턴스에 대한 번역 트리거
    
    데이터 추가/수정 후 이 함수를 호출하여 번역 수행
    
    Args:
        model_type: 모델 타입 (service, service_option, collage_text, gallery_group, terms_of_service, privacy_policy 등)
        model_instance: 모델 인스턴스
    """
    import threading
    
    def translate_async():
        try:
            if model_type == 'service':
                translate_service(model_instance)
            elif model_type == 'service_option':
                translate_service_option(model_instance)
            elif model_type == 'collage_text':
                translate_collage_text(model_instance)
            elif model_type == 'gallery_group':
                translate_gallery_group(model_instance)
            elif model_type == 'terms_of_service':
                translate_terms_of_service(model_instance)
            elif model_type == 'privacy_policy':
                translate_privacy_policy(model_instance)
            print(f"✅ 비동기 번역 완료: {model_type}_{model_instance.id}")
        except Exception as e:
            print(f"❌ 비동기 번역 오류: {str(e)}")
    
    # 백그라운드에서 번역 수행
    thread = threading.Thread(target=translate_async)
    thread.daemon = True
    thread.start()


def register_template_helpers(app):
    """
    Flask 앱에 번역 관련 템플릿 헬퍼 함수 등록
    
    Args:
        app: Flask 앱 인스턴스
    """
    
    @app.context_processor
    def inject_translation_helpers():
        return {
            't': t,
            'get_current_language': get_current_language,
            'get_translated_service': get_translated_service,
            'get_translated_service_option': get_translated_service_option,
            'get_translated_collage_text': get_translated_collage_text,
            'get_translated_gallery_group': get_translated_gallery_group,
            'TranslatedModel': TranslatedModel,
            'SUPPORTED_LANGUAGES': SUPPORTED_LANGUAGES
        }
    
    # Jinja2 필터 등록
    @app.template_filter('translate')
    def translate_filter(value, source_type, source_id, field_name):
        """
        Jinja2 필터로 번역 적용
        
        사용 예:
            {{ option.name | translate('service_option', option.id, 'name') }}
        """
        lang = get_current_language()
        translated = get_translation(source_type, source_id, field_name, lang)
        return translated if translated else value

