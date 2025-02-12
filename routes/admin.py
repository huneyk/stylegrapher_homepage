from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, login_user, logout_user
from extensions import db, login_manager
from models import Service, Gallery, User, ServiceOption, Booking, CarouselItem
from werkzeug.utils import secure_filename
import os
from PIL import Image
import json

admin = Blueprint('admin', __name__)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            flash('로그인되었습니다.')
            return redirect(url_for('admin.dashboard'))
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('admin/login.html')

@admin.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@admin.route('/dashboard')
@login_required
def dashboard():
    return render_template('admin/dashboard.html')

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

@admin.route('/gallery/upload', methods=['GET', 'POST'])
@login_required
def upload_image():
    if request.method == 'POST':
        if 'image' not in request.files:
            flash('이미지를 선택해주세요.')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('이미지를 선택해주세요.')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # 이미지 리사이즈
            resize_image(filepath)
            
            gallery = Gallery(
                image_path=filename,
                caption=request.form['caption'],
                category=request.form['category']
            )
            db.session.add(gallery)
            db.session.commit()
            
            flash('이미지가 업로드되었습니다.')
            return redirect(url_for('admin.dashboard'))
            
    return render_template('admin/upload_image.html')

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

@admin.route('/bookings')
@login_required
def list_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)

@admin.route('/booking/<int:id>/status/<status>')
@login_required
def update_booking_status(id, status):
    booking = Booking.query.get_or_404(id)
    if status in ['대기', '확정', '취소']:
        booking.status = status
        db.session.commit()
        flash('예약 상태가 업데이트되었습니다.')
    return redirect(url_for('admin.list_bookings'))

@admin.route('/booking/<int:id>/delete')
@login_required
def delete_booking(id):
    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    flash('예약이 삭제되었습니다.')
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
            filename = secure_filename(file.filename)
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            
            carousel_item = CarouselItem(
                title=request.form['title'],
                subtitle=request.form['subtitle'],
                image_path=filename,
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
                    old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], carousel_item.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # 새 이미지 저장
                filename = secure_filename(file.filename)
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                carousel_item.image_path = filename
        
        db.session.commit()
        flash('캐러셀 항목이 수정되었습니다.')
        return redirect(url_for('admin.list_carousel'))
        
    return render_template('admin/edit_carousel.html', carousel=carousel_item)

@admin.route('/carousel/delete/<int:id>')
@login_required
def delete_carousel(id):
    carousel_item = CarouselItem.query.get_or_404(id)
    
    # 이미지 파일 삭제
    if carousel_item.image_path:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], carousel_item.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(carousel_item)
    db.session.commit()
    flash('캐러셀 항목이 삭제되었습니다.')
    return redirect(url_for('admin.list_carousel'))