from app import create_app
from extensions import db
from models import User, Service, Gallery, Booking, ServiceOption

def init_db():
    app = create_app()
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create initial admin user if it doesn't exist
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin123')  # Change this password in production!
            db.session.add(admin)
        
        # Add some initial services and options if they don't exist
        if not Service.query.first():
            # 개인화보 서비스
            photo_service = Service(
                name='개인화보',
                description='특별한 순간을 아름답게 담아드립니다',
                price=150000,
                category='촬영'
            )
            db.session.add(photo_service)
            db.session.commit()  # Commit to get the service ID
            
            # 개인화보 옵션들
            photo_options = [
                ServiceOption(
                    service_id=photo_service.id,
                    name='기본 패키지',
                    description='1시간 촬영, 5컷 보정',
                    price=150000,
                    duration='1시간'
                ),
                ServiceOption(
                    service_id=photo_service.id,
                    name='스탠다드 패키지',
                    description='2시간 촬영, 10컷 보정',
                    price=250000,
                    duration='2시간'
                ),
                ServiceOption(
                    service_id=photo_service.id,
                    name='프리미엄 패키지',
                    description='3시간 촬영, 20컷 보정',
                    price=350000,
                    duration='3시간'
                )
            ]
            for option in photo_options:
                db.session.add(option)
            
            # 다른 서비스들 추가
            other_services = [
                Service(
                    name='메이크업 레슨',
                    description='나만의 메이크업 스킬을 배워보세요',
                    price=100000,
                    category='메이크업'
                ),
                Service(
                    name='퍼스널 컬러 진단',
                    description='나에게 어울리는 컬러를 찾아드립니다',
                    price=80000,
                    category='컨설팅'
                )
            ]
            for service in other_services:
                db.session.add(service)
        
        # Commit all changes
        db.session.commit()

if __name__ == '__main__':
    init_db() 