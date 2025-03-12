from app import create_app
from extensions import db
from models import User
from werkzeug.security import generate_password_hash
import sys

def create_admin(username, email, password):
    app = create_app()
    with app.app_context():
        # 이미 존재하는 사용자인지 확인
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"사용자 '{username}'이(가) 이미 존재합니다.")
            return
        
        # 새 관리자 계정 생성 (pbkdf2:sha256 알고리즘 사용)
        admin = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
            is_admin=True
        )
        
        # 데이터베이스에 저장
        db.session.add(admin)
        db.session.commit()
        print(f"관리자 계정이 생성되었습니다: {admin.username}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("사용법: python create_admin.py <username> <email> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]
    
    create_admin(username, email, password) 