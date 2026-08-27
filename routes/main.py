"""
Main 라우트 - MongoDB 기반
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file, make_response, session
from flask_babel import gettext as _
from flask_mail import Message
import json
import os
import io
from PIL import Image
from datetime import datetime, timedelta
# pymongo 상수는 utils/mongo_models.py에서 사용
from dotenv import load_dotenv
import functools

# MongoDB 모델 임포트
from utils.mongo_models import (
    get_mongo_db,
    Service, ServiceOption, GalleryGroup, Gallery,
    Booking, Inquiry, CollageText,
    TermsOfService, PrivacyPolicy, get_next_id,
    AdminNotificationEmail, AboutContent, PackagePhoto, PackagePhotoCategory,
    Notice
)
from utils.translation_helper import (
    get_current_language, 
    get_translated_service, 
    get_translated_service_option,
    get_translated_collage_text,
    get_translated_gallery_group,
    get_translated_notice,
    translate_package_photo_category,
    translate_package_photo_concept
)
from utils.gridfs_helper import get_image_from_gridfs, get_mongo_connection
from extensions import mail, cache
from utils.visitor_tracker import log_visitor
from utils.email_utils import send_email_with_retry, send_customer_email, send_admin_notification

# MongoDB 설정 불러오기 (fork-safe: 연결은 lazy하게 생성됨)
load_dotenv()


# 이미지 리사이징 함수
def resize_image_memory(img, width=1080):
    original_width, original_height = img.size
    ratio = width / original_width
    target_height = int(original_height * ratio)
    resized_img = img.resize((width, target_height), Image.Resampling.LANCZOS)
    return resized_img


# Create the Blueprint object
main = Blueprint('main', __name__)


# 방문자 추적 미들웨어
@main.before_request
def track_visitor():
    """페이지 방문 시 방문자 정보 기록"""
    # 추적 제외 경로
    excluded_paths = ['/static/', '/admin/', '/api/', '/favicon', '/_']
    
    # 제외 경로 확인
    if any(request.path.startswith(path) for path in excluded_paths):
        return
    
    # 정적 파일 확장자 제외
    static_extensions = ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf']
    if any(request.path.endswith(ext) for ext in static_extensions):
        return
    
    # AJAX 요청 제외
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return
    
    try:
        # IP 주소 가져오기 (프록시 고려)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        # User-Agent
        user_agent = request.headers.get('User-Agent', '')
        
        # 현재 언어
        language = session.get('language', 'ko')
        
        # 세션 ID
        session_id = session.get('_id') or request.cookies.get('session')
        
        # Referrer
        referrer = request.referrer
        
        # 방문 기록
        log_visitor(
            ip_address=ip_address,
            user_agent=user_agent,
            page_url=request.path,
            session_id=session_id,
            language=language,
            referrer=referrer,
            tokens_used=0,
            cost_usd=0.0
        )
    except Exception as e:
        # 추적 실패 시 무시 (사용자 경험에 영향 없음)
        print(f"방문자 추적 오류 (무시): {str(e)}")

# 간단한 메모리 캐시 구현
_cache = {}
_cache_timestamps = {}


def cache_with_timeout(timeout_seconds=300):
    """메모리 캐시 데코레이터 (언어별 캐싱 지원, 응답 전체 캐싱)"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 언어 설정을 캐시 키에 포함하여 다국어 지원
            current_lang = get_current_language()
            cache_key = f"{func.__name__}:{current_lang}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            if cache_key in _cache_timestamps:
                if datetime.now() - _cache_timestamps[cache_key] < timedelta(seconds=timeout_seconds):
                    return _cache[cache_key]
            
            result = func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_timestamps[cache_key] = datetime.now()
            
            return result
        return wrapper
    return decorator


def make_cache_key_with_lang():
    """언어별 캐시 키 생성 함수"""
    lang = get_current_language()
    return f"{request.path}:{lang}"


def make_cache_key_gallery():
    """갤러리 페이지용 캐시 키 생성 함수 (페이지 번호 포함)"""
    lang = get_current_language()
    # URL에서 페이지 번호 추출
    page = request.view_args.get('page', 1) if request.view_args else 1
    return f"gallery:{lang}:{page}"


def make_cache_key_service_detail():
    """서비스 상세 페이지용 캐시 키 생성 함수"""
    lang = get_current_language()
    service_id = request.view_args.get('id', 0) if request.view_args else 0
    return f"service:{lang}:{service_id}"


def make_cache_key_service_option():
    """서비스 옵션 상세 페이지용 캐시 키 생성 함수"""
    lang = get_current_language()
    option_id = request.view_args.get('id', 0) if request.view_args else 0
    return f"service_option:{lang}:{option_id}"


def clear_gallery_cache():
    """갤러리 관련 캐시를 모두 클리어하는 함수"""
    global _cache, _cache_timestamps
    keys_to_remove = []
    
    for key in _cache.keys():
        if key.startswith('gallery:') or key.startswith('index:'):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        if key in _cache:
            del _cache[key]
        if key in _cache_timestamps:
            del _cache_timestamps[key]
    
    print(f"🧹 갤러리 캐시 클리어 완료: {len(keys_to_remove)}개 항목 제거")


def clear_index_page_cache():
    """인덱스 페이지의 Flask-Caching 캐시를 모든 언어에 대해 클리어"""
    languages = ['ko', 'en', 'ja', 'zh', 'es']
    for lang in languages:
        cache.delete(f"/:{lang}")
    print("🧹 인덱스 페이지 캐시 클리어 완료")


def clear_service_option_cache(option_id=None):
    """서비스 옵션 관련 캐시를 클리어하는 함수
    
    Args:
        option_id: 특정 옵션 ID만 클리어할 경우 지정 (None이면 모든 서비스 옵션 캐시 클리어)
    """
    global _cache, _cache_timestamps
    
    # 지원되는 언어 목록
    languages = ['ko', 'en', 'ja', 'zh', 'es']
    
    # Flask-Caching 캐시 클리어
    if option_id:
        # 특정 옵션에 대해 모든 언어별 캐시 클리어
        for lang in languages:
            cache_key = f"service_option:{lang}:{option_id}"
            cache.delete(cache_key)
        print(f"🧹 서비스 옵션 캐시 클리어 완료 - 옵션 ID: {option_id}")
    else:
        # 모든 서비스 옵션 캐시 클리어 (패턴 삭제가 지원되지 않으면 전체 클리어)
        cache.clear()
        print(f"🧹 전체 캐시 클리어 완료")
    
    # 메모리 캐시에서도 서비스 관련 캐시 클리어
    keys_to_remove = []
    for key in list(_cache.keys()):
        if key.startswith('get_all_services:') or key.startswith('service_option:'):
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        if key in _cache:
            del _cache[key]
        if key in _cache_timestamps:
            del _cache_timestamps[key]
    
    if keys_to_remove:
        print(f"🧹 메모리 캐시 클리어 완료: {len(keys_to_remove)}개 항목 제거")


@cache_with_timeout(300)  # 5분 캐싱
def get_all_services():
    """모든 서비스와 서비스 옵션을 가져와서 카테고리별로 그룹화 (i18n 적용)"""
    from collections import OrderedDict
    
    lang = get_current_language()
    services = Service.query_all()
    service_options = ServiceOption.query_all()
    
    # 서비스를 미리 딕셔너리로 캐시하여 N+1 쿼리 방지
    services_dict = {s.id: s for s in services}
    
    # 서비스별 옵션 존재 여부 미리 계산 (N+1 쿼리 방지)
    services_with_options = set(opt.service_id for opt in service_options)
    
    # 카테고리별로 그룹화된 딕셔너리
    grouped_services = OrderedDict()
    
    for option in service_options:
        # 캐시된 서비스 딕셔너리에서 조회 (N+1 쿼리 방지)
        service = services_dict.get(option.service_id)
        
        # 번역 적용
        translated_option = get_translated_service_option(option, lang)
        translated_service = get_translated_service(service, lang) if service else None
        
        category = translated_service.get('name', service.name) if translated_service else '기타'
        
        if category not in grouped_services:
            grouped_services[category] = []
        
        grouped_services[category].append({
            'type': 'option',
            'id': f'option_{option.id}',
            'name': translated_option.get('name', option.name)
        })
    
    for service in services:
        # 캐시된 set에서 옵션 존재 여부 확인 (N+1 쿼리 방지)
        if service.id not in services_with_options:
            translated_service = get_translated_service(service, lang)
            category = '기타'
            
            if category not in grouped_services:
                grouped_services[category] = []
            
            grouped_services[category].append({
                'type': 'service',
                'id': f'service_{service.id}',
                'name': translated_service.get('name', service.name)
            })
    
    # 카테고리별로 정렬하고 각 카테고리 내 서비스도 이름으로 정렬
    sorted_grouped = OrderedDict()
    for category in sorted(grouped_services.keys()):
        sorted_grouped[category] = sorted(grouped_services[category], key=lambda x: x['name'])
    
    return sorted_grouped


@main.route('/')
@cache.cached(timeout=300, key_prefix=make_cache_key_with_lang)  # 5분 캐싱 (전체 응답)
def index():
    # 갤러리 그룹을 상단 고정, 표출 순서, 생성일 순으로 가져오기
    all_galleries = GalleryGroup.query_all_ordered()
    
    # 상위 3개는 collage용 (상단 고정된 갤러리가 우선)
    recent_galleries = all_galleries[:3] if all_galleries else []
    
    # 4-6번째는 하단 갤러리용
    preview_galleries = all_galleries[3:6] if len(all_galleries) > 3 else []
    
    services = Service.query_all()
    
    # Fade Text 데이터 가져오기 (순서별로 정렬)
    fade_texts_raw = CollageText.query_all_ordered()
    
    # 현재 언어에 맞게 번역된 Fade Text 가져오기
    lang = get_current_language()
    fade_texts = [get_translated_collage_text(ft, lang) for ft in fade_texts_raw]
    
    # 갤러리 그룹 번역
    translated_recent = [get_translated_gallery_group(g, lang) for g in recent_galleries]
    translated_preview = [get_translated_gallery_group(g, lang) for g in preview_galleries]
    
    # 활성화된 공지사항 가져오기 (최대 3개) + 번역
    active_notices = Notice.query_active(limit=3)
    translated_notices = [get_translated_notice(n, lang) for n in active_notices]
    
    return render_template('index.html', 
                         recent_galleries=recent_galleries,
                         preview_galleries=preview_galleries,
                         translated_recent=translated_recent,
                         translated_preview=translated_preview,
                         services=services,
                         fade_texts=fade_texts,
                         notices=translated_notices)


@main.route('/api/notice/<int:notice_id>')
def get_notice_content(notice_id):
    """공지사항 본문 JSON 반환 (모달용) - i18n 적용"""
    from flask import jsonify
    try:
        notice = Notice.get_by_id(notice_id)
        if not notice or not notice.is_active:
            return jsonify({'error': 'Not found'}), 404
        lang = get_current_language()
        translated = get_translated_notice(notice, lang)
        response = jsonify({
            'id': translated['id'],
            'title': translated['title'],
            'content': translated['content'],
            'created_at': notice.created_at.strftime('%Y-%m-%d') if notice.created_at else ''
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/services')
@cache.cached(timeout=300, key_prefix=make_cache_key_with_lang)  # 5분 캐싱
def services():
    lang = get_current_language()
    
    categories_data = {
        'ai_analysis': {
            'title': 'AI 분석',
            'description': '인공지능을 활용한 정밀 스타일 분석',
            'icon': 'bi-cpu',
            'color': '#6f42c1',
            'services': []
        },
        'consulting': {
            'title': '컨설팅 프로그램',
            'description': '전문가와 함께하는 1:1 맞춤 컨설팅',
            'icon': 'bi-person-check',
            'color': '#0d6efd',
            'services': []
        },
        'oneday': {
            'title': '원데이 스타일링',
            'description': '하루만에 완성하는 완벽한 변신',
            'icon': 'bi-star',
            'color': '#20c997',
            'services': []
        },
        'photo': {
            'title': '프리미엄 화보 제작',
            'description': '특별한 순간을 기록하는 전문 촬영',
            'icon': 'bi-camera',
            'color': '#fd7e14',
            'services': []
        }
    }
    
    services_list = Service.query_all()
    translated_options = {}
    
    for service in services_list:
        if service.category and service.category in categories_data:
            categories_data[service.category]['services'].append(service)
            
            for option in service.options:
                translated_options[option.id] = get_translated_service_option(option, lang)
    
    return render_template('services_new.html', 
                         categories_data=categories_data,
                         translated_options=translated_options,
                         current_lang=lang)


@main.route('/service/<int:id>')
@cache.cached(timeout=300, key_prefix=make_cache_key_service_detail)  # 5분 캐싱
def service_detail(id):
    service = Service.get_or_404(id)
    
    lang = get_current_language()
    translated = get_translated_service(service, lang)
    
    details = translated.get('details', [])
    packages = translated.get('packages', [])
    
    return render_template('service_detail.html', 
                         service=service,
                         translated=translated,
                         details=details,
                         packages=packages)


@main.route('/service_option/<int:id>')
@cache.cached(timeout=300, key_prefix=make_cache_key_service_option)  # 5분 캐싱
def service_option_detail(id):
    service_option = ServiceOption.get_or_404(id)
    
    lang = get_current_language()
    translated = get_translated_service_option(service_option, lang)
    
    details = translated.get('details', [])
    packages = translated.get('packages', [])
    
    # 원본 한국어 패키지 데이터 (카테고리 매칭용)
    original_packages = []
    if service_option.packages:
        try:
            original_packages = json.loads(service_option.packages)
        except json.JSONDecodeError:
            pass
    
    # 패키지 화보 조회 (활성화된 것만)
    package_photos = PackagePhoto.query_by_service_option(id, active_only=True)
    
    # 카테고리 순서 정보 가져오기
    categories = PackagePhotoCategory.query_by_service_option(id)
    
    # 카테고리별로 그룹화
    photos_by_category = {}
    for photo in package_photos:
        category = photo.category or '기타'
        if category not in photos_by_category:
            photos_by_category[category] = []
        photos_by_category[category].append(photo)
    
    # 카테고리 순서대로 정렬된 딕셔너리 생성
    sorted_photos_by_category = {}
    for cat in categories:
        if cat.name in photos_by_category:
            sorted_photos_by_category[cat.name] = photos_by_category[cat.name]
    # 순서가 없는 카테고리도 추가
    for cat_name in photos_by_category:
        if cat_name not in sorted_photos_by_category:
            sorted_photos_by_category[cat_name] = photos_by_category[cat_name]
    
    # 공개 화면에서 샘플 갤러리만 숨김 (DB 데이터·가격표는 유지)
    if id == 11:
        sorted_photos_by_category = {}
    
    return render_template('service_option_detail.html', 
                         service_option=service_option,
                         translated=translated,
                         details=details,
                         packages=packages,
                         original_packages=original_packages,
                         package_photos=package_photos,
                         photos_by_category=sorted_photos_by_category,
                         current_lang=lang,
                         translate_category=translate_package_photo_category,
                         translate_concept=translate_package_photo_concept)


@main.route('/image/<path:image_path>')
def serve_image(image_path):
    """GridFS 및 레거시 저장소에서 이미지를 효율적으로 서빙하는 라우트 (캐싱 최적화)"""
    try:
        # 강화된 캐싱 헤더 설정 (30일 캐싱 + ETag)
        cache_headers = {
            'Cache-Control': 'public, max-age=2592000, immutable',
            'Vary': 'Accept-Encoding'
        }
        
        # 1. GridFS에서 이미지 조회 시도 (메모리 캐시 + ETag 지원)
        try:
            binary_data, content_type, etag = get_image_from_gridfs(image_path)
            if binary_data:
                # ETag 기반 조건부 요청 처리 (304 Not Modified)
                if etag:
                    client_etag = request.headers.get('If-None-Match')
                    if client_etag and client_etag.strip('"') == etag:
                        response = make_response('', 304)
                        response.headers['ETag'] = f'"{etag}"'
                        response.headers['Cache-Control'] = cache_headers['Cache-Control']
                        return response
                
                response = make_response(binary_data)
                response.headers['Content-Type'] = content_type
                if etag:
                    response.headers['ETag'] = f'"{etag}"'
                for key, value in cache_headers.items():
                    response.headers[key] = value
                return response
        except Exception as gridfs_error:
            print(f"GridFS 조회 중 오류: {str(gridfs_error)}")
        
        # 2. 레거시 MongoDB 컬렉션에서 조회
        try:
            db = get_mongo_db()
            images_collection = db['gallery']
            image_doc = images_collection.find_one({'_id': image_path})
            if image_doc and 'binary_data' in image_doc:
                response = make_response(image_doc['binary_data'])
                response.headers['Content-Type'] = image_doc.get('content_type', 'image/jpeg')
                for key, value in cache_headers.items():
                    response.headers[key] = value
                return response
        except Exception as mongo_error:
            print(f"레거시 MongoDB 조회 중 오류: {str(mongo_error)}")
        
        # 3. 파일 시스템에서 서빙
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
        if os.path.exists(file_path):
            response = send_file(file_path)
            for key, value in cache_headers.items():
                response.headers[key] = value
            return response
        
        return "Image not found", 404
        
    except Exception as e:
        print(f"이미지 서빙 오류: {str(e)}")
        return "Image serving error", 500


@main.route('/package-photo-image/<image_id>')
def serve_package_photo_image(image_id):
    """패키지 화보 이미지 서빙 (GridFS)"""
    try:
        cache_headers = {
            'Cache-Control': 'public, max-age=2592000, immutable',
            'Vary': 'Accept-Encoding'
        }
        
        binary_data, content_type, etag = get_image_from_gridfs(image_id)
        if binary_data:
            # ETag 기반 조건부 요청 처리
            if etag:
                client_etag = request.headers.get('If-None-Match')
                if client_etag and client_etag.strip('"') == etag:
                    response = make_response('', 304)
                    response.headers['ETag'] = f'"{etag}"'
                    response.headers['Cache-Control'] = cache_headers['Cache-Control']
                    return response
            
            response = make_response(binary_data)
            response.headers['Content-Type'] = content_type
            if etag:
                response.headers['ETag'] = f'"{etag}"'
            for key, value in cache_headers.items():
                response.headers[key] = value
            return response
        
        return "Image not found", 404
        
    except Exception as e:
        print(f"패키지 화보 이미지 서빙 오류: {str(e)}")
        return "Image serving error", 500


@main.route('/gallery')
@main.route('/gallery/<int:page>')
@cache.cached(timeout=300, key_prefix=make_cache_key_gallery)  # 5분 캐싱
def gallery(page=1):
    try:
        per_page = 9
        
        # 갤러리 그룹 총 개수 조회
        total_groups = GalleryGroup.count()
        
        # 페이지네이션 정보
        total_pages = (total_groups + per_page - 1) // per_page
        has_more = page < total_pages
        next_page = page + 1 if has_more else None
        
        # 페이지네이션된 갤러리 그룹 조회
        gallery_groups = GalleryGroup.query_paginated(page=page, per_page=per_page)
        
        # 딕셔너리 형태로 변환 (템플릿 호환성)
        groups_dict = []
        for group in gallery_groups:
            groups_dict.append({
                'id': group.id,
                'title': group.title,
                'created_at': group.created_at,
                'is_pinned': group.is_pinned,
                'display_order': group.display_order,
                'images': [{'id': img.id, 'image_path': img.image_path, 'order': img.order} for img in group.images]
            })
        
        if request.headers.get('HX-Request'):
            gallery_items_html = render_template('_gallery_items.html', gallery_groups=groups_dict)
            
            if has_more:
                button_html = f'''
                <button class="btn gallery-more-btn"
                        hx-get="{url_for('main.gallery', page=next_page)}"
                        hx-target="#gallery-container"
                        hx-swap="beforeend"
                        hx-trigger="click"
                        hx-indicator="#loading-indicator">
                    더 많은 갤러리 보기
                </button>
                <div id="loading-indicator" class="htmx-indicator">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>'''
            else:
                button_html = ''
            
            response_html = gallery_items_html + f'<div id="load-more-section" hx-swap-oob="true">{button_html}</div>'
            return response_html
        
        return render_template('gallery.html', 
                              gallery_groups=groups_dict, 
                              has_more=has_more,
                              next_page=next_page)
                              
    except Exception as e:
        print(f"Error in gallery route: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('gallery.html', 
                              gallery_groups=[], 
                              has_more=False,
                              next_page=None)


@main.route('/gallery/detail/<int:group_id>')
def gallery_detail(group_id):
    """특정 갤러리 그룹의 모든 이미지를 보여주는 상세 페이지"""
    try:
        gallery_group = GalleryGroup.get_or_404(group_id)
        gallery_images = Gallery.query_by_group(group_id)
        
        return render_template('gallery_detail.html', 
                             gallery_group=gallery_group,
                             gallery_images=gallery_images)
                             
    except Exception as e:
        print(f"Error in gallery_detail route: {str(e)}")
        flash('갤러리를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('main.gallery'))


@main.route('/booking-choice')
def booking_choice():
    """예약 방법 선택 페이지"""
    return render_template('booking_choice.html')


@main.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        contact_phone = request.form.get('contact')
        email = request.form.get('email')
        selected_service = request.form.get('service')
        message = request.form.get('message')
        request_type = request.form.get('request_type', 'inquiry')  # 'inquiry' 또는 'booking'
        
        # 서비스 타입과 ID 파싱 (option_1 또는 service_1 형식)
        service_type, service_db_id = selected_service.split('_', 1)
        service_db_id = int(service_db_id)
        
        if service_type == 'option':
            service_option = ServiceOption.get_by_id(service_db_id)
            actual_service_id = service_option.service_id
            selected_service_name = service_option.name
        else:
            service = Service.get_by_id(service_db_id)
            actual_service_id = service.id
            selected_service_name = service.name
        
        # AI Agent 시스템으로 이메일 처리
        from utils.email_agents import process_inquiry_email
        
        ai_result = process_inquiry_email(
            name=name,
            email=email,
            phone=contact_phone,
            message=message,
            service_name=selected_service_name,
            service_id=actual_service_id
        )
        
        email_sent = False
        response_sent = False
        admin_notified = False
        is_booking = (request_type == 'booking')
        
        if is_booking:
            # 예약인 경우: Booking 컬렉션에 저장
            # 희망 예약일시 처리
            dates = request.form.getlist('date[]')
            times = request.form.getlist('time[]')
            datetime_message = "희망 예약일시:\n"
            
            for i, (date, time) in enumerate(zip(dates, times), 1):
                if date and time:
                    datetime_message += f"{i}순위: {date} {time}\n"
            
            enhanced_message = f"[예약 서비스: {selected_service_name}]\n\n{message}\n\n{datetime_message}"
            
            # MongoDB에 예약 저장 (AI 분석 결과 포함)
            booking = Booking(
                name=name,
                phone=contact_phone,
                email=email,
                service_id=actual_service_id,
                message=enhanced_message,
                status='대기',
                is_spam=ai_result.is_spam,
                spam_reason=ai_result.spam_reason,
                is_irrelevant=ai_result.is_irrelevant,
                irrelevant_reason=ai_result.irrelevant_reason,
                detected_language=ai_result.detected_language,
                sentiment=ai_result.sentiment,
                sentiment_detail=ai_result.sentiment_detail,
                ai_response=ai_result.ai_response,
                translated_message=ai_result.translated_message,
                ai_processed=ai_result.success,
                ai_processed_at=datetime.utcnow() if ai_result.success else None
            )
            booking.save()
            
            # 스팸인 경우: 회신하지 않음
            if ai_result.is_spam:
                print(f"🚫 스팸 예약 차단: {name} ({email}) - 사유: {ai_result.spam_reason}")
            # 관련 없는 내용인 경우: 간략한 회신만 전송, 관리자 알림 없음
            elif ai_result.is_irrelevant:
                print(f"⚠️ 관련 없는 예약 요청: {name} ({email}) - 사유: {ai_result.irrelevant_reason}")
                # 고객에게 간략한 회신만 전송
                if ai_result.ai_response:
                    customer_subject = _get_customer_subject(ai_result.detected_language, selected_service_name, is_booking=True)
                    
                    success, error = send_email_with_retry(
                        subject=customer_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email],
                        body=ai_result.ai_response,
                        record_type='booking',
                        record_id=str(booking.id) if hasattr(booking, 'id') else None
                    )
                    
                    if success:
                        response_sent = True
                        booking.response_sent = True
                        booking.response_sent_at = datetime.utcnow()
                        booking.response_email_subject = customer_subject
                        print(f"✅ 관련 없는 예약 요청에 간략한 회신 발송 완료: {email}")
                    else:
                        print(f"❌ 관련 없는 예약 요청 회신 발송 오류: {error}")
                # 관리자 알림 없음
            # 정상적인 예약인 경우: 고객 응답 + 관리자 알림
            elif not ai_result.is_spam:
                # 1. 고객에게 AI 응답 전송
                if ai_result.ai_response:
                    customer_subject = _get_customer_subject(ai_result.detected_language, selected_service_name, is_booking=True)
                    
                    success, error = send_email_with_retry(
                        subject=customer_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email],
                        body=ai_result.ai_response,
                        record_type='booking',
                        record_id=str(booking.id) if hasattr(booking, 'id') else None
                    )
                    
                    if success:
                        response_sent = True
                        booking.response_sent = True
                        booking.response_sent_at = datetime.utcnow()
                        booking.response_email_subject = customer_subject
                        print(f"✅ 예약 고객 응답 이메일 발송 완료: {email}")
                    else:
                        print(f"❌ 예약 고객 응답 이메일 발송 오류: {error}")
                
                # 2. 관리자에게 알림 전송
                admin_subject = f"[스타일그래퍼 예약] {selected_service_name} - {name}님 ({ai_result.detected_language.upper()})"
                
                admin_body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 스타일그래퍼 새 예약 신청
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 예약자 정보
• 이름: {name}
• 휴대폰: {contact_phone}
• 이메일: {email}

■ 예약 서비스
• {selected_service_name}

■ AI 분석 결과
• 감지된 언어: {ai_result.detected_language}
• 감성: {ai_result.sentiment} ({ai_result.sentiment_detail})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 메시지 원문
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{message}

■ {datetime_message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 메시지 한국어 번역 (원문이 한국어가 아닌 경우)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.translated_message if ai_result.detected_language != 'ko' else '(원문이 한국어입니다)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI 자동 응답 원문 (고객에게 발송됨)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.ai_response if ai_result.ai_response else '(AI 응답 생성 실패)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 AI 응답 한국어 번역 (원문이 한국어가 아닌 경우)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.translated_ai_response if ai_result.detected_language != 'ko' else '(원문이 한국어입니다)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 메일은 스타일그래퍼 홈페이지에서 자동으로 발송되었습니다.
"""
                
                booking_recipients = AdminNotificationEmail.get_active_emails('bookings')
                if not booking_recipients:
                    AdminNotificationEmail.initialize_default()
                    booking_recipients = AdminNotificationEmail.get_active_emails('bookings')
                
                if booking_recipients:
                    success, error = send_email_with_retry(
                        subject=admin_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=booking_recipients,
                        body=admin_body,
                        reply_to=email,
                        record_type='booking',
                        record_id=str(booking.id) if hasattr(booking, 'id') else None
                    )
                    
                    if success:
                        email_sent = True
                        admin_notified = True
                        booking.admin_notified = True
                        print(f"✅ 예약 관리자 알림 이메일 발송 완료: {', '.join(booking_recipients)}")
                    else:
                        print(f"❌ 예약 관리자 알림 이메일 발송 오류: {error}")
                else:
                    print("⚠️ 예약 알림을 받을 이메일이 없습니다.")
            
            booking.save()
            
        else:
            # 문의인 경우: Inquiry 컬렉션에 저장
            enhanced_message = f"[문의 대상: {selected_service_name}]\n\n{message}"
            
            # MongoDB에 문의 저장 (AI 분석 결과 포함)
            inquiry = Inquiry(
                name=name,
                phone=contact_phone,
                email=email,
                service_id=actual_service_id,
                message=enhanced_message,
                is_spam=ai_result.is_spam,
                spam_reason=ai_result.spam_reason,
                is_irrelevant=ai_result.is_irrelevant,
                irrelevant_reason=ai_result.irrelevant_reason,
                detected_language=ai_result.detected_language,
                sentiment=ai_result.sentiment,
                sentiment_detail=ai_result.sentiment_detail,
                ai_response=ai_result.ai_response,
                translated_message=ai_result.translated_message,
                ai_processed=ai_result.success,
                ai_processed_at=datetime.utcnow() if ai_result.success else None
            )
            inquiry.save()
            
            # 스팸인 경우: 회신하지 않음
            if ai_result.is_spam:
                print(f"🚫 스팸 문의 차단: {name} ({email}) - 사유: {ai_result.spam_reason}")
            # 관련 없는 내용인 경우: 간략한 회신만 전송, 관리자 알림 없음
            elif ai_result.is_irrelevant:
                print(f"⚠️ 관련 없는 문의: {name} ({email}) - 사유: {ai_result.irrelevant_reason}")
                # 고객에게 간략한 회신만 전송
                if ai_result.ai_response:
                    customer_subject = _get_customer_subject(ai_result.detected_language, selected_service_name, is_booking=False)
                    
                    success, error = send_email_with_retry(
                        subject=customer_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email],
                        body=ai_result.ai_response,
                        record_type='inquiry',
                        record_id=str(inquiry.id) if hasattr(inquiry, 'id') else None
                    )
                    
                    if success:
                        response_sent = True
                        inquiry.response_sent = True
                        inquiry.response_sent_at = datetime.utcnow()
                        inquiry.response_email_subject = customer_subject
                        print(f"✅ 관련 없는 문의에 간략한 회신 발송 완료: {email}")
                    else:
                        print(f"❌ 관련 없는 문의 회신 발송 오류: {error}")
                # 관리자 알림 없음
            # 정상적인 문의인 경우: 고객 응답 + 관리자 알림
            elif not ai_result.is_spam:
                # 1. 고객에게 AI 응답 전송
                if ai_result.ai_response:
                    customer_subject = _get_customer_subject(ai_result.detected_language, selected_service_name, is_booking=False)
                    
                    success, error = send_email_with_retry(
                        subject=customer_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=[email],
                        body=ai_result.ai_response,
                        record_type='inquiry',
                        record_id=str(inquiry.id) if hasattr(inquiry, 'id') else None
                    )
                    
                    if success:
                        response_sent = True
                        inquiry.response_sent = True
                        inquiry.response_sent_at = datetime.utcnow()
                        inquiry.response_email_subject = customer_subject
                        print(f"✅ 문의 고객 응답 이메일 발송 완료: {email}")
                    else:
                        print(f"❌ 문의 고객 응답 이메일 발송 오류: {error}")
                
                # 2. 관리자에게 전체 내용 전송
                admin_subject = f"[스타일그래퍼 문의] {selected_service_name} - {name}님 ({ai_result.detected_language.upper()})"
                
                admin_body = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📧 스타일그래퍼 새 문의 알림
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

■ 문의자 정보
• 이름: {name}
• 휴대폰: {contact_phone}
• 이메일: {email}

■ 문의 서비스
• {selected_service_name}

■ AI 분석 결과
• 감지된 언어: {ai_result.detected_language}
• 감성: {ai_result.sentiment} ({ai_result.sentiment_detail})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 문의 원문
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 메시지 한국어 번역 (원문이 한국어가 아닌 경우)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.translated_message if ai_result.detected_language != 'ko' else '(원문이 한국어입니다)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI 자동 응답 원문 (고객에게 발송됨)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.ai_response if ai_result.ai_response else '(AI 응답 생성 실패)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 AI 응답 한국어 번역 (원문이 한국어가 아닌 경우)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ai_result.translated_ai_response if ai_result.detected_language != 'ko' else '(원문이 한국어입니다)'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 메일은 스타일그래퍼 홈페이지에서 자동으로 발송되었습니다.
"""
                
                inquiry_recipients = AdminNotificationEmail.get_active_emails('inquiries')
                if not inquiry_recipients:
                    AdminNotificationEmail.initialize_default()
                    inquiry_recipients = AdminNotificationEmail.get_active_emails('inquiries')
                
                if inquiry_recipients:
                    success, error = send_email_with_retry(
                        subject=admin_subject,
                        sender=current_app.config['MAIL_DEFAULT_SENDER'],
                        recipients=inquiry_recipients,
                        body=admin_body,
                        reply_to=email,
                        record_type='inquiry',
                        record_id=str(inquiry.id) if hasattr(inquiry, 'id') else None
                    )
                    
                    if success:
                        email_sent = True
                        admin_notified = True
                        inquiry.admin_notified = True
                        print(f"✅ 문의 관리자 알림 이메일 발송 완료: {', '.join(inquiry_recipients)}")
                    else:
                        print(f"❌ 문의 관리자 알림 이메일 발송 오류: {error}")
                else:
                    print("⚠️ 문의 알림을 받을 이메일이 없습니다.")
            
            inquiry.save()
        
        # 성공 메시지 플래시
        flash(_('이메일이 정상 접수되었습니다. 먼저 담당 AI 에이전트가 바로 회신해드립니다. 추가 확인이나 안내가 필요한 경우 24시간 이내에 저희 담당자가 별도로 응대해드립니다. 감사합니다.'))
        return redirect(url_for('main.contact'))
    
    # GET 요청 처리 - 계층적 서비스 목록 생성
    all_services = get_all_services()
    
    # 기본 선택값 처리 (직전에 보던 서비스/옵션 페이지 기반)
    selected_service_id = request.args.get('service_id')
    selected_option_id = request.args.get('option_id')
    
    # 요청 유형 모드 처리 (inquiry 또는 booking)
    default_mode = request.args.get('mode', 'inquiry')
    
    default_selection = None
    if selected_option_id:
        default_selection = f'option_{selected_option_id}'
    elif selected_service_id:
        service = Service.get_by_id(selected_service_id)
        if service and service.options:
            default_selection = f'option_{service.options[0].id}'
        else:
            default_selection = f'service_{selected_service_id}'
        
    return render_template('booking.html', 
                         all_services=all_services, 
                         default_selection=default_selection,
                         default_mode=default_mode)


@main.route('/ask', methods=['GET', 'POST'])
def ask():
    """문의 페이지 - /contact로 리다이렉트 (통합됨)"""
    # 기존 링크 호환성을 위해 /contact로 리다이렉트
    return redirect(url_for('main.contact'))


def _get_customer_subject(language: str, service_name: str, is_booking: bool = False) -> str:
    """언어별 고객 응답 이메일 제목 생성"""
    if is_booking:
        subjects = {
            'ko': f'[스타일그래퍼] {service_name} 예약 문의 답변드립니다',
            'en': f'[Stylegrapher] Response to your {service_name} booking request',
            'ja': f'[スタイルグラファー] {service_name}のご予約に関するご回答',
            'zh': f'[Stylegrapher] 关于{service_name}预约的回复'
        }
    else:
        subjects = {
            'ko': f'[스타일그래퍼] {service_name} 문의 답변드립니다',
            'en': f'[Stylegrapher] Response to your {service_name} inquiry',
            'ja': f'[スタイルグラファー] {service_name}に関するお問い合わせへの回答',
            'zh': f'[Stylegrapher] 关于{service_name}咨询的回复'
        }
    return subjects.get(language, subjects['ko'])


# 서비스 카테고리별 라우트
@main.route('/ai-analysis')
def ai_analysis():
    return redirect(url_for('main.service_option_detail', id=1))


@main.route('/styling-consulting')
def styling_consulting():
    return redirect(url_for('main.service_option_detail', id=3))


@main.route('/oneday-styling')
def oneday_styling():
    return redirect(url_for('main.service_option_detail', id=7))


@main.route('/photo-profile')
def photo_profile():
    return redirect(url_for('main.service_option_detail', id=10))


# 새로운 페이지 라우트
@main.route('/customer-story')
def customer_story():
    return render_template('customer_story.html')


@main.route('/commercial-portfolio')
def commercial_portfolio():
    return render_template('commercial_portfolio.html')


@main.route('/about')
def about():
    about_content = AboutContent.get_current_content()
    return render_template('about.html', about_content=about_content)


@main.route('/terms-of-service')
def terms_of_service():
    terms = TermsOfService.get_current_content()
    
    # 서비스별 환불 조건 표시를 위한 데이터
    lang = get_current_language()
    services = Service.query_all()
    service_options = ServiceOption.query_all()
    
    # 서비스 옵션의 번역된 데이터 준비
    refund_policies = []
    for option in service_options:
        # 환불 정책이 있는 옵션만 포함
        if (option.refund_policy_text and option.refund_policy_text.strip()) or \
           (option.refund_policy_table and option.refund_policy_table.strip()):
            translated = get_translated_service_option(option, lang)
            service = option.service
            service_translated = get_translated_service(service, lang) if service else None
            
            refund_policies.append({
                'option': option,
                'translated': translated,
                'service_name': service_translated.get('name', service.name) if service_translated else (service.name if service else ''),
                'option_name': translated.get('name', option.name),
                'refund_policy_text': translated.get('refund_policy_text', option.refund_policy_text),
                'refund_policy_table': translated.get('refund_policy_table', option.refund_policy_table)
            })
    
    return render_template('terms_of_service.html', terms=terms, refund_policies=refund_policies)


@main.route('/privacy-policy')
def privacy_policy():
    policy = PrivacyPolicy.get_current_content()
    return render_template('privacy_policy.html', policy=policy)

