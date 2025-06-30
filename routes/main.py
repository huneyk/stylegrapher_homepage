from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file, make_response
from flask_mail import Message
from models import Service, ServiceOption, Gallery, Booking, GalleryGroup, CollageText, Inquiry
from extensions import db, mail
import json
from sqlalchemy import desc, asc
from sqlalchemy.sql import text
import os
import io
from PIL import Image
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import functools
import hashlib

# MongoDB 설정 불러오기
load_dotenv()
mongo_uri = os.environ.get('MONGO_URI')
if mongo_uri:
    try:
        print(f"main.py: MongoDB에 연결 시도: {mongo_uri}")
        # 향상된 연결 설정 - 타임아웃 증가 및 retryWrites 활성화
        mongo_client = MongoClient(
            mongo_uri, 
            serverSelectionTimeoutMS=30000,  # 30초로 증가
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
            retryWrites=True,
            retryReads=True,
            w='majority',  # 다수의 노드에 쓰기 확인
            readPreference='primaryPreferred'  # 프라이머리 선호, 없으면 세컨더리로 전환
        )
        # 연결 테스트
        mongo_client.server_info()
        print("main.py: MongoDB 연결 성공!")
        mongo_db = mongo_client['STG-DB']
        images_collection = mongo_db['gallery']
        print(f"main.py: MongoDB 데이터베이스 '{mongo_db.name}' 및 컬렉션 '{images_collection.name}' 사용 준비 완료")
    except Exception as e:
        print(f"main.py: MongoDB 연결 오류: {str(e)}")
        mongo_client = None
        mongo_db = None
        images_collection = None
else:
    print("main.py: MONGO_URI 환경 변수가 설정되지 않았습니다!")
    mongo_client = None
    mongo_db = None
    images_collection = None

# 이미지 리사이징 함수
def resize_image_memory(img, width=1080):
    """
    메모리 상의 이미지를 리사이즈하는 함수
    width: 타겟 너비 (픽셀)
    """
    # 원본 크기 저장
    original_width, original_height = img.size
    
    # 너비를 지정된 픽셀로 고정하고 비율 유지
    ratio = width / original_width
    target_height = int(original_height * ratio)
    
    # 이미지 리사이즈
    resized_img = img.resize((width, target_height), Image.Resampling.LANCZOS)
    
    return resized_img

# Create the Blueprint object
main = Blueprint('main', __name__)

# 간단한 메모리 캐시 구현
_cache = {}
_cache_timestamps = {}

def cache_with_timeout(timeout_minutes=30):
    """메모리 캐시 데코레이터"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # 캐시 만료 시간 확인
            if cache_key in _cache_timestamps:
                if datetime.now() - _cache_timestamps[cache_key] < timedelta(minutes=timeout_minutes):
                    return _cache[cache_key]
            
            # 캐시 미스 또는 만료된 경우 실행
            result = func(*args, **kwargs)
            _cache[cache_key] = result
            _cache_timestamps[cache_key] = datetime.now()
            
            return result
        return wrapper
    return decorator

def process_missing_images_background(missing_images):
    """백그라운드에서 누락된 이미지들을 MongoDB에 업로드"""
    if not images_collection:
        return
    
    for image_path in missing_images:
        try:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
            if os.path.exists(file_path):
                # 이미지 타입 결정
                content_type = 'image/jpeg'
                if image_path.lower().endswith('.png'):
                    content_type = 'image/png'
                elif image_path.lower().endswith('.gif'):
                    content_type = 'image/gif'
                
                # 이미지 리사이징 (더 작은 크기로)
                with Image.open(file_path) as img:
                    # 썸네일 생성 (600px 너비로 축소)
                    resized_img = resize_image_memory(img, width=600)
                    buffer = io.BytesIO()
                    resized_img.save(buffer, format='JPEG', quality=85, optimize=True)
                    img_binary = buffer.getvalue()
                
                # MongoDB에 저장
                new_doc = {
                    '_id': image_path,
                    'filename': image_path,
                    'content_type': content_type,
                    'binary_data': img_binary,
                    'created_at': datetime.now(),
                    'optimized': True
                }
                
                # 중복 체크 후 삽입
                if not images_collection.find_one({'_id': image_path}):
                    images_collection.insert_one(new_doc)
                    print(f"백그라운드에서 이미지 처리 완료: {image_path}")
                    
        except Exception as e:
            print(f"백그라운드 이미지 처리 실패 {image_path}: {str(e)}")

def get_all_services():
    """모든 서비스와 서비스 옵션을 가져와서 통합 목록 생성"""
    services = Service.query.all()
    service_options = ServiceOption.query.all()
    
    # 통합 서비스 목록 생성 (개별 서비스 옵션 위주로)
    all_services = []
    
    # ServiceOption들 추가
    for option in service_options:
        all_services.append({
            'type': 'option',
            'id': f'option_{option.id}',
            'name': option.name,
            'category': option.service.name if option.service else '기타'
        })
    
    # Service들도 추가 (ServiceOption이 없는 경우를 위해)
    for service in services:
        if not service.options:  # 옵션이 없는 서비스만 추가
            all_services.append({
                'type': 'service',
                'id': f'service_{service.id}',
                'name': service.name,
                'category': '기타'
            })
    
    # 카테고리별로 정렬
    all_services.sort(key=lambda x: (x['category'], x['name']))
    return all_services

@main.route('/')
def index():
    # 갤러리 그룹을 상단 고정, 표출 순서, 생성일 순으로 가져오기
    all_galleries = GalleryGroup.query.order_by(
        desc(GalleryGroup.is_pinned),
        desc(GalleryGroup.display_order), 
        desc(GalleryGroup.created_at)
    ).all()
    
    # 상위 3개는 collage용 (상단 고정된 갤러리가 우선)
    recent_galleries = all_galleries[:3] if all_galleries else []
    
    # 4-6번째는 하단 갤러리용
    preview_galleries = all_galleries[3:6] if len(all_galleries) > 3 else []
    
    services = Service.query.all()
    
    # 디버깅을 위한 출력
    print(f"Total galleries: {len(all_galleries)}")
    print(f"Recent galleries: {len(recent_galleries)}")
    print(f"Preview galleries: {len(preview_galleries)}")
    
    return render_template('index.html', 
                         recent_galleries=recent_galleries,
                         preview_galleries=preview_galleries,
                         services=services)

@main.route('/services')
def services():
    # 카테고리별로 서비스와 옵션을 그룹화
    categories_data = {
        'ai_analysis': {
            'title': 'STG AI 분석',
            'description': '인공지능을 활용한 정밀 스타일 분석',
            'icon': 'bi-cpu',
            'color': '#6f42c1',
            'services': []
        },
        'consulting': {
            'title': '스타일링 컨설팅',
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
            'title': '화보 & 프로필',
            'description': '특별한 순간을 기록하는 전문 촬영',
            'icon': 'bi-camera',
            'color': '#fd7e14',
            'services': []
        }
    }
    
    # 모든 서비스와 옵션 조회
    services = Service.query.all()
    for service in services:
        if service.category and service.category in categories_data:
            categories_data[service.category]['services'].append(service)
    
    return render_template('services_new.html', categories_data=categories_data)

@main.route('/service/<int:id>')
def service_detail(id):
    service = Service.query.get_or_404(id)
    # JSON 문자열을 파이썬 객체로 변환
    details = json.loads(service.details) if service.details else []
    packages = json.loads(service.packages) if service.packages else []
    return render_template('service_detail.html', 
                         service=service, 
                         details=details,
                         packages=packages)

@main.route('/service_option/<int:id>')
def service_option_detail(id):
    service_option = ServiceOption.query.get_or_404(id)
    
    # JSON 문자열을 파이썬 객체로 변환
    details = json.loads(service_option.details) if service_option.details else []
    packages = json.loads(service_option.packages) if service_option.packages else []
    
    return render_template('service_option_detail.html', 
                         service_option=service_option, 
                         details=details,
                         packages=packages)

@main.route('/image/<path:image_path>')
def serve_image(image_path):
    """이미지를 효율적으로 서빙하는 라우트"""
    try:
        print(f"이미지 요청: {image_path}")
        
        # MongoDB에서 이미지 조회
        if images_collection is not None:
            image_doc = images_collection.find_one({'_id': image_path})
            if image_doc and 'binary_data' in image_doc:
                print(f"MongoDB에서 이미지 발견: {image_path} (크기: {len(image_doc['binary_data'])} bytes)")
                response = make_response(image_doc['binary_data'])
                response.headers['Content-Type'] = image_doc.get('content_type', 'image/jpeg')
                response.headers['Cache-Control'] = 'public, max-age=86400'  # 1일 캐시
                return response
            else:
                print(f"MongoDB에서 이미지 없음: {image_path}")
        
        # MongoDB에 없으면 파일 시스템에서 서빙
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
        print(f"파일 시스템에서 확인: {file_path}")
        if os.path.exists(file_path):
            print(f"파일 시스템에서 이미지 발견: {image_path}")
            return send_file(file_path)
        
        # 이미지가 없으면 404
        print(f"이미지를 찾을 수 없음: {image_path}")
        return "Image not found", 404
        
    except Exception as e:
        print(f"이미지 서빙 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Image serving error", 500

@main.route('/gallery')
@main.route('/gallery/<int:page>')
@cache_with_timeout(15)  # 15분 캐시
def gallery(page=1):
    try:
        per_page = 9  # 페이지당 갤러리 그룹 수
        
        # 갤러리 그룹 총 개수 조회
        result = db.session.execute(text("SELECT COUNT(*) FROM gallery_group"))
        total_groups = result.scalar()
        
        # 페이지네이션 정보
        total_pages = (total_groups + per_page - 1) // per_page
        has_more = page < total_pages
        next_page = page + 1 if has_more else None
        
        # 최적화된 쿼리: 갤러리 그룹과 이미지를 한 번에 조회 (상단 고정 및 표출 순서 반영)
        result = db.session.execute(text("""
            SELECT 
                gg.id as group_id, 
                gg.title, 
                gg.created_at,
                gg.is_pinned,
                gg.display_order,
                g.id as image_id,
                g.image_path,
                g."order"
            FROM gallery_group gg
            LEFT JOIN gallery g ON gg.id = g.group_id
            WHERE gg.id IN (
                SELECT id FROM gallery_group 
                ORDER BY is_pinned DESC, display_order DESC, created_at DESC 
                LIMIT :limit OFFSET :offset
            )
            ORDER BY gg.is_pinned DESC, gg.display_order DESC, gg.created_at DESC, g."order"
        """), {"limit": per_page, "offset": (page - 1) * per_page})
        
        # 그룹별로 데이터 정리
        groups_dict = {}
        for row in result:
            group_id = row[0]
            if group_id not in groups_dict:
                groups_dict[group_id] = {
                    'id': group_id,
                    'title': row[1],
                    'created_at': row[2],
                    'is_pinned': bool(row[3]) if row[3] is not None else False,
                    'display_order': row[4] if row[4] is not None else 0,
                    'images': []
                }
            
            # 이미지가 있는 경우에만 추가
            if row[5] is not None:  # image_id가 None이 아닌 경우
                groups_dict[group_id]['images'].append({
                    'id': row[5],
                    'image_path': row[6],
                    'order': row[7]
                })
        
        # 리스트로 변환 (생성일 기준 정렬 유지)
        gallery_groups = list(groups_dict.values())
        
        # MongoDB 이미지 존재 여부 일괄 확인 (성능 최적화)
        if images_collection is not None and gallery_groups:
            try:
                # 모든 이미지 경로 수집
                all_image_paths = []
                for group in gallery_groups:
                    for image in group['images']:
                        all_image_paths.append(image['image_path'])
                
                if all_image_paths:
                    # 한 번의 쿼리로 모든 이미지 존재 여부 확인
                    existing_images = images_collection.find(
                        {'_id': {'$in': all_image_paths}}, 
                        {'_id': 1}
                    )
                    existing_image_set = {doc['_id'] for doc in existing_images}
                    
                    # 없는 이미지들을 백그라운드에서 처리
                    missing_images = set(all_image_paths) - existing_image_set
                    if missing_images:
                        print(f"MongoDB에 없는 이미지 {len(missing_images)}개 발견 (백그라운드에서 처리 시작)")
                        # 별도 스레드에서 처리 (non-blocking)
                        import threading
                        thread = threading.Thread(
                            target=process_missing_images_background, 
                            args=(list(missing_images),)
                        )
                        thread.daemon = True
                        thread.start()
                        
            except Exception as mongo_error:
                print(f"MongoDB 일괄 조회 중 오류 발생: {str(mongo_error)}")
        
        if request.headers.get('HX-Request'):
            # HTMX 요청인 경우 갤러리 아이템과 버튼 업데이트를 함께 반환
            gallery_items_html = render_template('_gallery_items.html', 
                                gallery_groups=gallery_groups)
            
            # 버튼 섹션 업데이트용 HTML
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
            
            # 갤러리 아이템과 버튼을 함께 반환
            response_html = gallery_items_html + f'<div id="load-more-section" hx-swap-oob="true">{button_html}</div>'
            return response_html
        
        # 일반 요청인 경우 전체 페이지 반환
        return render_template('gallery.html', 
                              gallery_groups=gallery_groups, 
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
        # 갤러리 그룹 조회
        gallery_group = GalleryGroup.query.get_or_404(group_id)
        print(f"갤러리 그룹 {group_id} 조회 성공: {gallery_group.title}")
        
        # 해당 그룹의 모든 이미지를 순서대로 조회
        gallery_images = Gallery.query.filter_by(group_id=group_id)\
                                     .order_by(Gallery.order.asc(), Gallery.id.asc()).all()
        
        print(f"갤러리 그룹 {group_id}의 이미지 수: {len(gallery_images)}")
        for i, img in enumerate(gallery_images):
            print(f"  이미지 {i+1}: {img.image_path}")
        
        return render_template('gallery_detail.html', 
                             gallery_group=gallery_group,
                             gallery_images=gallery_images)
                             
    except Exception as e:
        print(f"Error in gallery_detail route: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('갤러리를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('main.gallery'))

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    selected_service_id = request.args.get('service_id', None)
    services = Service.query.all()
    
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
        
        booking = Booking(
            name=name,
            email=email,
            service_id=service_id,
            message=full_message,
            status='대기'
        )
        db.session.add(booking)
        db.session.commit()
        
        flash('예약 신청이 잘 전달됐습니다. 스타일그래퍼 담당자가 곧 연락 드리겠습니다. 감사합니다.')
        return redirect(url_for('main.contact'))
        
    return render_template('booking.html', 
                         services=services, 
                         selected_service_id=selected_service_id)

@main.route('/ask', methods=['GET', 'POST'])
def ask():
    if request.method == 'POST':
        # 폼 데이터 수집
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        selected_service = request.form.get('service')
        message = request.form.get('message')
        
        # 선택된 서비스 정보 파싱
        service_type, service_db_id = selected_service.split('_', 1)
        service_db_id = int(service_db_id)
        
        # 실제 service_id와 선택된 서비스/옵션 이름 확인
        if service_type == 'option':
            service_option = ServiceOption.query.get(service_db_id)
            actual_service_id = service_option.service_id
            selected_service_name = service_option.name
        else:  # service_type == 'service'
            service = Service.query.get(service_db_id)
            actual_service_id = service.id
            selected_service_name = service.name
        
        # 메시지에 선택된 서비스 정보 추가
        enhanced_message = f"[문의 대상: {selected_service_name}]\n\n{message}"
        
        # SQLite 데이터베이스에 저장
        inquiry = Inquiry(
            name=name,
            phone=phone,
            email=email,
            service_id=actual_service_id,
            message=enhanced_message
        )
        db.session.add(inquiry)
        db.session.commit()
        
        # MongoDB에도 저장
        if mongo_db is not None:
            try:
                inquiry_doc = {
                    'name': name,
                    'phone': phone,
                    'email': email,
                    'service_id': actual_service_id,
                    'service_name': selected_service_name,
                    'service_type': service_type,
                    'message': message,
                    'enhanced_message': enhanced_message,
                    'created_at': datetime.now(),
                    'status': 'new'
                }
                inquiries_collection = mongo_db['inquiries']
                inquiries_collection.insert_one(inquiry_doc)
                print(f"MongoDB에 문의사항 저장 완료: {name}")
            except Exception as mongo_error:
                print(f"MongoDB 저장 오류: {str(mongo_error)}")
        
        # 이메일 발송
        email_sent = False
        try:
            # 관리자에게 보낼 이메일 내용
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
문의자에게 답변을 드리시기 바랍니다.
            """
            
            # 메일 메시지 생성
            msg = Message(
                subject=subject,
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=['stylegrapher.ysg@gmail.com'],
                body=email_body,
                reply_to=email  # 답장시 문의자 이메일로 가도록 설정
            )
            
            # 메일 발송
            mail.send(msg)
            email_sent = True
            print(f"이메일 발송 성공: {subject}")
            
        except Exception as e:
            print(f"이메일 발송 오류: {str(e)}")
        
        # 성공 시 현재 페이지에서 모달 표시
        return render_template('ask.html', 
                             all_services=get_all_services(),
                             show_success_modal=True,
                             email_sent=email_sent)
    
    # 모든 서비스와 서비스 옵션을 가져와서 통합 목록 생성
    all_services = get_all_services()
    
    # 이전 페이지에서 온 경우 default 선택을 위한 파라미터들
    selected_service_id = request.args.get('service_id')  # service_detail에서 온 경우
    selected_option_id = request.args.get('option_id')    # service_option_detail에서 온 경우
    
    default_selection = None
    if selected_option_id:
        default_selection = f'option_{selected_option_id}'
    elif selected_service_id:
        # 해당 서비스의 첫 번째 옵션을 찾거나 서비스 자체를 선택
        service = Service.query.get(selected_service_id)
        if service and service.options:
            default_selection = f'option_{service.options[0].id}'
        else:
            default_selection = f'service_{selected_service_id}'
    
    return render_template('ask.html', 
                         all_services=all_services, 
                         default_selection=default_selection)

# 서비스 카테고리별 라우트 - 각 카테고리의 대표 서비스 상세 페이지로 리다이렉트
@main.route('/ai-analysis')
def ai_analysis():
    # STG AI 분석 - AI 얼굴 분석 (Option ID: 1)로 리다이렉트
    return redirect(url_for('main.service_option_detail', id=1))

@main.route('/styling-consulting')
def styling_consulting():
    # 스타일링 컨설팅 - 퍼스널 컬러 진단 (Option ID: 3)으로 리다이렉트
    return redirect(url_for('main.service_option_detail', id=3))

@main.route('/oneday-styling')
def oneday_styling():
    # 원데이 스타일링 - 메이크업 (Option ID: 7)으로 리다이렉트
    return redirect(url_for('main.service_option_detail', id=7))

@main.route('/photo-profile')
def photo_profile():
    # 화보 & 프로필 - 개인화보 (Option ID: 10)으로 리다이렉트
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