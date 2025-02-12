from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import Service, Gallery, Booking
from extensions import db

# Create the Blueprint object
main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/services')
def services():
    services = Service.query.all()
    return render_template('services.html', services=services)

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