from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
from flask_login import login_required, login_user, logout_user
from extensions import db, login_manager
from models import Service, Gallery, User, ServiceOption, Booking, GalleryGroup, Inquiry, CollageText, SiteSettings, TermsOfService, PrivacyPolicy
from werkzeug.utils import secure_filename
import os
from PIL import Image
import json
from sqlalchemy import desc, text
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
import io
import uuid
from pymongo import MongoClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

admin = Blueprint('admin', __name__)

# MongoDB 연결 설정
mongo_uri = os.environ.get('MONGO_URI')
if not mongo_uri:
    print("경고: MONGO_URI 환경 변수가 설정되지 않았습니다!")
    
try:
    print(f"MongoDB에 연결 시도: {mongo_uri}")
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
    print("MongoDB 연결 성공!")
    mongo_db = mongo_client['STG-DB']  # .env의 URI에 맞는 데이터베이스 이름으로 변경
    images_collection = mongo_db['gallery']  # 이미지를 저장할 컬렉션 이름
    print(f"MongoDB 데이터베이스 '{mongo_db.name}' 및 컬렉션 '{images_collection.name}' 사용 준비 완료")
except Exception as e:
    print(f"MongoDB 연결 오류: {str(e)}")
    mongo_client = None
    mongo_db = None
    images_collection = None

@login_manager.user_loader
def load_user(id):
    try:
        # 직접 SQL 쿼리를 사용하여 사용자 조회
        result = db.session.execute(text("SELECT id, uq_user_username, password_hash FROM user WHERE id = :id"), {"id": id})
        user_data = result.fetchone()
        
        if user_data:
            # 사용자 객체 생성
            user = User()
            user.id = user_data[0]
            user.username = user_data[1]
            user.password_hash = user_data[2]
            user.is_admin = True  # 항상 관리자로 설정
            return user
        return None
    except Exception as e:
        print(f"Error loading user: {str(e)}")
        return None

@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # 테이블 구조 확인
            result = db.session.execute(text("PRAGMA table_info(user)"))
            columns = [column[1] for column in result.fetchall()]
            print("User table columns:", columns)
            
            # 기본 쿼리 - id와 password_hash만 사용
            query = "SELECT id, password_hash FROM user WHERE uq_user_username = :username"
            
            # 사용자 조회
            result = db.session.execute(text(query), {"username": username})
            user_data = result.fetchone()
            
            if user_data:
                # 비밀번호 해시 확인
                stored_hash = user_data[1]
                
                # 비밀번호 확인 시도
                password_verified = False
                try:
                    # 기본 방법으로 확인 시도
                    password_verified = check_password_hash(stored_hash, password)
                except Exception as hash_error:
                    print(f"Hash verification error: {str(hash_error)}")
                    
                    # 해시 타입이 scrypt인 경우 (이 부분은 로그인 우회를 위한 임시 조치)
                    if 'scrypt' in stored_hash and password == 'ysg123':
                        print("Using fallback verification for admin user")
                        password_verified = True
                        
                        # 비밀번호 해시 업데이트 (pbkdf2:sha256 사용)
                        update_sql = text("""
                        UPDATE user SET password_hash = :password_hash
                        WHERE id = :id
                        """)
                        update_params = {
                            "id": user_data[0],
                            "password_hash": generate_password_hash('ysg123', method='pbkdf2:sha256')
                        }
                        db.session.execute(update_sql, update_params)
                        db.session.commit()
                        print("Password hash updated to pbkdf2:sha256")
                
                if password_verified:
                    # 사용자 객체 생성
                    user = User()
                    user.id = user_data[0]
                    user.username = username
                    user.password_hash = user_data[1]
                    user.is_admin = True  # 항상 관리자로 설정
                    
                    login_user(user)
                    flash('로그인되었습니다.')
                    return redirect(url_for('admin.dashboard'))
            
            flash('아이디 또는 비밀번호가 올바르지 않습니다.')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('로그인 중 오류가 발생했습니다.')
    
    return render_template('admin/login.html')

@admin.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@admin.route('/dashboard')
@login_required
def dashboard():
    try:
        # 한국 시간대 설정
        kst = pytz.timezone('Asia/Seoul')
        
        # 각 항목 100개씩 가져오기
        # Booking 모델 대신 직접 SQL 쿼리 사용
        result = db.session.execute(text("""
            SELECT b.id, b.name, b.email, b.message, b.status, b.created_at, s.name as service_name
            FROM booking b
            LEFT JOIN service s ON b.service_id = s.id
            ORDER BY b.created_at DESC
            LIMIT 100
        """))
        recent_bookings = []
        for row in result:
            booking_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'message': row[3],
                'status': row[4],
                'created_at': row[5],
                'service': DictAsModel({'name': row[6]}) if row[6] else None
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if booking_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(booking_data['created_at'], datetime):
                        booking_data['created_at'] = pytz.utc.localize(booking_data['created_at']).astimezone(kst)
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(booking_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(booking_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        booking_data['created_at'] = pytz.utc.localize(dt).astimezone(kst)
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    booking_data['created_at'] = datetime.now()
            
            # 딕셔너리를 DictAsModel 객체로 변환
            booking = DictAsModel(booking_data)
            recent_bookings.append(booking)
        
        # Inquiry 모델 대신 직접 SQL 쿼리 사용
        result = db.session.execute(text("""
            SELECT i.id, i.name, i.email, i.phone, i.message, i.status, i.created_at, s.name as service_name
            FROM inquiry i
            LEFT JOIN service s ON i.service_id = s.id
            ORDER BY i.created_at DESC
            LIMIT 100
        """))
        recent_inquiries = []
        for row in result:
            inquiry_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'message': row[4],
                'status': row[5],
                'created_at': row[6],
                'service': DictAsModel({'name': row[7]}) if row[7] else None
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if inquiry_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(inquiry_data['created_at'], datetime):
                        inquiry_data['created_at'] = pytz.utc.localize(inquiry_data['created_at']).astimezone(kst)
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(inquiry_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(inquiry_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        inquiry_data['created_at'] = pytz.utc.localize(dt).astimezone(kst)
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    inquiry_data['created_at'] = datetime.now()
            
            # 딕셔너리를 DictAsModel 객체로 변환
            inquiry = DictAsModel(inquiry_data)
            recent_inquiries.append(inquiry)
        
        # GalleryGroup 모델 대신 직접 SQL 쿼리 사용
        result = db.session.execute(text("""
            SELECT id, title, created_at
            FROM gallery_group
            ORDER BY created_at DESC
            LIMIT 100
        """))
        recent_galleries = []
        for row in result:
            gallery_data = {
                'id': row[0],
                'title': row[1],
                'created_at': row[2]
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if gallery_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(gallery_data['created_at'], datetime):
                        gallery_data['created_at'] = pytz.utc.localize(gallery_data['created_at']).astimezone(kst)
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(gallery_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(gallery_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        gallery_data['created_at'] = pytz.utc.localize(dt).astimezone(kst)
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    gallery_data['created_at'] = datetime.now()
            
            # 딕셔너리를 DictAsModel 객체로 변환
            gallery = DictAsModel(gallery_data)
            recent_galleries.append(gallery)
        
        # 각 항목의 전체 개수 확인
        result = db.session.execute(text("SELECT COUNT(*) FROM booking"))
        total_bookings = result.scalar()
        
        result = db.session.execute(text("SELECT COUNT(*) FROM inquiry"))
        total_inquiries = result.scalar()
        
        result = db.session.execute(text("SELECT COUNT(*) FROM gallery_group"))
        total_galleries = result.scalar()

        # 디버깅을 위한 출력
        print(f"Bookings: {len(recent_bookings)}")
        print(f"Inquiries: {len(recent_inquiries)}")
        print(f"Galleries: {len(recent_galleries)}")

        return render_template('admin/dashboard.html',
                             recent_bookings=recent_bookings,
                             recent_inquiries=recent_inquiries,
                             recent_galleries=recent_galleries,
                             total_bookings=total_bookings,
                             total_inquiries=total_inquiries,
                             total_galleries=total_galleries)
                             
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        flash('데이터를 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/dashboard.html',
                             recent_bookings=[],
                             recent_inquiries=[],
                             recent_galleries=[],
                             total_bookings=0,
                             total_inquiries=0,
                             total_galleries=0)

@admin.route('/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    if request.method == 'POST':
        try:
            # 상세 정보 처리
            details_text = request.form.get('details', '').strip()
            details = [line.strip() for line in details_text.split('\n') if line.strip()] if details_text else []
            
            # 패키지 정보 처리
            packages_text = request.form.get('packages', '').strip()
            packages = []
            if packages_text:
                for line in packages_text.split('\n'):
                    line = line.strip()
                    if line and '|' in line:
                        parts = [part.strip() for part in line.split('|')]
                        if len(parts) >= 4:
                            packages.append({
                                'name': parts[0],
                                'price': parts[1],
                                'duration': parts[2],
                                'description': parts[3]
                            })
            
            # 서비스 생성
            service = Service(
                name=request.form['name'],
                description=request.form['description'],
                category=request.form['category'],
                details=json.dumps(details),
                packages=json.dumps(packages)
            )
            db.session.add(service)
            db.session.commit()
            
            flash('서비스가 성공적으로 추가되었습니다. 이제 개별 옵션을 추가해보세요.')
            return redirect(url_for('admin.list_options', service_id=service.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'서비스 추가 중 오류가 발생했습니다: {str(e)}')
            return redirect(request.url)
    
    return render_template('admin/add_service.html')

@admin.route('/category/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        try:
            # 간단한 카테고리 추가 - 이름과 설명만
            service = Service(
                name=request.form['name'],
                description=request.form['description'],
                category=None,  # 카테고리는 기본값으로 설정
                details=json.dumps([]),  # 빈 리스트
                packages=json.dumps([])  # 빈 리스트
            )
            db.session.add(service)
            db.session.flush()  # ID를 얻기 위해 flush
            
            # 기본 ServiceOption 생성 (카테고리에 서비스가 표시되도록)
            service_option = ServiceOption(
                service_id=service.id,
                name=request.form['name'],
                description=request.form['description'],
                detailed_description='',
                details=json.dumps([]),
                packages=json.dumps([])
            )
            db.session.add(service_option)
            db.session.commit()
            
            flash('새 카테고리가 성공적으로 추가되었습니다.')
            return redirect(url_for('admin.list_services'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'카테고리 추가 중 오류가 발생했습니다: {str(e)}')
            return redirect(request.url)
    
    return render_template('admin/add_category.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def resize_image(image_path, size=(1600, 1200)):
    with Image.open(image_path) as img:
        # 원본 이미지의 비율 계산
        width_ratio = size[0] / img.width
        height_ratio = size[1] / img.height
        
        # 더 작은 비율을 사용하여 aspect ratio 유지
        ratio = min(width_ratio, height_ratio)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        
        # 이미지 리사이즈
        resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 저장
        resized_img.save(image_path, quality=95, optimize=True)

# 이미지 리사이징 및 MongoDB 저장 헬퍼 함수
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

def save_image_to_mongodb(file, group_id=None, order=0):
    """
    파일을 MongoDB에 저장하는 함수
    file: 업로드된 파일 객체
    group_id: 갤러리 그룹 ID (선택적)
    order: 그룹 내 순서 (선택적)
    """
    filename = secure_filename(file.filename)
    
    # 이미지 데이터 읽기
    img_data = file.read()
    
    # 이미지 리사이즈
    img = Image.open(io.BytesIO(img_data))
    resized_img = resize_image_memory(img, width=1080)
    
    # 이미지를 바이트로 변환
    buffer = io.BytesIO()
    resized_img.save(buffer, format=img.format or 'JPEG', quality=95, optimize=True)
    img_binary = buffer.getvalue()
    
    # MongoDB에 이미지 저장
    image_id = str(uuid.uuid4())  # 고유 ID 생성
    image_doc = {
        '_id': image_id,
        'filename': filename,
        'content_type': file.content_type,
        'binary_data': img_binary,
        'created_at': datetime.now()
    }
    
    # 갤러리 그룹 ID가 있는 경우
    if group_id is not None:
        image_doc['group_id'] = group_id
        image_doc['order'] = order
    
    images_collection.insert_one(image_doc)
    return image_id

# 갤러리 이미지 업로드 함수 수정
@admin.route('/gallery/upload', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        if 'images[]' not in request.files:
            flash('이미지를 선택해주세요.')
            return redirect(request.url)
        
        files = request.files.getlist('images[]')
        if len(files) > 10:
            flash('최대 10개의 이미지만 업로드할 수 있습니다.')
            return redirect(request.url)
        
        try:
            # 현재 최고 display_order 값 조회
            max_order_result = db.session.execute(
                text("SELECT MAX(display_order) FROM gallery_group")
            ).scalar()
            next_order = (max_order_result or 0) + 1
            
            # 갤러리 그룹 생성 (새 갤러리가 가장 앞에 배치되도록)
            gallery_group = GalleryGroup(
                title=request.form['title'],
                display_order=next_order
            )
            db.session.add(gallery_group)
            db.session.flush()  # ID 생성을 위해 flush
            
            # MongoDB에 이미지 저장
            for i, file in enumerate(files):
                if file and allowed_file(file.filename):
                    # MongoDB에 이미지 저장 및 ID 반환
                    image_id = save_image_to_mongodb(file, gallery_group.id, i)
                    
                    # 갤러리 이미지 레코드 생성 (경로 대신 MongoDB ID 저장)
                    gallery = Gallery(
                        image_path=image_id,  # MongoDB ID를 저장
                        order=i,
                        group=gallery_group
                    )
                    db.session.add(gallery)
            
            db.session.commit()
            flash('이미지가 업로드되었습니다.')
            return redirect(url_for('admin.list_gallery'))
        except Exception as e:
            db.session.rollback()
            print(f"Error uploading images: {str(e)}")
            flash('이미지 업로드 중 오류가 발생했습니다.', 'error')
            return redirect(request.url)
            
    return render_template('admin/upload_image.html')

@admin.route('/gallery/delete/<int:group_id>')
@login_required
def delete_gallery_group(group_id):
    group = GalleryGroup.query.get_or_404(group_id)
    
    # MongoDB에서 이미지 삭제
    for image in group.images:
        images_collection.delete_one({'_id': image.image_path})
    
    db.session.delete(group)
    db.session.commit()
    flash('갤러리가 삭제되었습니다.')
    return redirect(url_for('admin.list_gallery'))

@admin.route('/gallery/update-order/<int:group_id>', methods=['POST'])
@login_required
def update_gallery_order(group_id):
    try:
        display_order = int(request.form.get('display_order', 0))
        
        # 입력값 검증
        if display_order < 0 or display_order > 999:
            if request.is_json or request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                return jsonify({
                    'success': False,
                    'message': '표출 순서는 0~999 사이의 값이어야 합니다.'
                }), 400
            flash('표출 순서는 0~999 사이의 값이어야 합니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        # 갤러리 그룹 존재 확인
        result = db.session.execute(
            text("SELECT id, is_pinned, title FROM gallery_group WHERE id = :id"),
            {"id": group_id}
        )
        group_data = result.fetchone()
        
        if not group_data:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': '갤러리를 찾을 수 없습니다.'
                }), 404
            flash('갤러리를 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        is_pinned = bool(group_data[1])
        gallery_title = group_data[2]
        
        # 순서 업데이트
        db.session.execute(
            text("UPDATE gallery_group SET display_order = :display_order, updated_at = :updated_at WHERE id = :id"),
            {
                "id": group_id,
                "display_order": display_order,
                "updated_at": datetime.utcnow()
            }
        )
        db.session.commit()
        
        # AJAX 요청인 경우 JSON 응답
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if is_pinned:
                message = f'상단고정 갤러리 "{gallery_title}"의 표출 순서가 {display_order}(으)로 업데이트되었습니다.'
            else:
                message = f'갤러리 "{gallery_title}"의 표출 순서가 {display_order}(으)로 업데이트되었습니다.'
            
            return jsonify({
                'success': True,
                'message': message,
                'display_order': display_order,
                'is_pinned': is_pinned
            })
        
        # 일반 요청인 경우 기존 방식
        if is_pinned:
            flash(f'상단고정 갤러리의 표출 순서가 {display_order}(으)로 업데이트되었습니다.')
        else:
            flash(f'갤러리 표출 순서가 {display_order}(으)로 업데이트되었습니다.')
            
    except ValueError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '올바른 숫자를 입력해주세요.'
            }), 400
        flash('올바른 숫자를 입력해주세요.', 'error')
    except Exception as e:
        print(f"Error updating gallery order: {str(e)}")
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '갤러리 순서 업데이트 중 오류가 발생했습니다.'
            }), 500
        flash('갤러리 순서 업데이트 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_gallery'))

@admin.route('/gallery/toggle-pin/<int:group_id>', methods=['POST'])
@login_required
def toggle_gallery_pin(group_id):
    try:
        # 현재 상태 확인 (title도 함께 가져오기)
        result = db.session.execute(
            text("SELECT is_pinned, title FROM gallery_group WHERE id = :id"),
            {"id": group_id}
        )
        current_data = result.fetchone()
        
        if not current_data:
            flash('갤러리를 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        current_pinned = bool(current_data[0])
        gallery_title = current_data[1]
        new_state = not current_pinned
        
        # 상단 고정하려는 경우, 이미 3개가 고정되어 있는지 확인
        if new_state:
            pinned_count = db.session.execute(
                text("SELECT COUNT(*) FROM gallery_group WHERE is_pinned = 1")
            ).scalar()
            
            if pinned_count >= 3:
                flash('상단 고정은 최대 3개까지만 가능합니다. 다른 갤러리의 고정을 해제한 후 시도해주세요.', 'warning')
                return redirect(url_for('admin.list_gallery'))
        
        # 상태 업데이트
        db.session.execute(
            text("UPDATE gallery_group SET is_pinned = :is_pinned, updated_at = :updated_at WHERE id = :id"),
            {
                "id": group_id,
                "is_pinned": new_state,
                "updated_at": datetime.utcnow()
            }
        )
        db.session.commit()
        
        if new_state:
            # 현재 고정된 갤러리 개수 확인
            pinned_count = db.session.execute(
                text("SELECT COUNT(*) FROM gallery_group WHERE is_pinned = 1")
            ).scalar()
            flash(f'"{gallery_title}" 갤러리가 상단에 고정되었습니다. (현재 {pinned_count}/3개 고정)')
        else:
            flash(f'"{gallery_title}" 갤러리의 상단 고정이 해제되었습니다.')
            
    except Exception as e:
        print(f"Error toggling gallery pin: {str(e)}")
        flash('갤러리 상단 고정 상태 변경 중 오류가 발생했습니다.', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin.list_gallery'))

@admin.route('/services')
@login_required
def list_services():
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

@admin.route('/service/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_service(id):
    service = Service.query.get_or_404(id)
    
    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.category = request.form['category']
        
        # 상세 내용 저장
        details = request.form.getlist('details[]')
        service.details = json.dumps(details)
        
        # 패키지 정보 저장
        packages = []
        names = request.form.getlist('package_names[]')
        descriptions = request.form.getlist('package_descriptions[]')
        prices = request.form.getlist('package_prices[]')
        
        for i in range(len(names)):
            if names[i].strip():
                package = {
                    'name': names[i],
                    'description': descriptions[i],
                    'price': prices[i]
                }
                packages.append(package)
        
        service.packages = json.dumps(packages)
        
        db.session.commit()
        flash('서비스가 수정되었습니다.')
        return redirect(url_for('admin.list_services'))
    
    # JSON 데이터를 파이썬 객체로 변환
    details = json.loads(service.details) if service.details else []
    packages = json.loads(service.packages) if service.packages else []
        
    return render_template('admin/edit_service.html', 
                         service=service,
                         details=details,
                         packages=packages)

@admin.route('/services/delete/<int:id>')
@login_required
def delete_service(id):
    service = Service.query.get_or_404(id)
    db.session.delete(service)
    db.session.commit()
    flash('서비스가 삭제되었습니다.')
    return redirect(url_for('admin.list_services'))

@admin.route('/services/<int:service_id>/options')
@login_required
def list_options(service_id):
    service = Service.query.get_or_404(service_id)
    return render_template('admin/options.html', service=service)

@admin.route('/services/options/add', methods=['GET', 'POST'])
@login_required
def add_option_standalone():
    """카테고리를 선택해서 새로운 서비스 옵션을 추가하는 독립형 라우트"""
    services = Service.query.all()
    
    if request.method == 'POST':
        service_id = int(request.form['service_id'])
        service = Service.query.get_or_404(service_id)
        
        # 기본 ServiceOption 생성
        option = ServiceOption(
            service_id=service_id,
            name=request.form['name'],
            description=request.form['description'],
            detailed_description=request.form.get('detailed_description', '')
        )
        
        # 상세 내용 처리 (각 줄을 배열로 변환)
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        # 패키지 정보 처리 (파이프로 구분된 형식을 JSON으로 변환)
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            packages_list = []
            for line in packages_text.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        # 5개 필드: name, description, duration, price, notes
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': parts[4].strip()
                        }
                        packages_list.append(package)
                    elif len(parts) >= 4:
                        # 4개 필드: name, description, duration, price (비고 없음)
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
                    elif len(parts) >= 3:
                        # 기존 3개 필드 호환성
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': '',
                            'price': parts[2].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
            option.packages = json.dumps(packages_list, ensure_ascii=False) if packages_list else None
        else:
            option.packages = None
        
        db.session.add(option)
        db.session.commit()
        flash(f'{service.name} 카테고리에 "{option.name}" 서비스가 추가되었습니다.')
        return redirect(url_for('admin.list_services'))
    
    return render_template('admin/add_option_standalone.html', services=services)

@admin.route('/services/<int:service_id>/options/add', methods=['GET', 'POST'])
@login_required
def add_option(service_id):
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        # 기본 ServiceOption 생성
        option = ServiceOption(
            service_id=service_id,
            name=request.form['name'],
            description=request.form['description'],
            detailed_description=request.form.get('detailed_description', '')
        )
        
        # 상세 내용 처리 (각 줄을 배열로 변환)
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        # 패키지 정보 처리 (파이프로 구분된 형식을 JSON으로 변환)
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            packages_list = []
            for line in packages_text.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        # 5개 필드: name, description, duration, price, notes
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': parts[4].strip()
                        }
                        packages_list.append(package)
                    elif len(parts) >= 4:
                        # 4개 필드: name, description, duration, price (비고 없음)
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
                    elif len(parts) >= 3:
                        # 기존 3개 필드 호환성
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': '',
                            'price': parts[2].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
            option.packages = json.dumps(packages_list, ensure_ascii=False) if packages_list else None
        else:
            option.packages = None
        
        db.session.add(option)
        db.session.commit()
        flash('옵션이 추가되었습니다.')
        return redirect(url_for('admin.list_options', service_id=service_id))
    
    return render_template('admin/add_option.html', service=service)

@admin.route('/services/options/<int:option_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_option(option_id):
    option = ServiceOption.query.get_or_404(option_id)
    
    if request.method == 'POST':
        # 기본 정보 업데이트
        option.name = request.form['name']
        option.description = request.form['description']
        option.detailed_description = request.form.get('detailed_description', '')
        
        # 예약 조건 필드들 업데이트
        option.booking_method = request.form.get('booking_method', '')
        option.payment_info = request.form.get('payment_info', '')
        option.guide_info = request.form.get('guide_info', '')
        option.refund_policy_text = request.form.get('refund_policy_text', '')
        option.refund_policy_table = request.form.get('refund_policy_table', '')
        option.overtime_charge_table = request.form.get('overtime_charge_table', '')
        
        # 상세 내용 처리 (각 줄을 배열로 변환)
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        # 패키지 정보 처리 (파이프로 구분된 형식을 JSON으로 변환)
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            packages_list = []
            for line in packages_text.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        # 5개 필드: name, description, duration, price, notes
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': parts[4].strip()
                        }
                        packages_list.append(package)
                    elif len(parts) >= 4:
                        # 4개 필드: name, description, duration, price (비고 없음)
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
                    elif len(parts) >= 3:
                        # 기존 3개 필드 호환성
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': '',
                            'price': parts[2].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
            option.packages = json.dumps(packages_list, ensure_ascii=False) if packages_list else None
        else:
            option.packages = None
        
        db.session.commit()
        flash('옵션이 수정되었습니다.')
        return redirect(url_for('admin.list_services'))
    
    # GET 요청 시 기존 데이터 로드
    details_text = ''
    if option.details:
        try:
            details_list = json.loads(option.details)
            details_text = '\n'.join(details_list)
        except:
            details_text = option.details
    
    packages_text = ''
    if option.packages:
        try:
            packages_list = json.loads(option.packages)
            packages_lines = []
            for package in packages_list:
                line = f"{package.get('name', '')}|{package.get('description', '')}|{package.get('duration', '')}|{package.get('price', '')}|{package.get('notes', '')}"
                packages_lines.append(line)
            packages_text = '\n'.join(packages_lines)
        except:
            packages_text = option.packages
    
    return render_template('admin/edit_option.html', 
                         option=option, 
                         details_text=details_text,
                         packages_text=packages_text)

@admin.route('/services/options/<int:option_id>/delete')
@login_required
def delete_option(option_id):
    option = ServiceOption.query.get_or_404(option_id)
    service_name = option.name
    db.session.delete(option)
    db.session.commit()
    flash(f'서비스 "{service_name}"이(가) 삭제되었습니다.')
    return redirect(url_for('admin.list_services'))

# 딕셔너리를 모델처럼 사용하기 위한 클래스 추가
class DictAsModel:
    def __init__(self, data):
        # 딕셔너리의 키-값 쌍을 객체의 속성으로 설정
        for key, value in data.items():
            setattr(self, key, value)
    
    def get_datetimes(self):
        """예약 메시지에서 날짜/시간 정보 추출"""
        try:
            if hasattr(self, 'message') and self.message:
                lines = self.message.split('\n')
                datetimes = []
                capture = False
                
                for line in lines:
                    if '희망 예약일시:' in line:
                        capture = True
                        continue
                    
                    if capture and line.strip() and '순위:' in line:
                        parts = line.split('순위:')
                        if len(parts) > 1:
                            datetimes.append(parts[1].strip())
                
                return datetimes
        except Exception as e:
            print(f"Error in get_datetimes: {str(e)}")
        return []
    
    def get_message_content(self):
        """메시지 내용에서 희망 예약일시 부분을 제외한 내용 반환"""
        try:
            if hasattr(self, 'message') and self.message:
                lines = self.message.split('\n')
                content_lines = []
                exclude = False
                
                for line in lines:
                    if '희망 예약일시:' in line:
                        exclude = True
                        continue
                    
                    if not exclude or not line.strip() or not ('순위:' in line):
                        content_lines.append(line)
                
                return '\n'.join(content_lines).strip()
        except Exception as e:
            print(f"Error in get_message_content: {str(e)}")
        return ''
    
    def strftime(self, format_string):
        """datetime 객체의 strftime 메서드를 모방"""
        try:
            if hasattr(self, 'created_at') and self.created_at:
                if isinstance(self.created_at, datetime):
                    return self.created_at.strftime(format_string)
        except Exception as e:
            print(f"Error in strftime: {str(e)}")
        return ''

@admin.route('/bookings')
@login_required
def list_bookings():
    try:
        # 직접 SQL 쿼리를 사용하여 예약 목록 조회
        result = db.session.execute(text("""
            SELECT b.id, b.name, b.email, b.message, b.status, b.created_at, s.name as service_name
            FROM booking b
            LEFT JOIN service s ON b.service_id = s.id
            ORDER BY b.created_at DESC
        """))
        
        # 결과를 DictAsModel 객체 리스트로 변환
        bookings = []
        for row in result:
            booking_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'message': row[3],
                'status': row[4],
                'created_at': row[5],
                'service': DictAsModel({'name': row[6]}) if row[6] else None
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if booking_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(booking_data['created_at'], datetime):
                        booking_data['created_at'] = pytz.utc.localize(booking_data['created_at']).astimezone(pytz.timezone('Asia/Seoul'))
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(booking_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(booking_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        booking_data['created_at'] = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Seoul'))
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    booking_data['created_at'] = datetime.now()
            
            # 딕셔너리를 DictAsModel 객체로 변환
            booking = DictAsModel(booking_data)
            bookings.append(booking)
        
        return render_template('admin/bookings.html', bookings=bookings)
    except Exception as e:
        print(f"Error in list_bookings: {str(e)}")
        flash('예약 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/bookings.html', bookings=[])

@admin.route('/booking/<int:id>/status/<status>')
@login_required
def update_booking_status(id, status):
    try:
        if status in ['대기', '확정', '취소']:
            # 직접 SQL 쿼리를 사용하여 예약 상태 업데이트
            db.session.execute(
                text("UPDATE booking SET status = :status WHERE id = :id"),
                {"id": id, "status": status}
            )
            db.session.commit()
            flash('예약 상태가 업데이트되었습니다.')
    except Exception as e:
        print(f"Error updating booking status: {str(e)}")
        flash('예약 상태 업데이트 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_bookings'))

@admin.route('/booking/<int:id>/delete')
@login_required
def delete_booking(id):
    try:
        # 직접 SQL 쿼리를 사용하여 예약 삭제
        db.session.execute(
            text("DELETE FROM booking WHERE id = :id"),
            {"id": id}
        )
        db.session.commit()
        flash('예약이 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting booking: {str(e)}")
        flash('예약 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_bookings'))

@admin.route('/gallery')
@login_required
def list_gallery():
    try:
        # 직접 SQL 쿼리를 사용하여 갤러리 그룹 목록 조회 (display_order, is_pinned 포함)
        result = db.session.execute(text("""
            SELECT id, title, created_at, display_order, is_pinned
            FROM gallery_group
            ORDER BY is_pinned DESC, display_order DESC, created_at DESC
        """))
        
        # 결과를 DictAsModel 객체 리스트로 변환
        gallery_groups = []
        for row in result:
            group_data = {
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'display_order': row[3] if row[3] is not None else 0,
                'is_pinned': bool(row[4]) if row[4] is not None else False,
                'images': []  # 이미지 목록은 별도로 조회
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if group_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(group_data['created_at'], datetime):
                        group_data['created_at'] = pytz.utc.localize(group_data['created_at']).astimezone(pytz.timezone('Asia/Seoul'))
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(group_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(group_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        group_data['created_at'] = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Seoul'))
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    group_data['created_at'] = datetime.now()
            
            # 각 그룹의 이미지 조회
            try:
                image_result = db.session.execute(text("""
                    SELECT id, image_path, caption, "order"
                    FROM gallery
                    WHERE group_id = :group_id
                    ORDER BY "order"
                """), {'group_id': group_data['id']})
                
                for img_row in image_result:
                    image_data = {
                        'id': img_row[0],
                        'image_path': img_row[1],
                        'caption': img_row[2],
                        'order': img_row[3]
                    }
                    # 이미지도 DictAsModel 객체로 변환
                    group_data['images'].append(DictAsModel(image_data))
            except Exception as img_error:
                print(f"Error fetching images for group {group_data['id']}: {str(img_error)}")
            
            # 딕셔너리를 DictAsModel 객체로 변환
            group = DictAsModel(group_data)
            gallery_groups.append(group)
        
        return render_template('admin/list_gallery.html', gallery_groups=gallery_groups)
    except Exception as e:
        print(f"Error in list_gallery: {str(e)}")
        flash('갤러리 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/list_gallery.html', gallery_groups=[])

@admin.route('/inquiries')
@login_required
def list_inquiries():
    try:
        # 직접 SQL 쿼리를 사용하여 문의 목록 조회
        result = db.session.execute(text("""
            SELECT i.id, i.name, i.email, i.phone, i.message, i.status, i.created_at, s.name as service_name
            FROM inquiry i
            LEFT JOIN service s ON i.service_id = s.id
            ORDER BY i.created_at DESC
        """))
        
        # 결과를 DictAsModel 객체 리스트로 변환
        inquiries = []
        for row in result:
            inquiry_data = {
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'phone': row[3],
                'message': row[4],
                'status': row[5],
                'created_at': row[6],
                'service': DictAsModel({'name': row[7]}) if row[7] else None
            }
            
            # 날짜 형식 변환 (문자열 또는 datetime 객체 모두 처리)
            if inquiry_data['created_at']:
                try:
                    # 이미 datetime 객체인 경우
                    if isinstance(inquiry_data['created_at'], datetime):
                        inquiry_data['created_at'] = pytz.utc.localize(inquiry_data['created_at']).astimezone(pytz.timezone('Asia/Seoul'))
                    # 문자열인 경우
                    else:
                        # 다양한 형식 처리
                        try:
                            dt = datetime.strptime(inquiry_data['created_at'], '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(inquiry_data['created_at'], '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 다른 형식이 있을 수 있음
                                dt = datetime.now()  # 기본값
                        inquiry_data['created_at'] = pytz.utc.localize(dt).astimezone(pytz.timezone('Asia/Seoul'))
                except Exception as date_error:
                    print(f"Date conversion error: {str(date_error)}")
                    # 오류 발생 시 현재 시간으로 대체
                    inquiry_data['created_at'] = datetime.now()
            
            # 딕셔너리를 DictAsModel 객체로 변환
            inquiry = DictAsModel(inquiry_data)
            inquiries.append(inquiry)
        
        return render_template('admin/inquiries.html', inquiries=inquiries)
    except Exception as e:
        print(f"Error in list_inquiries: {str(e)}")
        flash('문의 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/inquiries.html', inquiries=[])

@admin.route('/inquiries/<int:id>/status', methods=['POST'])
@login_required
def update_inquiry_status(id):
    try:
        status = request.form.get('status')
        # 직접 SQL 쿼리를 사용하여 문의 상태 업데이트
        db.session.execute(
            text("UPDATE inquiry SET status = :status WHERE id = :id"),
            {"id": id, "status": status}
        )
        db.session.commit()
        flash('문의 상태가 업데이트되었습니다.')
    except Exception as e:
        print(f"Error updating inquiry status: {str(e)}")
        flash('문의 상태 업데이트 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_inquiries'))

@admin.route('/inquiries/<int:id>/delete', methods=['POST'])
@login_required
def delete_inquiry(id):
    try:
        # 직접 SQL 쿼리를 사용하여 문의 삭제
        db.session.execute(
            text("DELETE FROM inquiry WHERE id = :id"),
            {"id": id}
        )
        db.session.commit()
        flash('문의가 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting inquiry: {str(e)}")
        flash('문의 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_inquiries'))

# 임시 관리자 비밀번호 재설정 라우트 (사용 후 제거 필요)
@admin.route('/reset-admin-password/<username>/<new_password>')
def reset_admin_password(username, new_password):
    # 보안을 위한 간단한 토큰 확인 (실제 구현에서는 더 강력한 보안 필요)
    token = request.args.get('token')
    if token != 'stylegrapher':  # 토큰 값을 'stylegrapher'로 변경
        return "Unauthorized", 401
    
    try:
        # 직접 SQL 쿼리를 사용하여 사용자 조회
        result = db.session.execute(
            text("SELECT id FROM user WHERE uq_user_username = :username"),
            {"username": username}
        )
        user_data = result.fetchone()
        
        if not user_data:
            return f"User {username} not found", 404
        
        # 새로운 해싱 알고리즘으로 비밀번호 설정
        update_sql = text("""
        UPDATE user SET password_hash = :password_hash
        WHERE id = :id
        """)
        update_params = {
            "id": user_data[0],
            "password_hash": generate_password_hash(new_password, method='pbkdf2:sha256')
        }
        db.session.execute(update_sql, update_params)
        db.session.commit()
        
        return f"Password for {username} has been reset successfully"
    except Exception as e:
        print(f"Error resetting password: {str(e)}")
        return f"Error resetting password: {str(e)}", 500

# 임시 관리자 계정 생성 라우트 (사용 후 제거 필요)
@admin.route('/create-admin/<username>/<email>/<password>')
def create_admin_account(username, email, password):
    # 보안을 위한 간단한 토큰 확인 (실제 구현에서는 더 강력한 보안 필요)
    token = request.args.get('token')
    if token != 'stylegrapher':  # 토큰 값을 'stylegrapher'로 변경
        return "Unauthorized", 401
    
    try:
        # 테이블 구조 확인
        result = db.session.execute(text("PRAGMA table_info(user)"))
        columns = [column[1] for column in result.fetchall()]
        print("User table columns:", columns)
        
        # 이미 존재하는 사용자인지 확인
        result = db.session.execute(
            text("SELECT id FROM user WHERE uq_user_username = :username"),
            {"username": username}
        )
        existing_user = result.fetchone()
        
        if existing_user:
            return f"User {username} already exists", 400
        
        # 테이블에 email 열이 있는지 확인
        has_email_column = 'email' in columns
        
        if has_email_column:
            # email 열이 있는 경우
            sql = text("""
            INSERT INTO user (uq_user_username, email, password_hash, is_admin) 
            VALUES (:username, :email, :password_hash, :is_admin)
            """)
            params = {
                "username": username,
                "email": email,
                "password_hash": generate_password_hash(password, method='pbkdf2:sha256'),
                "is_admin": True
            }
        else:
            # email 열이 없는 경우
            sql = text("""
            INSERT INTO user (uq_user_username, password_hash, is_admin) 
            VALUES (:username, :password_hash, :is_admin)
            """)
            params = {
                "username": username,
                "password_hash": generate_password_hash(password, method='pbkdf2:sha256'),
                "is_admin": True
            }
        
        # 새 관리자 계정 생성
        db.session.execute(sql, params)
        db.session.commit()
        
        return f"Admin account {username} has been created successfully"
    except Exception as e:
        print(f"Error creating admin account: {str(e)}")
        return f"Error creating admin account: {str(e)}", 500

@admin.route('/image/<image_id>')
def get_image(image_id):
    try:
        print(f"이미지 요청: {image_id}")
        
        # 로컬 파일 시스템에서 이미지 검색 함수
        def get_from_local():
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_id)
            print(f"로컬 파일 시스템에서 이미지 검색: {file_path}")
            
            if os.path.exists(file_path):
                print(f"로컬 파일 시스템에서 이미지 발견: {file_path}")
                content_type = 'image/jpeg'  # 기본값
                if image_id.lower().endswith('.png'):
                    content_type = 'image/png'
                elif image_id.lower().endswith('.gif'):
                    content_type = 'image/gif'
                    
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                
                response = make_response(image_data)
                response.headers.set('Content-Type', content_type)
                return response
            
            print(f"이미지를 찾을 수 없음: {image_id}")
            return None
        
        # MongoDB 연결이 없으면 로컬 저장소에서 검색
        if images_collection is None:
            print("MongoDB 연결이 설정되지 않았습니다.")
            local_response = get_from_local()
            if local_response:
                return local_response
            return "Image not found", 404
        
        try:
            # MongoDB에서 이미지 검색
            print(f"MongoDB에서 이미지 검색: {image_id}")
            image_doc = images_collection.find_one({'_id': image_id})
            
            if image_doc:
                print(f"MongoDB에서 이미지 발견: {image_id}")
                # MongoDB에서 찾은 경우 바이너리 데이터 반환
                response = make_response(image_doc['binary_data'])
                response.headers.set('Content-Type', image_doc['content_type'])
                return response
            else:
                print(f"MongoDB에서 이미지를 찾을 수 없음: {image_id}")
                # MongoDB에서 찾을 수 없는 경우, 로컬 파일 시스템에서 시도
                local_response = get_from_local()
                if local_response:
                    return local_response
                return "Image not found", 404
        except Exception as mongo_error:
            print(f"MongoDB에서 이미지 검색 중 오류 발생: {str(mongo_error)}")
            # MongoDB 검색 중 오류 발생 시 로컬 파일 시스템에서 시도
            local_response = get_from_local()
            if local_response:
                return local_response
            # 로컬에서도 찾을 수 없으면 오류 반환
            return "Error retrieving image", 500
            
    except Exception as e:
        print(f"이미지 검색 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Error retrieving image", 500

# Fade Text (CollageText) 관리
@admin.route('/fade-texts')
@login_required
def list_fade_texts():
    try:
        fade_texts = CollageText.query.order_by(CollageText.order.asc()).all()
        return render_template('admin/fade_texts.html', fade_texts=fade_texts)
    except Exception as e:
        print(f"Error listing fade texts: {str(e)}")
        flash('Fade Text 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin.route('/fade-text/add', methods=['GET', 'POST'])
@login_required
def add_fade_text():
    if request.method == 'POST':
        try:
            text = request.form.get('text', '').strip()
            order = request.form.get('order', 0, type=int)
            
            if not text:
                flash('텍스트를 입력해주세요.', 'error')
                return render_template('admin/add_fade_text.html')
                
            fade_text = CollageText(text=text, order=order)
            db.session.add(fade_text)
            db.session.commit()
            
            flash('Fade Text가 추가되었습니다.')
            return redirect(url_for('admin.list_fade_texts'))
        except Exception as e:
            print(f"Error adding fade text: {str(e)}")
            flash('Fade Text 추가 중 오류가 발생했습니다.', 'error')
    
    return render_template('admin/add_fade_text.html')

@admin.route('/fade-text/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_fade_text(id):
    try:
        fade_text = CollageText.query.get_or_404(id)
        
        if request.method == 'POST':
            text = request.form.get('text', '').strip()
            order = request.form.get('order', 0, type=int)
            
            if not text:
                flash('텍스트를 입력해주세요.', 'error')
                return render_template('admin/edit_fade_text.html', fade_text=fade_text)
                
            fade_text.text = text
            fade_text.order = order
            db.session.commit()
            
            flash('Fade Text가 수정되었습니다.')
            return redirect(url_for('admin.list_fade_texts'))
            
        return render_template('admin/edit_fade_text.html', fade_text=fade_text)
    except Exception as e:
        print(f"Error editing fade text: {str(e)}")
        flash('Fade Text 수정 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.list_fade_texts'))

@admin.route('/fade-text/delete/<int:id>')
@login_required
def delete_fade_text(id):
    try:
        fade_text = CollageText.query.get_or_404(id)
        db.session.delete(fade_text)
        db.session.commit()
        
        flash('Fade Text가 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting fade text: {str(e)}")
        flash('Fade Text 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_fade_texts'))

# 사이트 색상 설정 관리
@admin.route('/site-colors')
@login_required
def site_colors():
    try:
        settings = SiteSettings.get_current_settings()
        return render_template('admin/site_colors.html', settings=settings)
    except Exception as e:
        print(f"Error loading site colors: {str(e)}")
        flash('사이트 색상 설정을 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.dashboard'))

@admin.route('/site-colors/update', methods=['POST'])
@login_required
def update_site_colors():
    try:
        settings = SiteSettings.get_current_settings()
        
        # Main Color
        main_r = request.form.get('main_color_r', 139, type=int)
        main_g = request.form.get('main_color_g', 95, type=int)
        main_b = request.form.get('main_color_b', 191, type=int)
        
        # Sub Color
        sub_r = request.form.get('sub_color_r', 65, type=int)
        sub_g = request.form.get('sub_color_g', 26, type=int)
        sub_b = request.form.get('sub_color_b', 75, type=int)
        
        # Background Color
        bg_r = request.form.get('background_color_r', 255, type=int)
        bg_g = request.form.get('background_color_g', 255, type=int)
        bg_b = request.form.get('background_color_b', 255, type=int)
        
        # 값 유효성 검사 (0-255 범위)
        def validate_rgb(value):
            return max(0, min(255, value))
        
        settings.main_color_r = validate_rgb(main_r)
        settings.main_color_g = validate_rgb(main_g)
        settings.main_color_b = validate_rgb(main_b)
        
        settings.sub_color_r = validate_rgb(sub_r)
        settings.sub_color_g = validate_rgb(sub_g)
        settings.sub_color_b = validate_rgb(sub_b)
        
        settings.background_color_r = validate_rgb(bg_r)
        settings.background_color_g = validate_rgb(bg_g)
        settings.background_color_b = validate_rgb(bg_b)
        
        db.session.commit()
        
        flash('사이트 색상이 성공적으로 업데이트되었습니다.')
        return redirect(url_for('admin.site_colors'))
        
    except Exception as e:
        print(f"Error updating site colors: {str(e)}")
        flash('색상 업데이트 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.site_colors'))

@admin.route('/site-colors/reset', methods=['POST'])
@login_required
def reset_site_colors():
    try:
        settings = SiteSettings.get_current_settings()
        
        # 기본값으로 리셋
        settings.main_color_r = 139
        settings.main_color_g = 95
        settings.main_color_b = 191
        
        settings.sub_color_r = 65
        settings.sub_color_g = 26
        settings.sub_color_b = 75
        
        settings.background_color_r = 255
        settings.background_color_g = 255
        settings.background_color_b = 255
        
        db.session.commit()
        
        flash('사이트 색상이 기본값으로 리셋되었습니다.')
        return redirect(url_for('admin.site_colors'))
        
    except Exception as e:
        print(f"Error resetting site colors: {str(e)}")
        flash('색상 리셋 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.site_colors'))

# 이용약관 관리
@admin.route('/terms-of-service')
@login_required
def manage_terms():
    try:
        terms = TermsOfService.get_current_content()
        return render_template('admin/terms_of_service.html', terms=terms)
    except Exception as e:
        flash(f'이용약관 로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin.route('/terms-of-service/update', methods=['POST'])
@login_required
def update_terms():
    try:
        content = request.form.get('content', '')
        
        if not content.strip():
            flash('이용약관 내용을 입력해주세요.', 'error')
            return redirect(url_for('admin.manage_terms'))
        
        terms = TermsOfService.get_current_content()
        terms.content = content
        terms.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('이용약관이 성공적으로 업데이트되었습니다.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_terms'))

# 개인정보처리방침 관리
@admin.route('/privacy-policy')
@login_required
def manage_privacy():
    try:
        policy = PrivacyPolicy.get_current_content()
        return render_template('admin/privacy_policy.html', policy=policy)
    except Exception as e:
        flash(f'개인정보처리방침 로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin.route('/privacy-policy/update', methods=['POST'])
@login_required
def update_privacy():
    try:
        content = request.form.get('content', '')
        
        if not content.strip():
            flash('개인정보처리방침 내용을 입력해주세요.', 'error')
            return redirect(url_for('admin.manage_privacy'))
        
        policy = PrivacyPolicy.get_current_content()
        policy.content = content
        policy.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('개인정보처리방침이 성공적으로 업데이트되었습니다.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_privacy'))