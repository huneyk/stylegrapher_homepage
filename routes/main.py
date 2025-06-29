from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_mail import Message
from models import Service, ServiceOption, Gallery, Booking, CarouselItem, GalleryGroup, CollageText, Inquiry
from extensions import db, mail
import json
from sqlalchemy import desc
from sqlalchemy.sql import text
import os
import io
from PIL import Image
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

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

@main.route('/')
def index():
    # 모든 갤러리 그룹을 최신순으로 가져오기
    all_galleries = GalleryGroup.query.order_by(desc(GalleryGroup.created_at)).all()
    
    # 상위 3개는 collage용
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

@main.route('/gallery')
@main.route('/gallery/<int:page>')
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
        
        # SQL에서 갤러리 그룹 조회
        result = db.session.execute(text("""
            SELECT id, title, created_at
            FROM gallery_group
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """), {"limit": per_page, "offset": (page - 1) * per_page})
        
        # 갤러리 그룹 목록으로 변환
        gallery_groups = []
        for row in result:
            group_data = {
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'images': []
            }
            
            # SQL에서 각 그룹의 이미지 기본 정보 조회
            image_result = db.session.execute(text("""
                SELECT id, image_path, "order"
                FROM gallery
                WHERE group_id = :group_id
                ORDER BY "order"
            """), {'group_id': group_data['id']})
            
            for img_row in image_result:
                image_data = {
                    'id': img_row[0],
                    'image_path': img_row[1],
                    'order': img_row[2]
                }
                
                # MongoDB에서 이미지 확인
                mongodb_working = True
                if images_collection is not None:
                    try:
                        image_doc = images_collection.find_one({'_id': image_data['image_path']})
                        if not image_doc:
                            # MongoDB에 없는 이미지는 동적으로 MongoDB에 업로드 시도
                            try:
                                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_data['image_path'])
                                if os.path.exists(file_path):
                                    # 이미지 타입 결정
                                    content_type = 'image/jpeg'  # 기본값
                                    if image_data['image_path'].lower().endswith('.png'):
                                        content_type = 'image/png'
                                    elif image_data['image_path'].lower().endswith('.gif'):
                                        content_type = 'image/gif'
                                    
                                    # 이미지 읽기 및 리사이징
                                    with Image.open(file_path) as img:
                                        resized_img = resize_image_memory(img, width=1080)
                                        buffer = io.BytesIO()
                                        resized_img.save(buffer, format=img.format or 'JPEG', quality=95, optimize=True)
                                        img_binary = buffer.getvalue()
                                    
                                    # MongoDB에 저장
                                    new_doc = {
                                        '_id': image_data['image_path'],  # 기존 파일명을 ID로 사용
                                        'filename': image_data['image_path'],
                                        'content_type': content_type,
                                        'binary_data': img_binary,
                                        'group_id': group_data['id'],
                                        'order': image_data['order'],
                                        'created_at': datetime.now()
                                    }
                                    images_collection.insert_one(new_doc)
                                    print(f"이미지를 MongoDB에 자동 업로드: {image_data['image_path']}")
                            except Exception as upload_error:
                                print(f"이미지 자동 업로드 실패: {str(upload_error)}")
                    except Exception as mongo_error:
                        print(f"MongoDB 조회 중 오류 발생: {str(mongo_error)}")
                        mongodb_working = False
                
                group_data['images'].append(image_data)
            
            gallery_groups.append(group_data)
        
        if request.headers.get('HX-Request'):
            # HTMX 요청인 경우 갤러리 아이템만 반환
            return render_template('_gallery_items.html', 
                                gallery_groups=gallery_groups,
                                has_more=has_more,
                                next_page=next_page)
        
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
        
        # 데이터베이스에 저장
        inquiry = Inquiry(
            name=name,
            phone=phone,
            email=email,
            service_id=actual_service_id,
            message=enhanced_message
        )
        db.session.add(inquiry)
        db.session.commit()
        
        # 이메일 발송
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
                recipients=['stylegrapher.ysg@gmail.com'],
                body=email_body,
                reply_to=email  # 답장시 문의자 이메일로 가도록 설정
            )
            
            # 메일 발송
            mail.send(msg)
            
            flash('문의가 성공적으로 접수되었습니다. 담당자가 빠른 시일 내에 연락드리겠습니다.', 'success')
            
        except Exception as e:
            print(f"이메일 발송 오류: {str(e)}")
            flash('문의는 접수되었으나 이메일 발송에 문제가 발생했습니다. 직접 연락 부탁드립니다.', 'warning')
        
        return redirect(url_for('main.index'))
    
    # 모든 서비스와 서비스 옵션을 가져와서 통합 목록 생성
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