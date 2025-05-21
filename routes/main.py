from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from models import Service, Gallery, Booking, CarouselItem, GalleryGroup, CollageText, Inquiry
from extensions import db
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
    services = Service.query.all()
    return render_template('services.html', services=services)

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
        inquiry = Inquiry(
            name=request.form.get('name'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            service_id=request.form.get('service'),
            message=request.form.get('message')
        )
        db.session.add(inquiry)
        db.session.commit()
        
        return redirect(url_for('main.index'))
    
    services = Service.query.all()
    return render_template('ask.html', services=services) 