"""
Main 라우트 - MongoDB 기반
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file, make_response, session
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
    TermsOfService, PrivacyPolicy, get_next_id
)
from utils.translation_helper import (
    get_current_language, 
    get_translated_service, 
    get_translated_service_option,
    get_translated_collage_text,
    get_translated_gallery_group
)
from utils.gridfs_helper import get_image_from_gridfs, get_mongo_connection
from extensions import mail

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

# 간단한 메모리 캐시 구현
_cache = {}
_cache_timestamps = {}


def cache_with_timeout(timeout_minutes=30):
    """메모리 캐시 데코레이터 (언어별 캐싱 지원)"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 언어 설정을 캐시 키에 포함하여 다국어 지원
            current_lang = session.get('lang', 'ko')
            cache_key = f"{func.__name__}:{current_lang}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            if cache_key in _cache_timestamps:
                if datetime.now() - _cache_timestamps[cache_key] < timedelta(minutes=timeout_minutes):
                    return _cache[cache_key]
            
            result = func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_timestamps[cache_key] = datetime.now()
            
            return result
        return wrapper
    return decorator


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


def get_all_services():
    """모든 서비스와 서비스 옵션을 가져와서 통합 목록 생성"""
    services = Service.query_all()
    service_options = ServiceOption.query_all()
    
    all_services = []
    
    for option in service_options:
        all_services.append({
            'type': 'option',
            'id': f'option_{option.id}',
            'name': option.name,
            'category': option.service.name if option.service else '기타'
        })
    
    for service in services:
        if not service.options:
            all_services.append({
                'type': 'service',
                'id': f'service_{service.id}',
                'name': service.name,
                'category': '기타'
            })
    
    all_services.sort(key=lambda x: (x['category'], x['name']))
    return all_services


@main.route('/')
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
    
    return render_template('index.html', 
                         recent_galleries=recent_galleries,
                         preview_galleries=preview_galleries,
                         translated_recent=translated_recent,
                         translated_preview=translated_preview,
                         services=services,
                         fade_texts=fade_texts)


@main.route('/services')
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
def service_option_detail(id):
    service_option = ServiceOption.get_or_404(id)
    
    lang = get_current_language()
    translated = get_translated_service_option(service_option, lang)
    
    details = translated.get('details', [])
    packages = translated.get('packages', [])
    
    return render_template('service_option_detail.html', 
                         service_option=service_option,
                         translated=translated,
                         details=details,
                         packages=packages)


@main.route('/image/<path:image_path>')
def serve_image(image_path):
    """GridFS 및 레거시 저장소에서 이미지를 효율적으로 서빙하는 라우트"""
    try:
        # 1. GridFS에서 이미지 조회 시도
        try:
            binary_data, content_type = get_image_from_gridfs(image_path)
            if binary_data:
                response = make_response(binary_data)
                response.headers['Content-Type'] = content_type
                response.headers['Cache-Control'] = 'public, max-age=86400'
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
                response.headers['Cache-Control'] = 'public, max-age=86400'
                return response
        except Exception as mongo_error:
            print(f"레거시 MongoDB 조회 중 오류: {str(mongo_error)}")
        
        # 3. 파일 시스템에서 서빙
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
        if os.path.exists(file_path):
            return send_file(file_path)
        
        return "Image not found", 404
        
    except Exception as e:
        print(f"이미지 서빙 오류: {str(e)}")
        return "Image serving error", 500


@main.route('/gallery')
@main.route('/gallery/<int:page>')
@cache_with_timeout(15)
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


@main.route('/contact', methods=['GET', 'POST'])
def contact():
    selected_service_id = request.args.get('service_id', None)
    services = Service.query_all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        contact = request.form.get('contact')
        email = request.form.get('email')
        service_id = request.form.get('service')
        message = request.form.get('message')
        
        # 희망 예약일시 처리
        dates = request.form.getlist('date[]')
        times = request.form.getlist('time[]')
        datetime_message = "희망 예약일시:\n"
        
        for i, (date, time) in enumerate(zip(dates, times), 1):
            if date and time:
                datetime_message += f"{i}순위: {date} {time}\n"
        
        full_message = f"{message}\n\n{datetime_message}"
        
        # MongoDB에 예약 저장
        booking = Booking(
            name=name,
            email=email,
            service_id=int(service_id) if service_id else None,
            message=full_message,
            status='대기'
        )
        booking.save()
        
        flash('예약 신청이 잘 전달됐습니다. 스타일그래퍼 담당자가 곧 연락 드리겠습니다. 감사합니다.')
        return redirect(url_for('main.contact'))
        
    return render_template('booking.html', 
                         services=services, 
                         selected_service_id=selected_service_id)


@main.route('/ask', methods=['GET', 'POST'])
def ask():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        selected_service = request.form.get('service')
        message = request.form.get('message')
        
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
        
        enhanced_message = f"[문의 대상: {selected_service_name}]\n\n{message}"
        
        # MongoDB에 문의 저장
        inquiry = Inquiry(
            name=name,
            phone=phone,
            email=email,
            service_id=actual_service_id,
            message=enhanced_message
        )
        inquiry.save()
        
        # 이메일 발송
        email_sent = False
        try:
            subject = f"[스타일그래퍼 문의] {selected_service_name} 관련 문의"
            
            email_body = f"""
스타일그래퍼 홈페이지에서 새로운 문의가 접수되었습니다.

■ 문의자 정보
• 이름: {name}
• 휴대폰: {phone}
• 이메일: {email}

■ 문의 서비스
• {selected_service_name}

■ 문의 내용
{message}

---
이 메일은 스타일그래퍼 홈페이지에서 자동으로 발송되었습니다.
            """
            
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=['stylegrapher.ysg@gmail.com'],
                body=email_body,
                reply_to=email
            )
            
            mail.send(msg)
            email_sent = True
            
        except Exception as e:
            print(f"이메일 발송 오류: {str(e)}")
        
        return render_template('ask.html', 
                             all_services=get_all_services(),
                             show_success_modal=True,
                             email_sent=email_sent)
    
    all_services = get_all_services()
    
    selected_service_id = request.args.get('service_id')
    selected_option_id = request.args.get('option_id')
    
    default_selection = None
    if selected_option_id:
        default_selection = f'option_{selected_option_id}'
    elif selected_service_id:
        service = Service.get_by_id(selected_service_id)
        if service and service.options:
            default_selection = f'option_{service.options[0].id}'
        else:
            default_selection = f'service_{selected_service_id}'
    
    return render_template('ask.html', 
                         all_services=all_services, 
                         default_selection=default_selection)


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
    return render_template('about.html')


@main.route('/terms-of-service')
def terms_of_service():
    terms = TermsOfService.get_current_content()
    return render_template('terms_of_service.html', terms=terms)


@main.route('/privacy-policy')
def privacy_policy():
    policy = PrivacyPolicy.get_current_content()
    return render_template('privacy_policy.html', policy=policy)
