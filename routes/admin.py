from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
from flask_login import login_required, login_user, logout_user
from extensions import db, login_manager
from models import Service, Gallery, User, ServiceOption, Booking, CarouselItem, GalleryGroup, Inquiry
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
    mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
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
        service = Service(
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            category=request.form['category']
        )
        db.session.add(service)
        db.session.commit()
        flash('서비스가 추가되었습니다.')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/add_service.html')

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
            # 갤러리 그룹 생성
            gallery_group = GalleryGroup(title=request.form['title'])
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

@admin.route('/services/<int:service_id>/options/add', methods=['GET', 'POST'])
@login_required
def add_option(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        option = ServiceOption(
            service_id=service_id,
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            duration=request.form['duration']
        )
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
        option.name = request.form['name']
        option.description = request.form['description']
        option.price = request.form['price']
        option.duration = request.form['duration']
        db.session.commit()
        flash('옵션이 수정되었습니다.')
        return redirect(url_for('admin.list_options', service_id=option.service_id))
    return render_template('admin/edit_option.html', option=option)

@admin.route('/services/options/<int:option_id>/delete')
@login_required
def delete_option(option_id):
    option = ServiceOption.query.get_or_404(option_id)
    service_id = option.service_id
    db.session.delete(option)
    db.session.commit()
    flash('옵션이 삭제되었습니다.')
    return redirect(url_for('admin.list_options', service_id=service_id))

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

@admin.route('/carousel')
@login_required
def list_carousel():
    carousel_items = CarouselItem.query.order_by(CarouselItem.order).all()
    return render_template('admin/carousel.html', carousel_items=carousel_items)

@admin.route('/carousel/add', methods=['GET', 'POST'])
@login_required
def add_carousel():
    if request.method == 'POST':
        file = request.files['image']
        if file:
            # MongoDB에 이미지 저장 및 ID 반환
            image_id = save_image_to_mongodb(file)
            
            carousel_item = CarouselItem(
                title=request.form['title'],
                subtitle=request.form['subtitle'],
                image_path=image_id,  # MongoDB ID 저장
                order=CarouselItem.query.count()
            )
            db.session.add(carousel_item)
            db.session.commit()
            
            flash('캐러셀 슬라이드가 추가되었습니다.')
            return redirect(url_for('admin.list_carousel'))
            
    return render_template('admin/add_carousel.html')

@admin.route('/carousel/update-order', methods=['POST'])
@login_required
def update_carousel_order():
    order_data = request.get_json()
    for item in order_data:
        carousel_item = CarouselItem.query.get(item['id'])
        if carousel_item:
            carousel_item.order = item['order']
    db.session.commit()
    return jsonify({'success': True})

@admin.route('/carousel/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_carousel(id):
    carousel_item = CarouselItem.query.get_or_404(id)
    
    if request.method == 'POST':
        carousel_item.title = request.form['title']
        carousel_item.subtitle = request.form['subtitle']
        
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # 기존 이미지 삭제
                if carousel_item.image_path:
                    images_collection.delete_one({'_id': carousel_item.image_path})
                
                # MongoDB에 이미지 저장 및 ID 반환
                image_id = save_image_to_mongodb(file)
                carousel_item.image_path = image_id
        
        db.session.commit()
        flash('캐러셀 항목이 수정되었습니다.')
        return redirect(url_for('admin.list_carousel'))
        
    return render_template('admin/edit_carousel.html', carousel=carousel_item)

@admin.route('/carousel/delete/<int:id>')
@login_required
def delete_carousel(id):
    carousel_item = CarouselItem.query.get_or_404(id)
    
    # MongoDB에서 이미지 삭제
    if carousel_item.image_path:
        images_collection.delete_one({'_id': carousel_item.image_path})
    
    db.session.delete(carousel_item)
    db.session.commit()
    flash('캐러셀 항목이 삭제되었습니다.')
    return redirect(url_for('admin.list_carousel'))

@admin.route('/gallery')
@login_required
def list_gallery():
    try:
        # 직접 SQL 쿼리를 사용하여 갤러리 그룹 목록 조회
        result = db.session.execute(text("""
            SELECT id, title, created_at
            FROM gallery_group
            ORDER BY created_at DESC
        """))
        
        # 결과를 DictAsModel 객체 리스트로 변환
        gallery_groups = []
        for row in result:
            group_data = {
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
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
        
        if images_collection is None:
            print("MongoDB 연결이 설정되지 않았습니다.")
            # MongoDB 연결 없이 로컬 파일 시스템에서만 검색
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
            return "Image not found", 404
        
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
            return "Image not found", 404
    except Exception as e:
        print(f"이미지 검색 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Error retrieving image", 500