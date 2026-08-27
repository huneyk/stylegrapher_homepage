"""
Admin 라우트 - MongoDB 기반
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, make_response
from flask_login import login_required, login_user, logout_user
from extensions import login_manager
from werkzeug.utils import secure_filename
import os
from PIL import Image, ImageFile

# 손상된 이미지도 처리할 수 있도록 설정
ImageFile.LOAD_TRUNCATED_IMAGES = True
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
    TermsOfService, PrivacyPolicy, AdminNotificationEmail, CompanyInfo, AboutContent,
    PackagePhoto, PackagePhotoCategory, Notice
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
    'max_width': 600,
    'max_height': 700,
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


@admin.route('/gallery/update-slide-interval/<int:group_id>', methods=['POST'])
@login_required
def update_gallery_slide_interval(group_id):
    try:
        raw_value = request.form.get('slide_interval', '4')
        slide_interval = int(raw_value)

        if slide_interval < 1 or slide_interval > 30:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': '전환 간격은 1~30초 사이여야 합니다.'
                }), 400
            flash('전환 간격은 1~30초 사이여야 합니다.', 'error')
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

        group.slide_interval = slide_interval
        group.updated_at = datetime.utcnow()
        group.save()

        try:
            from routes.main import clear_gallery_cache
            clear_gallery_cache()
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f'갤러리 "{group.title}"의 전환 간격이 {slide_interval}초로 저장되었습니다.',
                'slide_interval': slide_interval
            })

        flash(f'사진 전환 간격이 {slide_interval}초로 저장되었습니다.')
    except ValueError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '올바른 숫자를 입력해주세요.'
            }), 400
        flash('올바른 숫자를 입력해주세요.', 'error')
    except Exception as e:
        print(f"Error updating gallery slide interval: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '전환 간격 업데이트 중 오류가 발생했습니다.'
            }), 500
        flash('전환 간격 업데이트 중 오류가 발생했습니다.', 'error')

    return redirect(url_for('admin.list_gallery'))


@admin.route('/gallery/update-image-order/<int:group_id>', methods=['POST'])
@login_required
def update_gallery_image_order(group_id):
    try:
        group = GalleryGroup.get_by_id(group_id)
        if not group:
            return jsonify({
                'success': False,
                'message': '갤러리를 찾을 수 없습니다.'
            }), 404

        data = request.get_json(silent=True) or {}
        image_ids = data.get('image_ids')
        if not isinstance(image_ids, list) or not image_ids:
            return jsonify({
                'success': False,
                'message': '이미지 순서 정보가 올바르지 않습니다.'
            }), 400

        images = Gallery.query_by_group(group_id)
        image_map = {str(img.id): img for img in images}

        if len(image_ids) != len(images) or any(str(image_id) not in image_map for image_id in image_ids):
            return jsonify({
                'success': False,
                'message': '이미지 목록이 일치하지 않습니다.'
            }), 400

        for index, image_id in enumerate(image_ids):
            image = image_map[str(image_id)]
            if image.order != index:
                image.order = index
                image.save()

        try:
            from routes.main import clear_gallery_cache
            clear_gallery_cache()
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")

        return jsonify({
            'success': True,
            'message': f'갤러리 "{group.title}"의 이미지 순서가 저장되었습니다.'
        })
    except Exception as e:
        print(f"Error updating gallery image order: {str(e)}")
        return jsonify({
            'success': False,
            'message': '이미지 순서 업데이트 중 오류가 발생했습니다.'
        }), 500


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
    """카테고리 설명 수정 - 카테고리명과 설명만 수정"""
    service = Service.get_or_404(id)
    
    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.save()
        
        trigger_translation('service', service)
        
        flash('카테고리 설명이 수정되었습니다.')
        return redirect(url_for('admin.list_services'))
        
    return render_template('admin/edit_service.html', service=service)


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
            description=request.form.get('description', ''),
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
            description=request.form.get('description', ''),
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
        option.description = request.form.get('description', '')
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
            binary_data, content_type, etag = get_image_from_gridfs(image_id)
            if binary_data:
                response = make_response(binary_data)
                response.headers.set('Content-Type', content_type)
                response.headers.set('Cache-Control', 'public, max-age=86400')
                if etag:
                    response.headers.set('ETag', etag)
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


# ========== 세션 관리 (사용자 세션 분석) ==========

@admin.route('/sessions')
@login_required
def sessions_dashboard():
    """사용자 세션 분석 대시보드"""
    from utils.visitor_tracker import get_visitor_sessions, get_visitor_stats
    
    try:
        # 필터 파라미터
        days = request.args.get('days', 30, type=int)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        sort_by = request.args.get('sort_by', 'timestamp')
        sort_order_str = request.args.get('sort_order', 'desc')
        sort_order = -1 if sort_order_str == 'desc' else 1
        ip_filter = request.args.get('ip', '').strip()
        country_filter = request.args.get('country', '').strip()
        
        # 오프셋 계산
        offset = (page - 1) * per_page
        
        # 세션 목록 조회
        sessions, total_count = get_visitor_sessions(
            days=days,
            limit=per_page,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            ip_filter=ip_filter if ip_filter else None,
            country_filter=country_filter if country_filter else None
        )
        
        # 통계 조회
        stats = get_visitor_stats(days=days)
        
        # 페이징 정보
        total_pages = (total_count + per_page - 1) // per_page
        
        # 시간대 변환 (KST)
        kst = pytz.timezone('Asia/Seoul')
        for session in sessions:
            if session.get('timestamp'):
                ts = session['timestamp']
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = pytz.utc.localize(ts)
                    session['timestamp_kst'] = ts.astimezone(kst)
        
        return render_template('admin/sessions.html',
                             sessions=sessions,
                             stats=stats,
                             total_count=total_count,
                             page=page,
                             per_page=per_page,
                             total_pages=total_pages,
                             days=days,
                             sort_by=sort_by,
                             sort_order=sort_order_str,
                             ip_filter=ip_filter,
                             country_filter=country_filter)
                             
    except Exception as e:
        print(f"❌ Error in sessions dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        # 오류 메시지는 관리자 페이지이므로 한국어로 유지하되, 로그에 상세 정보 출력
        # flash 메시지 대신 로그에만 기록하여 홈페이지에 오류가 표시되지 않도록 함
        print(f"⚠️ 세션 대시보드 오류 - 사용자에게는 빈 데이터 표시")
        return render_template('admin/sessions.html',
                             sessions=[],
                             stats={'total_sessions': 0, 'unique_visitors': 0, 'total_tokens': 0, 'total_cost': 0, 'by_country': {}, 'by_browser': {}, 'by_device': {}, 'by_page': {}, 'by_language': {}},
                             total_count=0,
                             page=1,
                             per_page=50,
                             total_pages=0,
                             days=30,
                             sort_by='timestamp',
                             sort_order='desc',
                             ip_filter='',
                             country_filter='')


@admin.route('/sessions/delete/<session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """세션 기록 삭제"""
    from utils.visitor_tracker import delete_visitor_session
    
    try:
        if delete_visitor_session(session_id):
            flash('세션 기록이 삭제되었습니다.', 'success')
        else:
            flash('세션 삭제에 실패했습니다.', 'error')
    except Exception as e:
        print(f"Error deleting session: {str(e)}")
        flash('세션 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.sessions_dashboard'))


@admin.route('/sessions/export')
@login_required
def export_sessions():
    """세션 데이터 내보내기"""
    from utils.visitor_tracker import export_visitor_data
    
    try:
        days = request.args.get('days', 30, type=int)
        data = export_visitor_data(days=days)
        
        response = make_response(json.dumps(data, indent=2, default=str, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=visitor_sessions_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        return response
        
    except Exception as e:
        print(f"Error exporting sessions: {str(e)}")
        flash('세션 데이터 내보내기 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.sessions_dashboard'))


# ========== 패키지 화보 관리 ==========

def save_package_photo_to_gridfs(file, package_photo_id=None):
    """패키지 화보 이미지를 1024x1024 이내로 리사이즈 후 GridFS에 저장 (OpenCV 사용)"""
    import cv2
    import numpy as np
    
    try:
        file.seek(0)
        filename = secure_filename(file.filename)
        
        # 원본 이미지 데이터 읽기
        img_data = file.read()
        original_size = len(img_data)
        
        # OpenCV로 이미지 디코딩 (PIL의 libjpeg 문제 우회)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise Exception("이미지 디코딩 실패")
        
        original_height, original_width = img.shape[:2]
        
        # 1024x1024 기준으로 리사이즈 (aspect ratio 유지, 가로/세로 중 큰 값 기준)
        max_size = 2048
        if original_width > max_size or original_height > max_size:
            # 가로/세로 중 더 큰 비율로 리사이즈
            width_ratio = max_size / original_width
            height_ratio = max_size / original_height
            ratio = min(width_ratio, height_ratio)
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        else:
            resized_img = img
            new_width, new_height = original_width, original_height
        
        # JPEG로 인코딩 (품질 85%)
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        _, img_encoded = cv2.imencode('.jpg', resized_img, encode_param)
        img_binary = img_encoded.tobytes()
        compressed_size = len(img_binary)
        content_type = 'image/jpeg'
        
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        print(f"PackagePhoto: 이미지 최적화 - {original_width}x{original_height} ({original_size/1024:.1f}KB) → "
              f"{new_width}x{new_height} ({compressed_size/1024:.1f}KB) [{compression_ratio:.1f}% 절약]")
        
        
        # GridFS에 저장
        image_id = str(uuid.uuid4())
        
        gridfs, db, _ = get_mongo_connection()
        if gridfs is None:
            raise Exception("GridFS 연결 실패")
        
        metadata = {
            'original_filename': filename,
            'content_type': content_type,
            'created_at': datetime.now(),
            'width': new_width,
            'height': new_height,
            'storage_type': 'gridfs',
            'usage': 'package_photo'
        }
        
        if package_photo_id is not None:
            metadata['package_photo_id'] = package_photo_id
        
        gridfs.put(
            img_binary,
            _id=image_id,
            filename=filename,
            content_type=content_type,
            metadata=metadata
        )
        
        print(f"PackagePhoto: 이미지 저장 완료 - ID: {image_id}")
        return image_id
        
    except Exception as e:
        print(f"PackagePhoto: 이미지 저장 오류 - {str(e)}")
        raise


@admin.route('/package-photos')
@login_required
def list_package_photos():
    """패키지 화보 목록"""
    try:
        # 서비스 옵션 ID 필터 (기본값: 11 - 패키지 화보)
        service_option_id = request.args.get('service_option_id', 11, type=int)
        
        package_photos = PackagePhoto.query_by_service_option(service_option_id, active_only=False)
        service_options = ServiceOption.query_all()
        
        # 카테고리 동기화 및 순서 정보 가져오기
        PackagePhotoCategory.sync_categories(service_option_id)
        category_order_map = PackagePhotoCategory.get_category_order_map(service_option_id)
        categories = PackagePhotoCategory.query_by_service_option(service_option_id)
        
        # 카테고리별로 그룹화
        photos_by_category = {}
        for photo in package_photos:
            category = photo.category or '미분류'
            if category not in photos_by_category:
                photos_by_category[category] = []
            photos_by_category[category].append(photo)
        
        # 카테고리 순서대로 정렬된 딕셔너리 생성
        sorted_photos_by_category = {}
        for cat in categories:
            if cat.name in photos_by_category:
                sorted_photos_by_category[cat.name] = photos_by_category[cat.name]
        # 순서가 없는 카테고리도 추가 (미분류 등)
        for cat_name in photos_by_category:
            if cat_name not in sorted_photos_by_category:
                sorted_photos_by_category[cat_name] = photos_by_category[cat_name]
        
        return render_template('admin/package_photos.html',
                             package_photos=package_photos,
                             photos_by_category=sorted_photos_by_category,
                             categories=categories,
                             service_options=service_options,
                             current_service_option_id=service_option_id)
    except Exception as e:
        print(f"Error listing package photos: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('패키지 화보 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/package_photos.html',
                             package_photos=[],
                             photos_by_category={},
                             categories=[],
                             service_options=[],
                             current_service_option_id=11)


@admin.route('/package-photos/category-order/<int:category_id>', methods=['POST'])
@login_required
def update_package_photo_category_order(category_id):
    """패키지 화보 카테고리 순서 업데이트"""
    try:
        category = PackagePhotoCategory.get_or_404(category_id)
        new_order = request.form.get('display_order', 0, type=int)
        
        if new_order < 0 or new_order > 999:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '표출 순서는 0~999 사이의 값이어야 합니다.'}), 400
            flash('표출 순서는 0~999 사이의 값이어야 합니다.', 'error')
            return redirect(url_for('admin.list_package_photos', service_option_id=category.service_option_id))
        
        category.display_order = new_order
        category.updated_at = datetime.utcnow()
        category.save()
        
        # 서비스 옵션 캐시 클리어 (프론트엔드 반영을 위해)
        try:
            from routes.main import clear_service_option_cache
            clear_service_option_cache(category.service_option_id)
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f'분류 "{category.name}"의 표출 순서가 {new_order}(으)로 업데이트되었습니다.',
                'display_order': new_order
            })
        
        flash(f'분류 "{category.name}"의 표출 순서가 {new_order}(으)로 업데이트되었습니다.')
        return redirect(url_for('admin.list_package_photos', service_option_id=category.service_option_id))
        
    except Exception as e:
        print(f"Error updating category order: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash('카테고리 순서 업데이트 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.list_package_photos'))


@admin.route('/package-photos/add', methods=['GET', 'POST'])
@login_required
def add_package_photo():
    """패키지 화보 추가"""
    if request.method == 'POST':
        try:
            service_option_id = request.form.get('service_option_id', 11, type=int)
            category = request.form.get('category', '').strip()
            concept = request.form.get('concept', '').strip()
            display_order = request.form.get('display_order', 0, type=int)
            
            if not category or not concept:
                flash('분류와 컨셉명을 입력해주세요.', 'error')
                return redirect(request.url)
            
            if 'images[]' not in request.files:
                flash('이미지를 선택해주세요.', 'error')
                return redirect(request.url)
            
            files = request.files.getlist('images[]')
            if len(files) == 0 or (len(files) == 1 and files[0].filename == ''):
                flash('이미지를 선택해주세요.', 'error')
                return redirect(request.url)
            
            if len(files) > 20:
                flash('최대 20개의 이미지만 업로드할 수 있습니다.', 'error')
                return redirect(request.url)
            
            # 이미지를 먼저 업로드하고 성공한 경우에만 패키지 화보 생성
            image_ids = []
            try:
                for file in files:
                    if file and allowed_file(file.filename):
                        image_id = save_package_photo_to_gridfs(file, None)  # 임시로 None 전달
                        image_ids.append(image_id)
                
                if len(image_ids) == 0:
                    flash('이미지 업로드에 실패했습니다. 이미지 파일을 확인해주세요.', 'error')
                    return redirect(request.url)
                    
            except Exception as upload_error:
                print(f"이미지 업로드 오류: {str(upload_error)}")
                import traceback
                traceback.print_exc()
                # 업로드 실패 시 이미 업로드된 이미지 정리
                for img_id in image_ids:
                    try:
                        delete_image_from_gridfs(img_id)
                    except:
                        pass
                flash('이미지 업로드 중 오류가 발생했습니다. 다시 시도해주세요.', 'error')
                return redirect(request.url)
            
            # 이미지 업로드 성공 후 패키지 화보 생성
            package_photo = PackagePhoto(
                service_option_id=service_option_id,
                category=category,
                concept=concept,
                images=image_ids,
                display_order=display_order,
                is_active=True
            )
            package_photo.save()
            
            # 서비스 옵션 캐시 클리어 (프론트엔드 반영을 위해)
            try:
                from routes.main import clear_service_option_cache
                clear_service_option_cache(service_option_id)
            except Exception as cache_error:
                print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
            
            flash(f'패키지 화보 "{concept}"이(가) 추가되었습니다. ({len(image_ids)}개 이미지)')
            return redirect(url_for('admin.list_package_photos', service_option_id=service_option_id))
            
        except Exception as e:
            print(f"Error adding package photo: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('패키지 화보 추가 중 오류가 발생했습니다.', 'error')
            return redirect(request.url)
    
    # GET 요청
    service_options = ServiceOption.query_all()
    service_option_id = request.args.get('service_option_id', 11, type=int)
    
    # 기존 카테고리 목록 가져오기
    existing_categories = PackagePhoto.get_categories(service_option_id)
    
    return render_template('admin/add_package_photo.html',
                         service_options=service_options,
                         current_service_option_id=service_option_id,
                         existing_categories=existing_categories)


@admin.route('/package-photos/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_package_photo(id):
    """패키지 화보 수정"""
    try:
        package_photo = PackagePhoto.get_or_404(id)
        
        if request.method == 'POST':
            package_photo.category = request.form.get('category', '').strip()
            package_photo.concept = request.form.get('concept', '').strip()
            package_photo.display_order = request.form.get('display_order', 0, type=int)
            package_photo.is_active = request.form.get('is_active') == 'on'
            
            # 새 이미지 추가
            if 'images[]' in request.files:
                files = request.files.getlist('images[]')
                new_image_ids = []
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        image_id = save_package_photo_to_gridfs(file, package_photo.id)
                        new_image_ids.append(image_id)
                
                if new_image_ids:
                    package_photo.images = package_photo.images + new_image_ids
            
            package_photo.updated_at = datetime.utcnow()
            package_photo.save()
            
            # 서비스 옵션 캐시 클리어 (프론트엔드 반영을 위해)
            try:
                from routes.main import clear_service_option_cache
                clear_service_option_cache(package_photo.service_option_id)
            except Exception as cache_error:
                print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
            
            flash(f'패키지 화보 "{package_photo.concept}"이(가) 수정되었습니다.')
            return redirect(url_for('admin.list_package_photos', service_option_id=package_photo.service_option_id))
        
        # GET 요청
        service_options = ServiceOption.query_all()
        existing_categories = PackagePhoto.get_categories(package_photo.service_option_id)
        
        return render_template('admin/edit_package_photo.html',
                             package_photo=package_photo,
                             service_options=service_options,
                             existing_categories=existing_categories)
                             
    except Exception as e:
        print(f"Error editing package photo: {str(e)}")
        flash('패키지 화보 수정 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.list_package_photos'))


@admin.route('/package-photos/<int:id>/delete', methods=['POST'])
@login_required
def delete_package_photo(id):
    """패키지 화보 삭제"""
    try:
        package_photo = PackagePhoto.get_or_404(id)
        service_option_id = package_photo.service_option_id
        concept = package_photo.concept
        
        # 관련 이미지 삭제
        for image_id in package_photo.images:
            try:
                delete_image_from_gridfs(image_id)
            except Exception as e:
                print(f"이미지 삭제 오류 (무시): {image_id} - {str(e)}")
        
        package_photo.delete()
        
        # 서비스 옵션 캐시 클리어 (프론트엔드 반영을 위해)
        try:
            from routes.main import clear_service_option_cache
            clear_service_option_cache(service_option_id)
        except Exception as cache_error:
            print(f"⚠️ 캐시 클리어 실패 (무시 가능): {str(cache_error)}")
        
        flash(f'패키지 화보 "{concept}"이(가) 삭제되었습니다.')
        return redirect(url_for('admin.list_package_photos', service_option_id=service_option_id))
        
    except Exception as e:
        print(f"Error deleting package photo: {str(e)}")
        flash('패키지 화보 삭제 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.list_package_photos'))


@admin.route('/package-photos/<int:id>/delete-image/<image_id>', methods=['POST'])
@login_required
def delete_package_photo_image(id, image_id):
    """패키지 화보에서 개별 이미지 삭제"""
    try:
        package_photo = PackagePhoto.get_or_404(id)
        
        if image_id in package_photo.images:
            # GridFS에서 이미지 삭제
            delete_image_from_gridfs(image_id)
            
            # 이미지 목록에서 제거
            package_photo.images = [img for img in package_photo.images if img != image_id]
            package_photo.updated_at = datetime.utcnow()
            package_photo.save()
            
            flash('이미지가 삭제되었습니다.')
        else:
            flash('이미지를 찾을 수 없습니다.', 'error')
            
        return redirect(url_for('admin.edit_package_photo', id=id))
        
    except Exception as e:
        print(f"Error deleting package photo image: {str(e)}")
        flash('이미지 삭제 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.edit_package_photo', id=id))


# ========== 공지사항 관리 ==========

@admin.route('/notices')
@login_required
def list_notices():
    """공지사항 목록"""
    try:
        notices = Notice.query_all_ordered()
        active_count = len([n for n in notices if n.is_active])
        return render_template('admin/notices.html', notices=notices, active_count=active_count)
    except Exception as e:
        print(f"Error listing notices: {str(e)}")
        flash('공지사항 목록을 불러오는 중 오류가 발생했습니다.', 'error')
        return render_template('admin/notices.html', notices=[], active_count=0)


@admin.route('/notices/add', methods=['GET', 'POST'])
@login_required
def add_notice():
    """공지사항 추가"""
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            display_order = request.form.get('display_order', 0, type=int)
            is_active = request.form.get('is_active') == 'on'
            
            if not title:
                flash('제목을 입력해주세요.', 'error')
                return render_template('admin/add_notice.html')
            
            if is_active:
                active_count = len(Notice.query_active(limit=10))
                if active_count >= 3:
                    flash('활성화된 공지사항은 최대 3개까지만 가능합니다. 다른 공지사항을 비활성화한 후 시도해주세요.', 'warning')
                    return render_template('admin/add_notice.html')
            
            notice = Notice(
                title=title,
                content=content,
                display_order=display_order,
                is_active=is_active
            )
            notice.save()
            
            trigger_translation('notice', notice)
            
            from routes.main import clear_index_page_cache
            clear_index_page_cache()
            
            flash('공지사항이 추가되었습니다.')
            return redirect(url_for('admin.list_notices'))
        except Exception as e:
            print(f"Error adding notice: {str(e)}")
            flash('공지사항 추가 중 오류가 발생했습니다.', 'error')
    
    return render_template('admin/add_notice.html')


@admin.route('/notices/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_notice(id):
    """공지사항 수정"""
    try:
        notice = Notice.get_or_404(id)
        
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            display_order = request.form.get('display_order', 0, type=int)
            is_active = request.form.get('is_active') == 'on'
            
            if not title:
                flash('제목을 입력해주세요.', 'error')
                return render_template('admin/edit_notice.html', notice=notice)
            
            if is_active and not notice.is_active:
                active_count = len(Notice.query_active(limit=10))
                if active_count >= 3:
                    flash('활성화된 공지사항은 최대 3개까지만 가능합니다.', 'warning')
                    return render_template('admin/edit_notice.html', notice=notice)
            
            notice.title = title
            notice.content = content
            notice.display_order = display_order
            notice.is_active = is_active
            notice.updated_at = datetime.utcnow()
            notice.save()
            
            trigger_translation('notice', notice)
            
            from routes.main import clear_index_page_cache
            clear_index_page_cache()
            
            flash('공지사항이 수정되었습니다.')
            return redirect(url_for('admin.list_notices'))
        
        return render_template('admin/edit_notice.html', notice=notice)
    except Exception as e:
        print(f"Error editing notice: {str(e)}")
        flash('공지사항 수정 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('admin.list_notices'))


@admin.route('/notices/<int:id>/toggle-active', methods=['POST'])
@login_required
def toggle_notice_active(id):
    """공지사항 활성화/비활성화 토글"""
    try:
        notice = Notice.get_by_id(id)
        if not notice:
            flash('공지사항을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_notices'))
        
        if not notice.is_active:
            active_count = len(Notice.query_active(limit=10))
            if active_count >= 3:
                flash('활성화된 공지사항은 최대 3개까지만 가능합니다. 다른 공지사항을 비활성화한 후 시도해주세요.', 'warning')
                return redirect(url_for('admin.list_notices'))
        
        notice.is_active = not notice.is_active
        notice.updated_at = datetime.utcnow()
        notice.save()
        
        from routes.main import clear_index_page_cache
        clear_index_page_cache()
        
        status = '활성화' if notice.is_active else '비활성화'
        flash(f'공지사항 "{notice.title}"이(가) {status}되었습니다.')
    except Exception as e:
        print(f"Error toggling notice: {str(e)}")
        flash('공지사항 상태 변경 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notices'))


@admin.route('/notices/<int:id>/delete', methods=['POST'])
@login_required
def delete_notice(id):
    """공지사항 삭제"""
    try:
        notice = Notice.get_by_id(id)
        if not notice:
            flash('공지사항을 찾을 수 없습니다.', 'error')
            return redirect(url_for('admin.list_notices'))
        
        title = notice.title
        notice.delete()
        
        from routes.main import clear_index_page_cache
        clear_index_page_cache()
        
        flash(f'공지사항 "{title}"이(가) 삭제되었습니다.')
    except Exception as e:
        print(f"Error deleting notice: {str(e)}")
        flash('공지사항 삭제 중 오류가 발생했습니다.', 'error')
    
    return redirect(url_for('admin.list_notices'))
