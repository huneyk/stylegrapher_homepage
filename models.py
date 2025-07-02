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
    
    # 예약 조건 관련 필드들
    booking_method = db.Column(db.Text)  # 예약 방법
    payment_info = db.Column(db.Text)  # 제작비 결제 방식  
    guide_info = db.Column(db.Text)  # 안내 사항
    refund_policy = db.Column(db.Text)  # 예약 변경 및 환불 규정 (구 버전 호환용)
    refund_policy_text = db.Column(db.Text)  # 환불 규정 기본 안내
    refund_policy_table = db.Column(db.Text)  # 환불 규정 테이블 데이터
    overtime_charge_table = db.Column(db.Text)  # 시간외 업차지 테이블 데이터
    
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

class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    main_color_r = db.Column(db.Integer, default=139)  # 기본값: rgba(139, 95, 191, 0.8)
    main_color_g = db.Column(db.Integer, default=95)
    main_color_b = db.Column(db.Integer, default=191)
    sub_color_r = db.Column(db.Integer, default=65)   # 기본값: rgba(65, 26, 75, 0.8)
    sub_color_g = db.Column(db.Integer, default=26)
    sub_color_b = db.Column(db.Integer, default=75)
    background_color_r = db.Column(db.Integer, default=255)  # 기본값: white
    background_color_g = db.Column(db.Integer, default=255)
    background_color_b = db.Column(db.Integer, default=255)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SiteSettings {self.id}>'
    
    @classmethod
    def get_current_settings(cls):
        """현재 사이트 설정을 가져오거나 기본값으로 생성"""
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
    
    def get_main_color_rgb(self):
        """main color RGB 문자열 반환"""
        return f"{self.main_color_r}, {self.main_color_g}, {self.main_color_b}"
    
    def get_sub_color_rgb(self):
        """sub color RGB 문자열 반환"""
        return f"{self.sub_color_r}, {self.sub_color_g}, {self.sub_color_b}"
    
    def get_background_color_rgb(self):
        """background color RGB 문자열 반환"""
        return f"{self.background_color_r}, {self.background_color_g}, {self.background_color_b}"
    
    def get_main_color_hex(self):
        """main color HEX 문자열 반환"""
        return f"#{self.main_color_r:02x}{self.main_color_g:02x}{self.main_color_b:02x}"
    
    def get_sub_color_hex(self):
        """sub color HEX 문자열 반환"""
        return f"#{self.sub_color_r:02x}{self.sub_color_g:02x}{self.sub_color_b:02x}"
    
    def get_background_color_hex(self):
        """background color HEX 문자열 반환"""
        return f"#{self.background_color_r:02x}{self.background_color_g:02x}{self.background_color_b:02x}"

class TermsOfService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TermsOfService {self.id}>'
    
    @classmethod
    def get_current_content(cls):
        """현재 이용약관 내용을 가져오거나 기본값으로 생성"""
        terms = cls.query.first()
        if not terms:
            # 기본 이용약관 내용
            default_content = """<section class="mb-4">
    <h3 class="section-title">제1조 (목적)</h3>
    <p>이 약관은 스타일그래퍼(이하 "회사"라 함)가 제공하는 스타일링 서비스 및 관련 제반 서비스의 이용과 관련하여 회사와 회원과의 권리, 의무 및 책임사항, 기타 필요한 사항을 규정함을 목적으로 합니다.</p>
</section>

<section class="mb-4">
    <h3 class="section-title">제2조 (정의)</h3>
    <p>이 약관에서 사용하는 용어의 정의는 다음과 같습니다:</p>
    <ol>
        <li>"서비스"라 함은 회사가 제공하는 스타일링 컨설팅, AI 분석, 화보 촬영, 원데이 스타일링 등 모든 서비스를 의미합니다.</li>
        <li>"회원"이라 함은 회사의 서비스를 이용하는 고객을 의미합니다.</li>
        <li>"예약"이라 함은 회원이 특정 서비스를 신청하는 것을 의미합니다.</li>
    </ol>
</section>

<section class="mb-4">
    <h3 class="section-title">제3조 (약관의 효력 및 변경)</h3>
    <p>1. 본 약관은 회사의 홈페이지에 게시하거나 기타의 방법으로 회원에게 공지함으로써 효력이 발생합니다.</p>
    <p>2. 회사는 합리적인 사유가 발생할 경우에는 본 약관을 변경할 수 있으며, 약관이 변경된 경우에는 지체 없이 이를 공지하거나 통지합니다.</p>
</section>"""
            terms = cls(content=default_content)
            db.session.add(terms)
            db.session.commit()
        return terms

class PrivacyPolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PrivacyPolicy {self.id}>'
    
    @classmethod
    def get_current_content(cls):
        """현재 개인정보처리방침 내용을 가져오거나 기본값으로 생성"""
        policy = cls.query.first()
        if not policy:
            # 기본 개인정보처리방침 내용
            default_content = """<section class="mb-4">
    <h3 class="section-title">제1조 (개인정보의 처리목적)</h3>
    <p>스타일그래퍼('https://stylegrapher.com' 이하 '회사')는 다음의 목적을 위하여 개인정보를 처리하고 있으며, 다음의 목적 이외의 용도로는 이용하지 않습니다.</p>
    <ul>
        <li>서비스 제공에 관한 계약 이행 및 서비스 제공에 따른 요금정산</li>
        <li>회원 관리: 회원제 서비스 이용에 따른 본인확인, 개인 식별, 불량회원의 부정 이용 방지와 비인가 사용 방지</li>
        <li>마케팅 및 광고에의 활용: 이벤트 등 광고성 정보 전달, 접속 빈도 파악</li>
        <li>고객 서비스 이용에 관한 통지, CS업무</li>
    </ul>
</section>

<section class="mb-4">
    <h3 class="section-title">제2조 (개인정보의 처리 및 보유기간)</h3>
    <p>① 회사는 정보주체로부터 개인정보를 수집할 때 동의받은 개인정보 보유․이용기간 또는 법령에 따른 개인정보 보유․이용기간 내에서 개인정보를 처리․보유합니다.</p>
    <p>② 구체적인 개인정보 처리 및 보유 기간은 다음과 같습니다:</p>
    <ul>
        <li>서비스 이용 관련 정보: 서비스 이용계약 해지 후 5년</li>
        <li>결제 및 환불 관련 정보: 5년 (전자상거래 등에서의 소비자보호에 관한 법률)</li>
        <li>고객 상담 관련 정보: 3년</li>
        <li>마케팅 목적 개인정보: 동의철회 시까지</li>
    </ul>
</section>"""
            policy = cls(content=default_content)
            db.session.add(policy)
            db.session.commit()
        return policy