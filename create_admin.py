from app import create_app, db
from models import User

def create_admin_user():
    app = create_app()
    with app.app_context():
        # 기존 admin 사용자가 있는지 확인
        admin = User.query.filter_by(username='admin').first()
        if admin:
            print('Admin user already exists!')
            return
        
        # 새 admin 사용자 생성
        admin = User(
            username='admin',
            email='admin@example.com'
        )
        admin.set_password('admin123')  # 초기 비밀번호를 'admin123'으로 설정
        
        db.session.add(admin)
        db.session.commit()
        print('Admin user created successfully!')

if __name__ == '__main__':
    create_admin_user() 