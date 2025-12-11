"""
Admin 라우트 - MongoDB 기반
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
from flask_login import login_required, login_user, logout_user
from extensions import login_manager
from werkzeug.utils import secure_filename
import os
from PIL import Image
import json
from datetime import datetime
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
import io
import uuid
# pymongo 상수는 utils/mongo_models.py에서 사용
from dotenv import load_dotenv
from utils.monitor import security_monitor
from utils.translation_helper import trigger_translation
from utils.gridfs_helper import (
    save_image_to_gridfs,
    get_image_from_gridfs,
    delete_image_from_gridfs,
    get_mongo_connection,
    get_gridfs_stats,
    migrate_legacy_to_gridfs
)

# MongoDB 모델 임포트
from utils.mongo_models import (
    get_mongo_db, init_collections,
    User, Service, ServiceOption, GalleryGroup, Gallery,
    Booking, Inquiry, CollageText, SiteSettings,
    TermsOfService, PrivacyPolicy, AdminNotificationEmail, CompanyInfo, AboutContent
)

# .env 파일 로드 (fork-safe: MongoDB 연결은 lazy하게 생성됨)
load_dotenv()

admin = Blueprint('admin', __name__)


@login_manager.user_loader
def load_user(id):
    """Flask-Login 사용자 로더 - MongoDB 기반"""
    try:
        user = User.get_by_id(int(id))
        return user
    except Exception as e:
        print(f"Error loading user: {str(e)}")
        return None


@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            user = User.get_by_username(username)
            
            if user and user.check_password(password):
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
        kst = pytz.timezone('Asia/Seoul')
        
        # MongoDB에서 최근 100개 데이터 가져오기
        recent_bookings = Booking.query_all_ordered(limit=100)
        recent_inquiries = Inquiry.query_all_ordered(limit=100)
        recent_galleries = GalleryGroup.query_all_ordered()[:100]
        
        # 시간대 변환
        for booking in recent_bookings:
            if booking.created_at:
                if isinstance(booking.created_at, datetime):
                    if booking.created_at.tzinfo is None:
                        booking.created_at = pytz.utc.localize(booking.created_at).astimezone(kst)
                    else:
                        booking.created_at = booking.created_at.astimezone(kst)
        
        for inquiry in recent_inquiries:
            if inquiry.created_at:
                if isinstance(inquiry.created_at, datetime):
                    if inquiry.created_at.tzinfo is None:
                        inquiry.created_at = pytz.utc.localize(inquiry.created_at).astimezone(kst)
                    else:
                        inquiry.created_at = inquiry.created_at.astimezone(kst)
        
        for gallery in recent_galleries:
            if gallery.created_at:
                if isinstance(gallery.created_at, datetime):
                    if gallery.created_at.tzinfo is None:
                        gallery.created_at = pytz.utc.localize(gallery.created_at).astimezone(kst)
                    else:
                        gallery.created_at = gallery.created_at.astimezone(kst)
        
        # 전체 개수
        total_bookings = Booking.count()
        total_inquiries = Inquiry.count()
        total_galleries = GalleryGroup.count()
        
        # 미확인 (대기 상태) 예약/문의 개수
        pending_bookings = Booking.count({'status': '대기'})
        pending_inquiries = Inquiry.count({'$and': [
            {'status': '대기'},
            {'$or': [{'is_spam': False}, {'is_spam': {'$exists': False}}]}
        ]})
        
        return render_template('admin/dashboard.html',
                             recent_bookings=recent_bookings,
                             recent_inquiries=recent_inquiries,
                             recent_galleries=recent_galleries,
                             total_bookings=total_bookings,
                             total_inquiries=total_inquiries,
                             total_galleries=total_galleries,
                             pending_bookings=pending_bookings,
                             pending_inquiries=pending_inquiries)
                             
    except Exception as e:
        print(f"Error in dashboard route: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('데이터를 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/dashboard.html',
                             recent_bookings=[],
                             recent_inquiries=[],
                             recent_galleries=[],
                             total_bookings=0,
                             total_inquiries=0,
                             total_galleries=0,
                             pending_bookings=0,
                             pending_inquiries=0)


@admin.route('/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    if request.method == 'POST':
        try:
            details_text = request.form.get('details', '').strip()
            details = [line.strip() for line in details_text.split('\n') if line.strip()] if details_text else []
            
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
            
            service = Service(
                name=request.form['name'],
                description=request.form['description'],
                category=request.form['category'],
                details=json.dumps(details),
                packages=json.dumps(packages)
            )
            service.save()
            
            trigger_translation('service', service)
            
            flash('서비스가 성공적으로 추가되었습니다. 이제 개별 옵션을 추가해보세요.')
            return redirect(url_for('admin.list_options', service_id=service.id))
            
        except Exception as e:
            flash(f'서비스 추가 중 오류가 발생했습니다: {str(e)}')
            return redirect(request.url)
    
    return render_template('admin/add_service.html')


@admin.route('/category/add', methods=['GET', 'POST'])
@login_required
def add_category():
    if request.method == 'POST':
        try:
            service = Service(
                name=request.form['name'],
                description=request.form['description'],
                category=None,
                details=json.dumps([]),
                packages=json.dumps([])
            )
            service.save()
            
            service_option = ServiceOption(
                service_id=service.id,
                name=request.form['name'],
                description=request.form['description'],
                detailed_description='',
                details=json.dumps([]),
                packages=json.dumps([])
            )
            service_option.save()
            
            # 서비스 옵션 캐시 클리어
            from routes.main import clear_service_option_cache
            clear_service_option_cache(service_option.id)
            
            # 다국어 번역 트리거
            trigger_translation('service', service)
            trigger_translation('service_option', service_option)
            
            flash('새 카테고리가 성공적으로 추가되었습니다.')
            return redirect(url_for('admin.list_services'))
            
        except Exception as e:
            flash(f'카테고리 추가 중 오류가 발생했습니다: {str(e)}')
            return redirect(request.url)
    
    return render_template('admin/add_category.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# 웹 최적화 설정
WEB_IMAGE_CONFIG = {
    'max_width': 800,
    'max_height': 1200,
    'jpeg_quality': 82,
    'progressive_jpeg': True,
}


def resize_image_memory(img, max_width=None, max_height=None):
    """메모리 상의 이미지를 웹 최적화 크기로 리사이즈"""
    max_width = max_width or WEB_IMAGE_CONFIG['max_width']
    max_height = max_height or WEB_IMAGE_CONFIG['max_height']
    
    original_width, original_height = img.size
    
    if original_width <= max_width and original_height <= max_height:
        return img
    
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    ratio = min(width_ratio, height_ratio)
    
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)
    
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return resized_img


def save_image_to_mongodb(file, group_id=None, order=0):
    """파일을 GridFS에 저장"""
    try:
        image_id = save_image_to_gridfs(file, group_id=group_id, order=order)
        print(f"GridFS: 이미지 저장 성공 - ID: {image_id}")
        return image_id
    except Exception as e:
        print(f"GridFS 저장 실패, 레거시 방식으로 저장 시도: {str(e)}")
        
        file.seek(0)
        filename = secure_filename(file.filename)
        
        img_data = file.read()
        original_size = len(img_data)
        
        img = Image.open(io.BytesIO(img_data))
        resized_img = resize_image_memory(img)
        
        buffer = io.BytesIO()
        if resized_img.mode in ('RGBA', 'P'):
            resized_img = resized_img.convert('RGB')
        resized_img.save(
            buffer, 
            format='JPEG', 
            quality=WEB_IMAGE_CONFIG['jpeg_quality'],
            optimize=True,
            progressive=WEB_IMAGE_CONFIG['progressive_jpeg']
        )
        img_binary = buffer.getvalue()
        
        compressed_size = len(img_binary)
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        print(f"레거시 저장: 이미지 최적화 - {original_size/1024:.1f}KB → {compressed_size/1024:.1f}KB [{compression_ratio:.1f}% 절약]")
        
        image_id = str(uuid.uuid4())
        image_doc = {
            '_id': image_id,
            'filename': filename,
            'content_type': 'image/jpeg',
            'binary_data': img_binary,
            'created_at': datetime.now()
        }
        
        if group_id is not None:
            image_doc['group_id'] = group_id
            image_doc['order'] = order
        
        try:
            db = get_mongo_db()
            images_collection = db['gallery']
            images_collection.insert_one(image_doc)
            print(f"레거시 방식으로 이미지 저장 성공 - ID: {image_id}")
        except Exception as e:
            print(f"레거시 MongoDB 저장 오류 (무시): {str(e)}")
        
        return image_id


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
            # 새 갤러리의 순서 결정 (기존 갤러리 영향 없음)
            all_groups = GalleryGroup.query_all_ordered()
            min_order = min([g.display_order for g in all_groups]) if all_groups else 1
            next_order = min_order - 1 if min_order > 0 else 0
            
            print(f"🛡️ 갤러리 순서 보호: 새 갤러리를 순서 {next_order}로 배치")
            
            gallery_group = GalleryGroup(
                title=request.form['title'],
                display_order=next_order,
                is_pinned=False
            )
            gallery_group.save()
            
            for i, file in enumerate(files):
                if file and allowed_file(file.filename):
                    image_id = save_image_to_mongodb(file, gallery_group.id, i)
                    
                    gallery = Gallery(
                        image_path=image_id,
                        order=i,
                        group_id=gallery_group.id
                    )
                    gallery.save()
            
            try:
                trigger_translation('gallery_group', gallery_group)
                print(f"🌐 갤러리 그룹 '{gallery_group.title}' 번역 시작됨")
            except Exception as trans_error:
                print(f"⚠️ 번역 트리거 실패 (무시 가능): {str(trans_error)}")
            
            try:
                from routes.main import clear_gallery_cache
                clear_gallery_cache()
            except Exception as cache_error:
                print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
            
            flash('이미지가 업로드되었습니다.')
            return redirect(url_for('admin.list_gallery'))
        except Exception as e:
            print(f"Error uploading images: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('이미지 업로드 중 오류가 발생했습니다.', 'error')
            return redirect(request.url)
            
    return render_template('admin/upload_image.html')


@admin.route('/gallery/delete/<int:group_id>')
@login_required
def delete_gallery_group(group_id):
    group = GalleryGroup.get_or_404(group_id)
    
    # 이미지 삭제
    for image in group.images:
        try:
            deleted = delete_image_from_gridfs(image.image_path)
            if not deleted:
                try:
                    db = get_mongo_db()
                    images_collection = db['gallery']
                    images_collection.delete_one({'_id': image.image_path})
                except Exception as db_error:
                    print(f"레거시 MongoDB 삭제 오류 (무시): {str(db_error)}")
            print(f"이미지 삭제 완료: {image.image_path}")
            image.delete()
        except Exception as e:
            print(f"이미지 삭제 중 오류 (무시): {str(e)}")
    
    group.delete()
    
    try:
        from routes.main import clear_gallery_cache
        clear_gallery_cache()
    except Exception as cache_error:
        print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
    
    flash('갤러리가 삭제되었습니다.')
    return redirect(url_for('admin.list_gallery'))


@admin.route('/gallery/update-order/<int:group_id>', methods=['POST'])
@login_required
def update_gallery_order(group_id):
    try:
        raw_value = request.form.get('display_order', '0')
        display_order = int(raw_value)
        
        print(f"🎯 update_gallery_order 호출: group_id={group_id}, raw_value={raw_value}, display_order={display_order}")
        
        if display_order < 0 or display_order > 999:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': '표출 순서는 0~999 사이의 값이어야 합니다.'
                }), 400
            flash('표출 순서는 0~999 사이의 값이어야 합니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        group = GalleryGroup.get_by_id(group_id)
        if not group:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': '갤러리를 찾을 수 없습니다.'
                }), 404
            flash('갤러리를 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        print(f"📥 기존 display_order: {group.display_order}")
        
        # 명시적으로 int로 변환하여 저장
        group.display_order = int(display_order)
        group.updated_at = datetime.utcnow()
        
        print(f"📤 새로운 display_order 설정: {group.display_order}")
        
        group.save()
        
        # 저장 후 재조회하여 확인
        saved_group = GalleryGroup.get_by_id(group_id)
        print(f"✅ 저장 후 재조회 display_order: {saved_group.display_order if saved_group else 'NOT FOUND'}")
        
        try:
            from routes.main import clear_gallery_cache
            clear_gallery_cache()
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            message = f'갤러리 "{group.title}"의 표출 순서가 {display_order}(으)로 업데이트되었습니다.'
            return jsonify({
                'success': True,
                'message': message,
                'display_order': int(display_order),
                'is_pinned': group.is_pinned
            })
        
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
        group = GalleryGroup.get_by_id(group_id)
        if not group:
            flash('갤러리를 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_gallery'))
        
        new_state = not group.is_pinned
        
        if new_state:
            pinned_count = len([g for g in GalleryGroup.query_all_ordered() if g.is_pinned])
            if pinned_count >= 3:
                flash('상단 고정은 최대 3개까지만 가능합니다. 다른 갤러리의 고정을 해제한 후 시도해주세요.', 'warning')
                return redirect(url_for('admin.list_gallery'))
        
        group.is_pinned = new_state
        group.updated_at = datetime.utcnow()
        group.save()
        
        try:
            from routes.main import clear_gallery_cache
            clear_gallery_cache()
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
        
        if new_state:
            pinned_count = len([g for g in GalleryGroup.query_all_ordered() if g.is_pinned])
            flash(f'"{group.title}" 갤러리가 상단에 고정되었습니다. (현재 {pinned_count}/3개 고정)')
        else:
            flash(f'"{group.title}" 갤러리의 상단 고정이 해제되었습니다.')
            
    except Exception as e:
        print(f"Error toggling gallery pin: {str(e)}")
        flash('갤러리 상단 고정 상태 변경 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_gallery'))


@admin.route('/services')
@login_required
def list_services():
    services = Service.query_all()
    return render_template('admin/services.html', services=services)


@admin.route('/service/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_service(id):
    service = Service.get_or_404(id)
    
    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.category = request.form['category']
        
        details = request.form.getlist('details[]')
        service.details = json.dumps(details)
        
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
        service.save()
        
        trigger_translation('service', service)
        
        flash('서비스가 수정되었습니다.')
        return redirect(url_for('admin.list_services'))
    
    details = json.loads(service.details) if service.details else []
    packages = json.loads(service.packages) if service.packages else []
        
    return render_template('admin/edit_service.html', 
                         service=service,
                         details=details,
                         packages=packages)


@admin.route('/services/delete/<int:id>')
@login_required
def delete_service(id):
    service = Service.get_or_404(id)
    
    # 관련 옵션들도 삭제
    for option in service.options:
        option.delete()
    
    service.delete()
    flash('서비스가 삭제되었습니다.')
    return redirect(url_for('admin.list_services'))


@admin.route('/services/<int:service_id>/options')
@login_required
def list_options(service_id):
    service = Service.get_or_404(service_id)
    return render_template('admin/options.html', service=service)


@admin.route('/services/options/add', methods=['GET', 'POST'])
@login_required
def add_option_standalone():
    """카테고리를 선택해서 새로운 서비스 옵션을 추가하는 독립형 라우트"""
    services = Service.query_all()
    
    if request.method == 'POST':
        service_id = int(request.form['service_id'])
        service = Service.get_or_404(service_id)
        
        option = ServiceOption(
            service_id=service_id,
            name=request.form['name'],
            description=request.form['description'],
            detailed_description=request.form.get('detailed_description', '')
        )
        
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            packages_list = []
            for line in packages_text.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': parts[4].strip()
                        }
                        packages_list.append(package)
                    elif len(parts) >= 4:
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
                    elif len(parts) >= 3:
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
        
        option.save()
        
        # 서비스 옵션 캐시 클리어
        from routes.main import clear_service_option_cache
        clear_service_option_cache(option.id)
        
        trigger_translation('service_option', option)
        
        flash(f'{service.name} 카테고리에 "{option.name}" 서비스가 추가되었습니다.')
        return redirect(url_for('admin.list_services'))
    
    return render_template('admin/add_option_standalone.html', services=services)


@admin.route('/services/<int:service_id>/options/add', methods=['GET', 'POST'])
@login_required
def add_option(service_id):
    service = Service.get_or_404(service_id)
    
    if request.method == 'POST':
        option = ServiceOption(
            service_id=service_id,
            name=request.form['name'],
            description=request.form['description'],
            detailed_description=request.form.get('detailed_description', '')
        )
        
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            packages_list = []
            for line in packages_text.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 5:
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': parts[4].strip()
                        }
                        packages_list.append(package)
                    elif len(parts) >= 4:
                        package = {
                            'name': parts[0].strip(),
                            'description': parts[1].strip(),
                            'duration': parts[2].strip(),
                            'price': parts[3].strip(),
                            'notes': ''
                        }
                        packages_list.append(package)
                    elif len(parts) >= 3:
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
        
        option.save()
        
        # 서비스 옵션 캐시 클리어
        from routes.main import clear_service_option_cache
        clear_service_option_cache(option.id)
        
        trigger_translation('service_option', option)
        
        flash('옵션이 추가되었습니다.')
        return redirect(url_for('admin.list_options', service_id=service_id))
    
    return render_template('admin/add_option.html', service=service)


@admin.route('/services/options/<int:option_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_option(option_id):
    option = ServiceOption.get_or_404(option_id)
    
    if request.method == 'POST':
        print(f"🔧 서비스 옵션 편집 시작 - ID: {option_id}")
        
        option.name = request.form['name']
        option.description = request.form['description']
        option.detailed_description = request.form.get('detailed_description', '')
        
        # 예약 조건 필드 업데이트
        def update_field(form_value):
            if form_value is not None and form_value.strip():
                return form_value
            return None
        
        option.booking_method = update_field(request.form.get('booking_method'))
        option.payment_info = update_field(request.form.get('payment_info'))
        option.guide_info = update_field(request.form.get('guide_info'))
        option.refund_policy_text = update_field(request.form.get('refund_policy_text'))
        option.refund_policy_table = update_field(request.form.get('refund_policy_table'))
        option.overtime_charge_table = update_field(request.form.get('overtime_charge_table'))
        
        # 상세 내용 처리
        details_text = request.form.get('details', '')
        if details_text.strip():
            details_list = [line.strip() for line in details_text.split('\n') if line.strip()]
            option.details = json.dumps(details_list, ensure_ascii=False)
        else:
            option.details = None
        
        # 패키지 정보 처리
        packages_text = request.form.get('packages', '')
        if packages_text.strip():
            try:
                packages_data = json.loads(packages_text)
                
                if isinstance(packages_data, dict) and 'tables' in packages_data:
                    valid_tables = []
                    for table in packages_data.get('tables', []):
                        valid_packages = []
                        for pkg in table.get('packages', []):
                            if pkg.get('name', '').strip():
                                valid_packages.append({
                                    'name': pkg.get('name', '').strip(),
                                    'description': pkg.get('description', '').strip(),
                                    'duration': pkg.get('duration', '').strip(),
                                    'price': pkg.get('price', '').strip(),
                                    'notes': pkg.get('notes', '').strip()
                                })
                        valid_tables.append({
                            'title': table.get('title', '').strip(),
                            'order': table.get('order', len(valid_tables)),
                            'packages': valid_packages
                        })
                    
                    option.packages = json.dumps({'tables': valid_tables}, ensure_ascii=False) if valid_tables else None
                elif isinstance(packages_data, list):
                    option.packages = json.dumps({'tables': [{'title': '', 'order': 0, 'packages': packages_data}]}, ensure_ascii=False)
                else:
                    option.packages = packages_text
            except json.JSONDecodeError:
                packages_list = []
                for line in packages_text.split('\n'):
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 5:
                            package = {
                                'name': parts[0].strip(),
                                'description': parts[1].strip(),
                                'duration': parts[2].strip(),
                                'price': parts[3].strip(),
                                'notes': parts[4].strip()
                            }
                            packages_list.append(package)
                        elif len(parts) >= 4:
                            package = {
                                'name': parts[0].strip(),
                                'description': parts[1].strip(),
                                'duration': parts[2].strip(),
                                'price': parts[3].strip(),
                                'notes': ''
                            }
                            packages_list.append(package)
                        elif len(parts) >= 3:
                            package = {
                                'name': parts[0].strip(),
                                'description': parts[1].strip(),
                                'duration': '',
                                'price': parts[2].strip(),
                                'notes': ''
                            }
                            packages_list.append(package)
                if packages_list:
                    option.packages = json.dumps({'tables': [{'title': '', 'order': 0, 'packages': packages_list}]}, ensure_ascii=False)
                else:
                    option.packages = None
        else:
            option.packages = None
        
        try:
            option.save()
            print(f"✅ MongoDB 저장 성공 - 옵션 ID: {option_id}")
            
            # 서비스 옵션 캐시 클리어
            from routes.main import clear_service_option_cache
            clear_service_option_cache(option_id)
            
            flash('옵션이 수정되었습니다.')
            trigger_translation('service_option', option)
        except Exception as e:
            print(f"❌ MongoDB 저장 실패: {str(e)}")
            flash('옵션 수정 중 오류가 발생했습니다.', 'error')
        
        return redirect(url_for('admin.list_services'))
    
    # GET 요청
    details_text = ''
    if option.details:
        try:
            details_list = json.loads(option.details)
            details_text = '\n'.join(details_list)
        except:
            details_text = option.details
    
    packages_text = option.packages or ''
    
    return render_template('admin/edit_option.html', 
                         option=option, 
                         details_text=details_text,
                         packages_text=packages_text)


@admin.route('/services/options/<int:option_id>/delete')
@login_required
def delete_option(option_id):
    option = ServiceOption.get_or_404(option_id)
    service_name = option.name
    option.delete()
    
    # 서비스 옵션 캐시 클리어
    from routes.main import clear_service_option_cache
    clear_service_option_cache(option_id)
    
    flash(f'서비스 "{service_name}"이(가) 삭제되었습니다.')
    return redirect(url_for('admin.list_services'))


@admin.route('/bookings')
@login_required
def list_bookings():
    try:
        kst = pytz.timezone('Asia/Seoul')
        bookings = Booking.query_all_ordered()
        
        for booking in bookings:
            if booking.created_at and isinstance(booking.created_at, datetime):
                if booking.created_at.tzinfo is None:
                    booking.created_at = pytz.utc.localize(booking.created_at).astimezone(kst)
                else:
                    booking.created_at = booking.created_at.astimezone(kst)
        
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
            booking = Booking.get_by_id(id)
            if booking:
                booking.status = status
                booking.save()
                flash('예약 상태가 업데이트되었습니다.')
    except Exception as e:
        print(f"Error updating booking status: {str(e)}")
        flash('예약 상태 업데이트 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_bookings'))


@admin.route('/booking/<int:id>/delete')
@login_required
def delete_booking(id):
    try:
        Booking.delete_by_id(id)
        flash('예약이 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting booking: {str(e)}")
        flash('예약 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_bookings'))


@admin.route('/gallery')
@login_required
def list_gallery():
    try:
        kst = pytz.timezone('Asia/Seoul')
        gallery_groups = GalleryGroup.query_all_ordered()
        
        # 디버깅: 각 갤러리 그룹의 display_order 출력
        print(f"📋 list_gallery 조회 - 총 {len(gallery_groups)}개 갤러리 그룹")
        for group in gallery_groups:
            print(f"  - ID={group.id}, title={group.title}, display_order={group.display_order}, is_pinned={group.is_pinned}")
            if group.created_at and isinstance(group.created_at, datetime):
                if group.created_at.tzinfo is None:
                    group.created_at = pytz.utc.localize(group.created_at).astimezone(kst)
                else:
                    group.created_at = group.created_at.astimezone(kst)
        
        return render_template('admin/list_gallery.html', gallery_groups=gallery_groups)
    except Exception as e:
        print(f"Error in list_gallery: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('갤러리 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/list_gallery.html', gallery_groups=[])


@admin.route('/inquiries')
@login_required
def list_inquiries():
    try:
        kst = pytz.timezone('Asia/Seoul')
        # 스팸이 아닌 문의만 표시 (기본)
        inquiries = Inquiry.query_non_spam()
        
        for inquiry in inquiries:
            if inquiry.created_at and isinstance(inquiry.created_at, datetime):
                if inquiry.created_at.tzinfo is None:
                    inquiry.created_at = pytz.utc.localize(inquiry.created_at).astimezone(kst)
                else:
                    inquiry.created_at = inquiry.created_at.astimezone(kst)
        
        # 스팸 문의 개수
        spam_count = len(Inquiry.query_spam())
        
        return render_template('admin/inquiries.html', inquiries=inquiries, spam_count=spam_count)
    except Exception as e:
        print(f"Error in list_inquiries: {str(e)}")
        flash('문의 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/inquiries.html', inquiries=[], spam_count=0)


@admin.route('/inquiries/spam')
@login_required
def list_spam_inquiries():
    """스팸으로 분류된 문의 목록"""
    try:
        kst = pytz.timezone('Asia/Seoul')
        inquiries = Inquiry.query_spam()
        
        for inquiry in inquiries:
            if inquiry.created_at and isinstance(inquiry.created_at, datetime):
                if inquiry.created_at.tzinfo is None:
                    inquiry.created_at = pytz.utc.localize(inquiry.created_at).astimezone(kst)
                else:
                    inquiry.created_at = inquiry.created_at.astimezone(kst)
        
        return render_template('admin/spam_inquiries.html', inquiries=inquiries)
    except Exception as e:
        print(f"Error in list_spam_inquiries: {str(e)}")
        flash('스팸 문의 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/spam_inquiries.html', inquiries=[])


@admin.route('/inquiries/<id>/unmark-spam', methods=['POST'])
@login_required
def unmark_spam(id):
    """스팸 표시 해제"""
    try:
        inquiry = Inquiry.get_by_id(id)
        if inquiry:
            inquiry.is_spam = False
            inquiry.spam_reason = ''
            inquiry.save()
            flash('스팸 표시가 해제되었습니다.')
    except Exception as e:
        print(f"Error unmarking spam: {str(e)}")
        flash('스팸 표시 해제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_spam_inquiries'))


@admin.route('/inquiries/<id>/status', methods=['POST'])
@login_required
def update_inquiry_status(id):
    try:
        status = request.form.get('status')
        inquiry = Inquiry.get_by_id(id)
        if inquiry:
            inquiry.status = status
            inquiry.save()
            flash('문의 상태가 업데이트되었습니다.')
    except Exception as e:
        print(f"Error updating inquiry status: {str(e)}")
        flash('문의 상태 업데이트 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_inquiries'))


@admin.route('/inquiries/<id>/delete', methods=['POST'])
@login_required
def delete_inquiry(id):
    try:
        Inquiry.delete_by_id(id)
        flash('문의가 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting inquiry: {str(e)}")
        flash('문의 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_inquiries'))


@admin.route('/reset-admin-password/<username>/<new_password>')
def reset_admin_password(username, new_password):
    """임시 관리자 비밀번호 재설정 라우트"""
    token = request.args.get('token')
    if token != 'stylegrapher':
        return "Unauthorized", 401
    
    try:
        user = User.get_by_username(username)
        if not user:
            return f"User {username} not found", 404
        
        user.set_password(new_password)
        user.save()
        
        return f"Password for {username} has been reset successfully"
    except Exception as e:
        print(f"Error resetting password: {str(e)}")
        return f"Error resetting password: {str(e)}", 500


@admin.route('/image/<image_id>')
def get_image(image_id):
    """GridFS 및 레거시 저장소에서 이미지 조회"""
    try:
        # 1. GridFS에서 이미지 검색 시도
        try:
            binary_data, content_type = get_image_from_gridfs(image_id)
            if binary_data:
                response = make_response(binary_data)
                response.headers.set('Content-Type', content_type)
                response.headers.set('Cache-Control', 'public, max-age=86400')
                return response
        except Exception as gridfs_error:
            print(f"GridFS 조회 중 오류: {str(gridfs_error)}")
        
        # 2. 레거시 MongoDB 컬렉션에서 검색
        try:
            db = get_mongo_db()
            images_collection = db['gallery']
            image_doc = images_collection.find_one({'_id': image_id})
            if image_doc and 'binary_data' in image_doc:
                response = make_response(image_doc['binary_data'])
                response.headers.set('Content-Type', image_doc.get('content_type', 'image/jpeg'))
                response.headers.set('Cache-Control', 'public, max-age=86400')
                return response
        except Exception as mongo_error:
            print(f"레거시 MongoDB 검색 중 오류: {str(mongo_error)}")
        
        # 3. 로컬 파일 시스템에서 검색
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_id)
        if os.path.exists(file_path):
            content_type = 'image/jpeg'
            if image_id.lower().endswith('.png'):
                content_type = 'image/png'
            elif image_id.lower().endswith('.gif'):
                content_type = 'image/gif'
                
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            response = make_response(image_data)
            response.headers.set('Content-Type', content_type)
            response.headers.set('Cache-Control', 'public, max-age=86400')
            return response
        
        return "Image not found", 404
            
    except Exception as e:
        print(f"이미지 검색 중 오류 발생: {str(e)}")
        return "Error retrieving image", 500


# Fade Text (CollageText) 관리
@admin.route('/fade-texts')
@login_required
def list_fade_texts():
    try:
        fade_texts = CollageText.query_all_ordered()
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
            fade_text.save()
            
            trigger_translation('collage_text', fade_text)
            
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
        fade_text = CollageText.get_or_404(id)
        
        if request.method == 'POST':
            text = request.form.get('text', '').strip()
            order = request.form.get('order', 0, type=int)
            
            if not text:
                flash('텍스트를 입력해주세요.', 'error')
                return render_template('admin/edit_fade_text.html', fade_text=fade_text)
            
            fade_text.text = text
            fade_text.order = order
            fade_text.updated_at = datetime.utcnow()
            fade_text.save()
            
            trigger_translation('collage_text', fade_text)
            
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
        CollageText.delete_by_id(id)
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
        
        def validate_rgb(value):
            return max(0, min(255, value))
        
        settings.main_color_r = validate_rgb(request.form.get('main_color_r', 139, type=int))
        settings.main_color_g = validate_rgb(request.form.get('main_color_g', 95, type=int))
        settings.main_color_b = validate_rgb(request.form.get('main_color_b', 191, type=int))
        
        settings.sub_color_r = validate_rgb(request.form.get('sub_color_r', 65, type=int))
        settings.sub_color_g = validate_rgb(request.form.get('sub_color_g', 26, type=int))
        settings.sub_color_b = validate_rgb(request.form.get('sub_color_b', 75, type=int))
        
        settings.background_color_r = validate_rgb(request.form.get('background_color_r', 255, type=int))
        settings.background_color_g = validate_rgb(request.form.get('background_color_g', 255, type=int))
        settings.background_color_b = validate_rgb(request.form.get('background_color_b', 255, type=int))
        
        settings.updated_at = datetime.utcnow()
        settings.save()
        
        flash('사이트 색상이 성공적으로 업데이트되었습니다.')
        return redirect(url_for('admin.site_colors'))
        
    except Exception as e:
        print(f"Error updating site colors: {str(e)}")
        flash('색상 업데이트 중 오류가 발생했습니다.', 'error')
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
        terms.save()
        
        # 다국어 번역 트리거
        trigger_translation('terms_of_service', terms)
        
        flash('이용약관이 성공적으로 업데이트되었습니다.', 'success')
        
    except Exception as e:
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
        policy.save()
        
        # 다국어 번역 트리거
        trigger_translation('privacy_policy', policy)
        
        flash('개인정보처리방침이 성공적으로 업데이트되었습니다.', 'success')
        
    except Exception as e:
        flash(f'오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_privacy'))


# 회사 안내 정보 관리 (RAG 컨텍스트용)
@admin.route('/company-info')
@login_required
def manage_company_info():
    try:
        company_info = CompanyInfo.get_current_info()
        return render_template('admin/company_info.html', company_info=company_info)
    except Exception as e:
        flash(f'회사 정보 로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))


@admin.route('/company-info/update', methods=['POST'])
@login_required
def update_company_info():
    try:
        company_info = CompanyInfo.get_current_info()
        
        company_info.company_name = request.form.get('company_name', '').strip()
        company_info.email = request.form.get('email', '').strip()
        company_info.business_type = request.form.get('business_type', '').strip()
        company_info.service_areas = request.form.get('service_areas', '').strip()
        company_info.customer_service_principles = request.form.get('customer_service_principles', '').strip()
        company_info.additional_info = request.form.get('additional_info', '').strip()
        company_info.updated_at = datetime.utcnow()
        company_info.save()
        
        flash('회사 정보가 성공적으로 업데이트되었습니다. RAG 컨텍스트에 자동으로 반영됩니다.', 'success')
        
    except Exception as e:
        flash(f'오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_company_info'))


# About 페이지 콘텐츠 관리 (RAG 컨텍스트용)
@admin.route('/about-content')
@login_required
def manage_about_content():
    try:
        about_content = AboutContent.get_current_content()
        return render_template('admin/about_content.html', about_content=about_content)
    except Exception as e:
        flash(f'About 페이지 콘텐츠 로드 중 오류가 발생했습니다: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))


@admin.route('/about-content/update', methods=['POST'])
@login_required
def update_about_content():
    try:
        about_content = AboutContent.get_current_content()
        
        about_content.hero_title = request.form.get('hero_title', '').strip()
        about_content.hero_subtitle = request.form.get('hero_subtitle', '').strip()
        about_content.hero_description = request.form.get('hero_description', '').strip()
        about_content.hero_message = request.form.get('hero_message', '').strip()
        about_content.brand_philosophy = request.form.get('brand_philosophy', '').strip()
        about_content.fashion_icons = request.form.get('fashion_icons', '').strip()
        about_content.current_era = request.form.get('current_era', '').strip()
        about_content.experience = request.form.get('experience', '').strip()
        about_content.mission = request.form.get('mission', '').strip()
        about_content.updated_at = datetime.utcnow()
        about_content.save()
        
        flash('About 페이지 콘텐츠가 성공적으로 업데이트되었습니다. RAG 컨텍스트 및 About 페이지에 자동 반영됩니다.', 'success')
        
    except Exception as e:
        flash(f'오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.manage_about_content'))


@admin.route('/security-dashboard')
@login_required
def security_dashboard():
    """보안 대시보드"""
    summary = security_monitor.get_attack_summary()
    return render_template('admin/security_dashboard.html', security_summary=summary)


@admin.route('/security-report')
@login_required
def security_report():
    """보안 리포트 다운로드"""
    hours = request.args.get('hours', 24, type=int)
    report = security_monitor.export_security_report(hours)
    
    response = make_response(json.dumps(report, indent=2, default=str))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=security_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    return response


# 다국어 번역 관리
@admin.route('/translations')
@login_required
def translations_dashboard():
    """번역 관리 대시보드"""
    from utils.translation import translations_collection, SUPPORTED_LANGUAGES
    
    stats = {
        'total': 0,
        'by_type': {},
        'languages': SUPPORTED_LANGUAGES
    }
    
    if translations_collection:
        try:
            stats['total'] = translations_collection.count_documents({})
            
            pipeline = [
                {"$group": {"_id": "$source_type", "count": {"$sum": 1}}}
            ]
            for doc in translations_collection.aggregate(pipeline):
                stats['by_type'][doc['_id']] = doc['count']
        except Exception as e:
            print(f"번역 통계 조회 오류: {str(e)}")
    
    return render_template('admin/translations.html', stats=stats)


@admin.route('/translations/migrate', methods=['POST'])
@login_required
def migrate_translations():
    """전체 데이터 번역 마이그레이션 (비동기)"""
    import threading
    
    def run_migration():
        try:
            from utils.translation import migrate_all_translations
            migrate_all_translations()
        except Exception as e:
            print(f"번역 마이그레이션 오류: {str(e)}")
    
    thread = threading.Thread(target=run_migration)
    thread.daemon = True
    thread.start()
    
    flash('번역 마이그레이션이 백그라운드에서 시작되었습니다. 완료까지 몇 분이 소요될 수 있습니다.', 'info')
    return redirect(url_for('admin.translations_dashboard'))


@admin.route('/translations/translate/<source_type>/<int:source_id>', methods=['POST'])
@login_required
def translate_single(source_type, source_id):
    """단일 항목 번역"""
    try:
        if source_type == 'service':
            service = Service.get_or_404(source_id)
            trigger_translation('service', service)
            flash(f'서비스 "{service.name}" 번역이 시작되었습니다.', 'success')
        elif source_type == 'service_option':
            option = ServiceOption.get_or_404(source_id)
            trigger_translation('service_option', option)
            flash(f'서비스 옵션 "{option.name}" 번역이 시작되었습니다.', 'success')
        elif source_type == 'collage_text':
            ct = CollageText.get_or_404(source_id)
            trigger_translation('collage_text', ct)
            flash(f'Fade Text 번역이 시작되었습니다.', 'success')
        elif source_type == 'gallery_group':
            gg = GalleryGroup.get_or_404(source_id)
            trigger_translation('gallery_group', gg)
            flash(f'갤러리 "{gg.title}" 번역이 시작되었습니다.', 'success')
        else:
            flash('지원하지 않는 타입입니다.', 'error')
    except Exception as e:
        flash(f'번역 중 오류가 발생했습니다: {str(e)}', 'error')
    
    return redirect(url_for('admin.translations_dashboard'))


# ========== GridFS 저장소 관리 ==========

@admin.route('/storage')
@login_required
def storage_dashboard():
    """GridFS 저장소 대시보드"""
    stats = get_gridfs_stats()
    
    if 'gridfs_total_size' in stats:
        size_mb = stats['gridfs_total_size'] / (1024 * 1024)
        stats['gridfs_total_size_mb'] = f"{size_mb:.2f}"
    
    return render_template('admin/storage_dashboard.html', stats=stats)


@admin.route('/storage/migrate', methods=['POST'])
@login_required
def migrate_to_gridfs():
    """레거시 이미지를 GridFS로 마이그레이션 (백그라운드)"""
    import threading
    
    def run_migration():
        try:
            success, fail, skip = migrate_legacy_to_gridfs(batch_size=50)
            print(f"GridFS 마이그레이션 완료: 성공 {success}, 실패 {fail}, 건너뜀 {skip}")
        except Exception as e:
            print(f"GridFS 마이그레이션 오류: {str(e)}")
    
    thread = threading.Thread(target=run_migration)
    thread.daemon = True
    thread.start()
    
    flash('GridFS 마이그레이션이 백그라운드에서 시작되었습니다. 완료까지 몇 분이 소요될 수 있습니다.', 'info')
    return redirect(url_for('admin.storage_dashboard'))


@admin.route('/storage/stats')
@login_required
def storage_stats_json():
    """GridFS 저장소 통계 JSON 반환"""
    stats = get_gridfs_stats()
    return jsonify(stats)


# ========== 알림 이메일 관리 ==========

@admin.route('/notification-emails')
@login_required
def list_notification_emails():
    """알림 이메일 목록"""
    try:
        emails = AdminNotificationEmail.query_all_ordered()
        return render_template('admin/notification_emails.html', emails=emails)
    except Exception as e:
        print(f"Error listing notification emails: {str(e)}")
        flash('알림 이메일 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/notification_emails.html', emails=[])


@admin.route('/notification-emails/add', methods=['POST'])
@login_required
def add_notification_email():
    """알림 이메일 추가"""
    try:
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        receive_inquiries = request.form.get('receive_inquiries') == 'on'
        receive_bookings = request.form.get('receive_bookings') == 'on'
        
        if not email:
            flash('이메일 주소를 입력해주세요.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        # 이메일 형식 간단 검증
        if '@' not in email or '.' not in email:
            flash('올바른 이메일 형식이 아닙니다.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        # 중복 확인
        existing = AdminNotificationEmail.get_by_email(email)
        if existing:
            flash('이미 등록된 이메일 주소입니다.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        notification_email = AdminNotificationEmail(
            email=email,
            name=name,
            is_active=True,
            receive_inquiries=receive_inquiries,
            receive_bookings=receive_bookings
        )
        notification_email.save()
        
        flash(f'알림 이메일 "{email}"이(가) 추가되었습니다.', 'success')
        
    except Exception as e:
        print(f"Error adding notification email: {str(e)}")
        flash('알림 이메일 추가 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notification_emails'))


@admin.route('/notification-emails/<int:id>/toggle-active', methods=['POST'])
@login_required
def toggle_notification_email_active(id):
    """알림 이메일 활성화/비활성화 토글"""
    try:
        email_obj = AdminNotificationEmail.get_by_id(id)
        if not email_obj:
            flash('이메일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        email_obj.is_active = not email_obj.is_active
        email_obj.updated_at = datetime.utcnow()
        email_obj.save()
        
        status = '활성화' if email_obj.is_active else '비활성화'
        flash(f'"{email_obj.email}" 이메일이 {status}되었습니다.', 'success')
        
    except Exception as e:
        print(f"Error toggling notification email: {str(e)}")
        flash('이메일 상태 변경 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notification_emails'))


@admin.route('/notification-emails/<int:id>/update', methods=['POST'])
@login_required
def update_notification_email(id):
    """알림 이메일 정보 수정"""
    try:
        email_obj = AdminNotificationEmail.get_by_id(id)
        if not email_obj:
            flash('이메일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        name = request.form.get('name', '').strip()
        receive_inquiries = request.form.get('receive_inquiries') == 'on'
        receive_bookings = request.form.get('receive_bookings') == 'on'
        
        email_obj.name = name
        email_obj.receive_inquiries = receive_inquiries
        email_obj.receive_bookings = receive_bookings
        email_obj.updated_at = datetime.utcnow()
        email_obj.save()
        
        flash(f'"{email_obj.email}" 이메일 설정이 업데이트되었습니다.', 'success')
        
    except Exception as e:
        print(f"Error updating notification email: {str(e)}")
        flash('이메일 설정 수정 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notification_emails'))


@admin.route('/notification-emails/<int:id>/delete', methods=['POST'])
@login_required
def delete_notification_email(id):
    """알림 이메일 삭제"""
    try:
        email_obj = AdminNotificationEmail.get_by_id(id)
        if not email_obj:
            flash('이메일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_notification_emails'))
        
        email_address = email_obj.email
        email_obj.delete()
        
        flash(f'"{email_address}" 이메일이 삭제되었습니다.', 'success')
        
    except Exception as e:
        print(f"Error deleting notification email: {str(e)}")
        flash('이메일 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notification_emails'))


# ========== 로그 분석 시스템 ==========

import re
from collections import defaultdict

def parse_log_line(line: str) -> dict:
    """로그 라인을 파싱하여 구조화된 데이터로 반환"""
    result = {
        'raw': line.strip(),
        'timestamp': None,
        'level': 'INFO',
        'logger': None,
        'message': line.strip(),
        'ip': None,
        'user_agent': None,
        'details': None
    }
    
    # Flask/Werkzeug 요청 로그 패턴: 127.0.0.1 - - [01/Dec/2025 11:39:09] "GET /gallery HTTP/1.1" 404 -
    werkzeug_pattern = r'^([\d.]+) - - \[([^\]]+)\] "([^"]+)" (\d+) -?$'
    werkzeug_match = re.match(werkzeug_pattern, line.strip())
    if werkzeug_match:
        result['ip'] = werkzeug_match.group(1)
        result['timestamp'] = werkzeug_match.group(2)
        result['message'] = werkzeug_match.group(3)
        status_code = int(werkzeug_match.group(4))
        if status_code >= 500:
            result['level'] = 'ERROR'
        elif status_code >= 400:
            result['level'] = 'WARNING'
        else:
            result['level'] = 'INFO'
        result['details'] = f'Status: {status_code}'
        return result
    
    # 표준 로그 패턴: 2025-12-01 11:39:09,027 - SECURITY - WARNING - ...
    standard_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},?\d*) - (\w+) - (\w+) - (.+)$'
    standard_match = re.match(standard_pattern, line.strip())
    if standard_match:
        result['timestamp'] = standard_match.group(1)
        result['logger'] = standard_match.group(2)
        result['level'] = standard_match.group(3).upper()
        rest = standard_match.group(4)
        
        # IP, UA, Details 추출
        ip_match = re.search(r'IP: ([\d.]+)', rest)
        if ip_match:
            result['ip'] = ip_match.group(1)
        
        ua_match = re.search(r'UA: ([^-]+)', rest)
        if ua_match:
            result['user_agent'] = ua_match.group(1).strip()
        
        details_match = re.search(r'Details: (.+)$', rest)
        if details_match:
            result['details'] = details_match.group(1)
        
        result['message'] = rest
        return result
    
    # 일반 로그 (MongoDB 연결 등)
    if 'MongoDB' in line or 'GridFS' in line:
        result['logger'] = 'DATABASE'
        if '성공' in line or 'success' in line.lower():
            result['level'] = 'INFO'
        elif '실패' in line or 'error' in line.lower() or 'fail' in line.lower():
            result['level'] = 'ERROR'
    elif 'WARNING' in line.upper():
        result['level'] = 'WARNING'
    elif 'ERROR' in line.upper():
        result['level'] = 'ERROR'
    elif 'DEBUG' in line.upper():
        result['level'] = 'DEBUG'
    
    return result


def get_log_statistics(logs: list) -> dict:
    """로그 통계 계산"""
    stats = {
        'total': len(logs),
        'by_level': defaultdict(int),
        'by_logger': defaultdict(int),
        'by_ip': defaultdict(int),
        'recent_errors': [],
        'recent_warnings': []
    }
    
    for log in logs:
        stats['by_level'][log['level']] += 1
        if log['logger']:
            stats['by_logger'][log['logger']] += 1
        if log['ip']:
            stats['by_ip'][log['ip']] += 1
        
        if log['level'] == 'ERROR' and len(stats['recent_errors']) < 10:
            stats['recent_errors'].append(log)
        elif log['level'] == 'WARNING' and len(stats['recent_warnings']) < 10:
            stats['recent_warnings'].append(log)
    
    # defaultdict을 일반 dict로 변환
    stats['by_level'] = dict(stats['by_level'])
    stats['by_logger'] = dict(stats['by_logger'])
    stats['by_ip'] = dict(sorted(stats['by_ip'].items(), key=lambda x: x[1], reverse=True)[:20])
    
    return stats


@admin.route('/logs')
@login_required
def log_analysis():
    """로그 분석 대시보드"""
    try:
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.log')
        
        # 필터 파라미터
        level_filter = request.args.get('level', '').upper()
        search_query = request.args.get('search', '').strip()
        ip_filter = request.args.get('ip', '').strip()
        limit = request.args.get('limit', 500, type=int)
        
        logs = []
        all_logs = []
        
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 최신 로그가 위로 오도록 역순 처리
            for line in reversed(lines):
                if not line.strip():
                    continue
                
                parsed = parse_log_line(line)
                all_logs.append(parsed)
                
                # 필터 적용
                if level_filter and parsed['level'] != level_filter:
                    continue
                if search_query and search_query.lower() not in parsed['raw'].lower():
                    continue
                if ip_filter and parsed['ip'] != ip_filter:
                    continue
                
                logs.append(parsed)
                
                if len(logs) >= limit:
                    break
        
        # 통계 계산 (전체 로그 기준)
        stats = get_log_statistics(all_logs[:5000])  # 최대 5000개로 통계 계산
        
        return render_template('admin/log_analysis.html',
                             logs=logs,
                             stats=stats,
                             level_filter=level_filter,
                             search_query=search_query,
                             ip_filter=ip_filter,
                             limit=limit,
                             log_file_exists=os.path.exists(log_file_path))
                             
    except Exception as e:
        print(f"Error in log analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('로그 분석 중 오류가 발생했습니다.', 'error')
        return render_template('admin/log_analysis.html',
                             logs=[],
                             stats={'total': 0, 'by_level': {}, 'by_logger': {}, 'by_ip': {}, 'recent_errors': [], 'recent_warnings': []},
                             level_filter='',
                             search_query='',
                             ip_filter='',
                             limit=500,
                             log_file_exists=False)


@admin.route('/logs/download')
@login_required
def download_logs():
    """로그 파일 다운로드"""
    try:
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.log')
        
        if not os.path.exists(log_file_path):
            flash('로그 파일이 존재하지 않습니다.', 'error')
            return redirect(url_for('admin.log_analysis'))
        
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        
        response = make_response(log_content)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=app_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        return response
        
    except Exception as e:
        print(f"Error downloading logs: {str(e)}")
        flash('로그 다운로드 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.log_analysis'))


@admin.route('/logs/clear', methods=['POST'])
@login_required
def clear_logs():
    """로그 파일 초기화 (백업 후 삭제)"""
    try:
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.log')
        
        if not os.path.exists(log_file_path):
            flash('로그 파일이 존재하지 않습니다.', 'error')
            return redirect(url_for('admin.log_analysis'))
        
        # 백업 생성
        backup_path = os.path.join(
            os.path.dirname(log_file_path),
            f'app_log_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        # 로그 파일 초기화
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Log cleared at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        flash(f'로그가 초기화되었습니다. 백업 파일: {os.path.basename(backup_path)}', 'success')
        
    except Exception as e:
        print(f"Error clearing logs: {str(e)}")
        flash('로그 초기화 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.log_analysis'))


@admin.route('/logs/stats')
@login_required
def log_stats_json():
    """로그 통계 JSON 반환 (AJAX용)"""
    try:
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.log')
        
        if not os.path.exists(log_file_path):
            return jsonify({'error': 'Log file not found'}), 404
        
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        all_logs = []
        for line in lines[-5000:]:  # 최근 5000개만
            if line.strip():
                all_logs.append(parse_log_line(line))
        
        stats = get_log_statistics(all_logs)
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== 세션 관리 ==========

@admin.route('/sessions')
@login_required
def sessions_dashboard():
    """세션 관리 대시보드"""
    from flask import session
    from flask_login import current_user
    
    try:
        # 현재 세션 정보
        current_session = {
            'language': session.get('language', 'ko'),
            'user_id': current_user.id if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None,
            'is_permanent': session.permanent
        }
        
        # 전체 사용자 수
        total_users = User.count()
        
        # 최근 로그인 활동 (예약/문의 접수 기준으로 추정)
        recent_bookings = Booking.query_all_ordered(limit=10)
        recent_inquiries = Inquiry.query_all_ordered(limit=10)
        
        # 언어별 분포 (최근 예약/문의 기준)
        language_dist = defaultdict(int)
        for booking in Booking.query_all_ordered(limit=100):
            lang = getattr(booking, 'language', 'ko') or 'ko'
            language_dist[lang] += 1
        
        return render_template('admin/sessions.html',
                             current_session=current_session,
                             total_users=total_users,
                             recent_bookings=recent_bookings,
                             recent_inquiries=recent_inquiries,
                             language_distribution=dict(language_dist))
                             
    except Exception as e:
        print(f"Error in sessions dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('세션 정보를 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/sessions.html',
                             current_session={},
                             total_users=0,
                             recent_bookings=[],
                             recent_inquiries=[],
                             language_distribution={})


# ========== 토큰 사용량 ==========

@admin.route('/token-usage')
@login_required
def token_usage_dashboard():
    """AI 토큰 사용량 대시보드"""
    from utils.ai_usage_tracker import get_usage_stats, get_recent_usage, get_daily_summary
    
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # 사용량 통계
        stats = get_usage_stats(hours=hours)
        
        # 최근 사용 내역
        recent_usage = get_recent_usage(limit=50)
        
        # 일별 요약
        daily_summary = get_daily_summary(days=30)
        
        return render_template('admin/token_usage.html',
                             stats=stats,
                             recent_usage=recent_usage,
                             daily_summary=daily_summary,
                             hours=hours)
                             
    except Exception as e:
        print(f"Error in token usage dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('토큰 사용량 정보를 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/token_usage.html',
                             stats={'total_requests': 0, 'total_tokens': 0, 'total_cost': 0, 'by_type': {}, 'by_model': {}, 'hourly': []},
                             recent_usage=[],
                             daily_summary=[],
                             hours=24)


@admin.route('/token-usage/stats')
@login_required
def token_usage_stats_json():
    """토큰 사용량 통계 JSON 반환"""
    from utils.ai_usage_tracker import get_usage_stats
    
    try:
        hours = request.args.get('hours', 24, type=int)
        stats = get_usage_stats(hours=hours)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========== AI 인사이트 ==========

@admin.route('/ai-insights')
@login_required
def ai_insights_dashboard():
    """AI 인사이트 대시보드"""
    from utils.ai_usage_tracker import get_ai_insights, get_usage_stats, get_daily_summary
    
    try:
        # AI 인사이트 분석
        insights = get_ai_insights()
        
        # 기본 통계 (24시간)
        stats_24h = get_usage_stats(hours=24)
        
        # 일별 요약 (30일)
        daily_summary = get_daily_summary(days=30)
        
        # 주간 비교 데이터
        stats_7d = get_usage_stats(hours=168)  # 7일
        
        return render_template('admin/ai_insights.html',
                             insights=insights,
                             stats_24h=stats_24h,
                             stats_7d=stats_7d,
                             daily_summary=daily_summary)
                             
    except Exception as e:
        print(f"Error in AI insights dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('AI 인사이트를 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/ai_insights.html',
                             insights={'summary': {}, 'trends': {}, 'recommendations': [], 'top_usage': [], 'cost_analysis': {}},
                             stats_24h={'total_requests': 0, 'total_tokens': 0, 'total_cost': 0},
                             stats_7d={'total_requests': 0, 'total_tokens': 0, 'total_cost': 0},
                             daily_summary=[])


@admin.route('/ai-insights/export')
@login_required
def export_ai_insights():
    """AI 인사이트 리포트 다운로드"""
    from utils.ai_usage_tracker import get_ai_insights, get_usage_stats, get_daily_summary
    
    try:
        report = {
            'generated_at': datetime.now().isoformat(),
            'insights': get_ai_insights(),
            'stats_24h': get_usage_stats(hours=24),
            'stats_7d': get_usage_stats(hours=168),
            'daily_summary': get_daily_summary(days=30)
        }
        
        response = make_response(json.dumps(report, indent=2, default=str, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=ai_insights_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return response
        
    except Exception as e:
        print(f"Error exporting AI insights: {str(e)}")
        flash('AI 인사이트 내보내기 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.ai_insights_dashboard'))
