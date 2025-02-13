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
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # 전체 갤러리 수 먼저 확인
    total_count = GalleryGroup.query.count()
    
    # 페이지네이션 적용
    pagination = GalleryGroup.query.order_by(desc(GalleryGroup.created_at)).paginate(
        page=page, per_page=per_page, error_out=False)
    gallery_groups = pagination.items
    
    # 현재까지 보여진 갤러리 수
    shown_galleries = (page - 1) * per_page + len(gallery_groups)
    # 남은 갤러리 수 계산
    remaining_galleries = total_count - shown_galleries
    
    # 남은 갤러리가 있고, 현재 페이지의 갤러리가 per_page와 같을 때만 더보기 버튼 표시
    has_more = remaining_galleries > 0 and len(gallery_groups) == per_page
    
    if request.headers.get('HX-Request'):
        # HTMX 요청인 경우 부분적 HTML만 반환
        return render_template('_gallery_items.html', 
                             gallery_groups=gallery_groups,
                             has_more=has_more,
                             next_page=page + 1)
    
    return render_template('gallery.html', 
                         gallery_groups=gallery_groups,
                         has_more=has_more,
                         next_page=page + 1,
                         total_galleries=total_count)

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