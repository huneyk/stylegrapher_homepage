from datetime import datetime
from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, name='uq_user_username')
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    details = db.Column(db.Text)  # JSON 형식으로 저장
    packages = db.Column(db.Text)  # JSON 형식으로 저장

class ServiceOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)  # 기본 설명 - index page 카드에 표시
    detailed_description = db.Column(db.Text)  # 상세 설명 - 서비스 상세 페이지에 표시
    details = db.Column(db.Text)  # JSON 형식으로 저장 (상세 내용 리스트)
    packages = db.Column(db.Text)  # JSON 형식으로 저장 (패키지 및 가격 정보)
    
    # Service 모델과의 관계 설정
    service = db.relationship('Service', backref=db.backref('options', lazy=True, cascade="all, delete-orphan"))

class GalleryGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    display_order = db.Column(db.Integer, default=0)  # 표출 순서
    is_pinned = db.Column(db.Boolean, default=False)  # 상단 고정
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    images = db.relationship('Gallery', backref='group', cascade='all, delete-orphan')

class Gallery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    order = db.Column(db.Integer, default=0)
    group_id = db.Column(db.Integer, db.ForeignKey('gallery_group.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id', name='fk_booking_service'))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='대기')  # 대기, 확정, 취소
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    service = db.relationship('Service', backref='bookings')
    
    def get_datetimes(self):
        # 메시지에서 희망 예약일시 부분만 추출
        lines = self.message.split('\n')
        datetimes = []
        for line in lines:
            if '순위:' in line:
                datetimes.append(line.strip())
        return datetimes
    
    def get_message_content(self):
        # 메시지에서 희망 예약일시를 제외한 내용만 반환
        parts = self.message.split('\n\n희망 예약일시:')
        return parts[0] if parts else ''



class CollageText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<CollageText {self.text}>'

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='대기')  # 대기, 처리중, 완료
    
    service = db.relationship('Service', backref='inquiries')