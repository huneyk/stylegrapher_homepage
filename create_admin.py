from app import app, db
from models import User
from werkzeug.security import generate_password_hash
import sys

def create_admin(username, password):
    with app.app_context():
        try:
            # 이미 존재하는 사용자인지 확인
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                print(f"사용자 '{username}'이(가) 이미 존재합니다.")
                return
            
            # 새 관리자 계정 생성 (email 필드 제외)
            admin = User(
                username=username,
                password_hash=generate_password_hash(password, method='pbkdf2:sha256'),
                is_admin=True
            )
            
            # 데이터베이스에 저장
            db.session.add(admin)
            db.session.commit()
            print(f"관리자 계정이 생성되었습니다: {admin.username}")
        except Exception as e:
            print(f"Error: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python create_admin.py <username> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    create_admin(username, password) 