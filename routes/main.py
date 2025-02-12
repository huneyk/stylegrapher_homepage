from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import Service, Gallery, Booking, CarouselItem, GalleryGroup, CollageText
from extensions import db
import json
from sqlalchemy import desc

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
    gallery_groups = GalleryGroup.query.order_by(GalleryGroup.created_at.desc()).all()
    return render_template('gallery.html', gallery_groups=gallery_groups)

@main.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('contact')
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
        
        flash('예약 문의가 성공적으로 전송되었습니다.')
        return redirect(url_for('main.contact'))
        
    services = Service.query.all()
    return render_template('booking.html', services=services) 