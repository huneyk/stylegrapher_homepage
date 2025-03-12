from app import create_app
from models import db
from werkzeug.security import generate_password_hash
from sqlalchemy import text
import sys

def create_admin(username="admin", password="ysg123"):
    app = create_app()  # 애플리케이션 인스턴스 생성
    with app.app_context():
        try:
            # 데이터베이스 테이블 구조 확인
            result = db.session.execute(text("PRAGMA table_info(user)"))
            columns = result.fetchall()
            print("User table columns:")
            for column in columns:
                print(column)
            
            # 이미 존재하는 사용자인지 확인 (직접 SQL 사용)
            result = db.session.execute(text("SELECT id FROM user WHERE uq_user_username = :username"), {"username": username})
            existing_user = result.fetchone()
            
            if existing_user:
                print(f"사용자 '{username}'이(가) 이미 존재합니다.")
                # 기존 사용자의 비밀번호 업데이트
                update_sql = text("""
                UPDATE user SET password_hash = :password_hash
                WHERE uq_user_username = :username
                """)
                update_params = {
                    "username": username,
                    "password_hash": generate_password_hash(password, method='pbkdf2:sha256')
                }
                db.session.execute(update_sql, update_params)
                db.session.commit()
                print(f"사용자 '{username}'의 비밀번호가 업데이트되었습니다.")
                return
            
            # 테이블에 email 열이 있는지 확인
            has_email_column = any(column[1] == 'email' for column in columns)
            
            if has_email_column:
                # email 열이 있는 경우
                sql = text("""
                INSERT INTO user (uq_user_username, email, password_hash, is_admin) 
                VALUES (:username, :email, :password_hash, :is_admin)
                """)
                params = {
                    "username": username,
                    "email": f"{username}@example.com",  # 기본 이메일 제공
                    "password_hash": generate_password_hash(password, method='pbkdf2:sha256'),
                    "is_admin": True
                }
            else:
                # email 열이 없는 경우
                sql = text("""
                INSERT INTO user (uq_user_username, password_hash, is_admin) 
                VALUES (:username, :password_hash, :is_admin)
                """)
                params = {
                    "username": username,
                    "password_hash": generate_password_hash(password, method='pbkdf2:sha256'),
                    "is_admin": True
                }
            
            # 새 관리자 계정 생성 (직접 SQL 사용)
            db.session.execute(sql, params)
            db.session.commit()
            
            print(f"관리자 계정이 생성되었습니다: {username}")
        except Exception as e:
            print(f"Error: {str(e)}")
            db.session.rollback()

if __name__ == "__main__":
    # 명령줄 인수가 제공되면 사용하고, 그렇지 않으면 기본값 사용
    if len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        username = "admin"
        password = "ysg123"
        print(f"기본 사용자 이름 '{username}'과 비밀번호 '{password}'를 사용합니다.")
    
    create_admin(username, password) 