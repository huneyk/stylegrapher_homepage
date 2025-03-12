import os
from flask import Flask
from routes.main import main
from routes.admin import admin
from extensions import db, login_manager, migrate
from models import User
from config import Config

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