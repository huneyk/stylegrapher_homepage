import os
from flask import Flask
from routes.main import main
from routes.admin import admin
from extensions import db, login_manager, migrate
from models import User
from config import Config
from pymongo import MongoClient
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# MongoDB 연결 설정
mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
try:
    mongo_client = MongoClient(
        mongo_uri, 
        serverSelectionTimeoutMS=30000,  # 30초로 증가
        connectTimeoutMS=20000,
        socketTimeoutMS=20000,
        retryWrites=True,
        retryReads=True,
        w='majority',  # 다수의 노드에 쓰기 확인
        readPreference='primaryPreferred'  # 프라이머리 선호, 없으면 세컨더리로 전환
    )
    # 테스트 연결
    mongo_client.server_info()
    print("app.py: MongoDB 연결 성공!")
    mongo_db = mongo_client['STG-DB'] if 'mongodb.net' in mongo_uri else mongo_client['stylegrapher_db']
    images_collection = mongo_db['gallery']
    print(f"app.py: MongoDB 데이터베이스 '{mongo_db.name}' 및 컬렉션 '{images_collection.name}' 사용 준비 완료")
except Exception as e:
    print(f"app.py: MongoDB 연결 오류: {str(e)}")
    mongo_client = None
    mongo_db = None
    images_collection = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 업로드 폴더 설정
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
    
    # 확장 기능 초기화
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    login_manager.login_view = 'admin.login'
    
    # Import blueprints from routes package
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    
    @login_manager.user_loader
    def load_user(user_id):
        from sqlalchemy import text
        try:
            # 직접 SQL 쿼리를 사용하여 사용자 조회
            result = db.session.execute(text("SELECT id, uq_user_username, password_hash FROM user WHERE id = :id"), {"id": user_id})
            user_data = result.fetchone()
            
            if user_data:
                # 사용자 객체 생성
                user = User()
                user.id = user_data[0]
                user.username = user_data[1]
                user.password_hash = user_data[2]
                user.is_admin = True  # 항상 관리자로 설정
                return user
            return None
        except Exception as e:
            print(f"Error loading user: {str(e)}")
            return None
    
    return app