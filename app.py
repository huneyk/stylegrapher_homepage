import os
import json
from flask import Flask, request, abort, send_from_directory
from routes.main import main
from routes.admin import admin
from extensions import db, login_manager, migrate, mail
from models import User
from config import Config
from pymongo import MongoClient
from dotenv import load_dotenv
from utils.security import add_security_headers, is_suspicious_request, get_client_ip, log_security_event

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
    mail.init_app(app)
    
    login_manager.login_view = 'admin.login'
    
    # 🛡️ 강화된 데이터 보호 시스템 - 배포 시 덮어쓰기 완전 방지
    def init_comprehensive_data_protection():
        """배포 시 기존 데이터 보호 초기화 및 덮어쓰기 방지"""
        try:
            from models import ServiceOption, GalleryGroup
            from sqlalchemy import text
            
            print("🛡️ 종합 데이터 보호 시스템 초기화 중...")
            
            # 서비스 옵션 데이터 보호 확인
            service_result = db.session.execute(
                text("""SELECT COUNT(*) FROM service_option 
                        WHERE booking_method IS NOT NULL 
                           OR payment_info IS NOT NULL 
                           OR guide_info IS NOT NULL 
                           OR refund_policy_text IS NOT NULL
                           OR refund_policy_table IS NOT NULL
                           OR overtime_charge_table IS NOT NULL""")
            ).scalar()
            
            # 갤러리 순서 데이터 보호 확인
            gallery_result = db.session.execute(
                text("SELECT COUNT(*) FROM gallery_group WHERE display_order IS NOT NULL")
            ).scalar()
            
            if service_result > 0:
                print(f"🛡️ {service_result}개의 기존 서비스 옵션 데이터 발견 - 보호 모드 활성화")
                app.config['DATA_PROTECTION_ACTIVE'] = True
                app.config['SERVICE_DATA_PROTECTED'] = True
            else:
                app.config['SERVICE_DATA_PROTECTED'] = False
            
            if gallery_result > 0:
                print(f"🛡️ {gallery_result}개의 기존 갤러리 순서 데이터 발견 - 순서 보호 활성화")
                app.config['GALLERY_ORDER_PROTECTED'] = True
            else:
                app.config['GALLERY_ORDER_PROTECTED'] = False
            
            # 전체 보호 모드 설정
            app.config['DATA_PROTECTION_ACTIVE'] = True  # 항상 보호 모드로 설정
            
            print("✅ 종합 데이터 보호 시스템 활성화 완료")
            print("🛡️ 모든 기존 데이터가 덮어쓰기로부터 보호됩니다")
                
        except Exception as e:
            print(f"⚠️ 데이터 보호 시스템 초기화 오류: {str(e)}")
            # 오류 발생 시에도 최대 보호 모드 활성화
            app.config['DATA_PROTECTION_ACTIVE'] = True
            app.config['SERVICE_DATA_PROTECTED'] = True
            app.config['GALLERY_ORDER_PROTECTED'] = True
            print("🛡️ 안전을 위해 최대 보호 모드로 설정됨")
    
    # 앱 컨텍스트에서 데이터 보호 시스템 초기화
    with app.app_context():
        init_comprehensive_data_protection()
    
    # 보안 미들웨어 - 모든 요청에 대해 실행
    @app.before_request
    def security_middleware():
        # robots.txt 요청은 보안 검사 제외
        if request.path == '/robots.txt':
            return
            
        # 의심스러운 요청 패턴 검사
        is_suspicious, reason = is_suspicious_request()
        if is_suspicious:
            log_security_event("BLOCKED_REQUEST", reason)
            abort(404)  # 404로 위장하여 정보 노출 방지
    
    # 모든 응답에 보안 헤더 추가
    @app.after_request
    def after_request(response):
        return add_security_headers(response)
    
    # robots.txt 제공
    @app.route('/robots.txt')
    def robots_txt():
        return send_from_directory(app.static_folder, 'robots.txt')
    
    # 개선된 404 오류 핸들러
    @app.errorhandler(404)
    def page_not_found(error):
        # 보안 이벤트 로깅
        log_security_event("404_ERROR", f"Path: {request.path}")
        return "Not Found", 404
    
    # 429 오류 핸들러 (Rate Limiting)
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        log_security_event("RATE_LIMIT", f"IP: {get_client_ip()}")
        return "Too Many Requests", 429
    
    # Jinja2 필터 추가
    @app.template_filter('from_json')
    def from_json_filter(value):
        """JSON 문자열을 Python 객체로 변환하는 필터"""
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    
    # 전역 컨텍스트 추가 - 사이드 메뉴용 카테고리별 서비스
    @app.context_processor
    def inject_menu_data():
        from models import Service
        
        categories_data = {
            'ai_analysis': {
                'title': 'STG AI 분석',
                'icon': 'bi-cpu',
                'services': []
            },
            'consulting': {
                'title': '스타일링 컨설팅',
                'icon': 'bi-person-check',
                'services': []
            },
            'oneday': {
                'title': '원데이 스타일링',
                'icon': 'bi-star',
                'services': []
            },
            'photo': {
                'title': '화보 & 프로필',
                'icon': 'bi-camera',
                'services': []
            }
        }
        
        try:
            services = Service.query.all()
            for service in services:
                if service.category and service.category in categories_data:
                    categories_data[service.category]['services'].append(service)
        except Exception as e:
            print(f"Error loading menu data: {str(e)}")
        
        return dict(menu_categories=categories_data)
    
    # 전역 컨텍스트 추가 - 사이트 색상 설정
    @app.context_processor
    def inject_site_colors():
        from models import SiteSettings
        
        try:
            settings = SiteSettings.get_current_settings()
            if settings:
                return dict(
                    site_colors={
                        'main_rgb': settings.get_main_color_rgb(),
                        'sub_rgb': settings.get_sub_color_rgb(),
                        'background_rgb': settings.get_background_color_rgb(),
                        'main_hex': settings.get_main_color_hex(),
                        'sub_hex': settings.get_sub_color_hex(),
                        'background_hex': settings.get_background_color_hex()
                    }
                )
        except Exception as e:
            print(f"Error loading site colors: {str(e)}")
        
        # 설정이 없는 경우 빈 색상 정보 반환
        return dict(
            site_colors={
                'main_rgb': None,
                'sub_rgb': None,
                'background_rgb': None,
                'main_hex': None,
                'sub_hex': None,
                'background_hex': None
            }
        )
    
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

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)