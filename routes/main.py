from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import Service, Gallery, Booking
from extensions import db
import json

# Create the Blueprint object
main = Blueprint('main', __name__)

@main.route('/')
def index():
    services = Service.query.all()
    images = Gallery.query.order_by(Gallery.id.desc()).limit(6).all()
    return render_template('index.html', services=services, images=images)

@main.route('/services')
def services():
    services = Service.query.all()
    return render_template('services.html', services=services)

@main.route('/service/<int:service_type>')
def service_detail(service_type):
    service = Service.query.get_or_404(service_type)
    # JSON 문자열을 파이썬 객체로 변환
    details = json.loads(service.details) if service.details else []
    packages = json.loads(service.packages) if service.packages else []
    return render_template('service_detail.html', 
                         service=service, 
                         details=details,
                         packages=packages)

@main.route('/gallery')
def gallery():
    images = Gallery.query.all()
    return render_template('gallery.html', images=images)

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # 예약/문의 폼 처리 로직
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        booking = Booking(name=name, email=email, message=message)
        db.session.add(booking)
        db.session.commit()
        
        flash('문의가 성공적으로 전송되었습니다.')
        return redirect(url_for('main.contact'))
        
    # services 변수를 템플릿에 전달
    services = Service.query.all()
    return render_template('booking.html', services=services) 