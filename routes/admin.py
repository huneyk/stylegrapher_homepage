from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, login_user, logout_user
from extensions import db, login_manager
from models import Service, Gallery, User, ServiceOption
from werkzeug.utils import secure_filename
import os

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
            return redirect(url_for('admin.dashboard'))
        flash('Invalid username or password')
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
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            
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

@admin.route('/services/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_service(id):
    service = Service.query.get_or_404(id)
    if request.method == 'POST':
        service.name = request.form['name']
        service.description = request.form['description']
        service.price = request.form['price']
        service.category = request.form['category']
        db.session.commit()
        flash('서비스가 수정되었습니다.')
        return redirect(url_for('admin.list_services'))
    return render_template('admin/edit_service.html', service=service)

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