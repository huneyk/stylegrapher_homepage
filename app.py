import os
from flask import Flask
from routes.main import main
from routes.admin import admin
from extensions import db, login_manager
from models import User
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 업로드 폴더 설정
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'
    
    # Import blueprints from routes package
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    return app