"""
Flask 애플리케이션 팩토리 - MongoDB 기반
"""
import os
import json
from flask import Flask, request, abort, send_from_directory, session, g, redirect, url_for, jsonify
from routes.main import main
from routes.admin import admin
from extensions import db, login_manager, migrate, mail, babel, compress, cache
from config import Config
from dotenv import load_dotenv
from utils.security import add_security_headers, is_suspicious_request, get_client_ip, log_security_event
from utils.translation_helper import register_template_helpers
from utils.mongo_models import get_mongo_db, init_collections, Service, SiteSettings
from utils.translation import export_mongodb_to_cache, TRANSLATIONS_CACHE_FILE

# 지원하는 언어 목록
SUPPORTED_LANGUAGES = {
    'ko': '한국어',
    'en': 'English',
    'ja': '日本語',
    'zh': '中文',
    'es': 'Español'
}

# .env 파일 로드
load_dotenv()

# MongoDB 연결은 create_app() 내에서 lazy하게 초기화됨 (fork-safe)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 업로드 폴더 설정
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
    
    # Babel 설정
    app.config['BABEL_DEFAULT_LOCALE'] = 'ko'
    app.config['BABEL_SUPPORTED_LOCALES'] = list(SUPPORTED_LANGUAGES.keys())
    app.config['LANGUAGES'] = SUPPORTED_LANGUAGES
    
    # 성능 최적화 - Gzip 압축 설정
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html', 'text/css', 'text/xml', 'text/javascript',
        'application/json', 'application/javascript', 'application/xml',
        'application/x-javascript', 'image/svg+xml'
    ]
    app.config['COMPRESS_LEVEL'] = 6
    app.config['COMPRESS_MIN_SIZE'] = 500
    compress.init_app(app)
    
    # 캐싱 설정 (SimpleCache - 메모리 기반)
    app.config['CACHE_TYPE'] = 'SimpleCache'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5분
    cache.init_app(app)
    
    # SQLAlchemy 초기화 (마이그레이션 스크립트용으로 유지)
    db.init_app(app)
    migrate.init_app(app, db)
    
    # 확장 기능 초기화
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Babel 초기화
    def get_locale():
        lang = request.args.get('lang')
        if lang and lang in SUPPORTED_LANGUAGES:
            session['lang'] = lang
            return lang
        
        if 'lang' in session and session['lang'] in SUPPORTED_LANGUAGES:
            return session['lang']
        
        best_match = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
        if best_match:
            return best_match
        
        return 'ko'
    
    babel.init_app(app, locale_selector=get_locale)
    
    login_manager.login_view = 'admin.login'
    
    # MongoDB 컬렉션 초기화
    def init_mongodb():
        """MongoDB 컬렉션 및 인덱스 초기화"""
        try:
            print("🔧 MongoDB 컬렉션 초기화 중...")
            init_collections()
            print("✅ MongoDB 컬렉션 초기화 완료")
        except Exception as e:
            print(f"⚠️ MongoDB 초기화 오류: {str(e)}")
    
    def init_translation_cache():
        """번역 JSON 캐시 초기화"""
        try:
            # 캐시 파일이 없거나 비어있으면 MongoDB에서 내보내기
            if not TRANSLATIONS_CACHE_FILE.exists() or TRANSLATIONS_CACHE_FILE.stat().st_size == 0:
                print("🔧 번역 캐시 파일 생성 중...")
                if export_mongodb_to_cache():
                    print("✅ 번역 캐시 파일 생성 완료")
                else:
                    print("⚠️ 번역 캐시 파일 생성 실패 (MongoDB fallback 사용)")
            else:
                print(f"✅ 번역 캐시 파일 존재: {TRANSLATIONS_CACHE_FILE}")
        except Exception as e:
            print(f"⚠️ 번역 캐시 초기화 오류: {str(e)} (MongoDB fallback 사용)")
    
    # 앱 시작 시 MongoDB 및 번역 캐시 초기화
    with app.app_context():
        init_mongodb()
        init_translation_cache()
    
    # 보안 미들웨어
    @app.before_request
    def security_middleware():
        if request.path == '/robots.txt':
            return
            
        is_suspicious, reason = is_suspicious_request()
        if is_suspicious:
            log_security_event("BLOCKED_REQUEST", reason)
            abort(404)
    
    # 보안 헤더 및 캐싱 헤더 추가
    @app.after_request
    def after_request(response):
        response = add_security_headers(response)
        
        # 정적 파일 캐싱 헤더 설정 (성능 최적화)
        if request.path.startswith('/static/'):
            # CSS, JS 파일 - 1주일 캐싱
            if request.path.endswith(('.css', '.js')):
                response.headers['Cache-Control'] = 'public, max-age=604800'
            # 이미지 파일 - 1개월 캐싱
            elif request.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.webp')):
                response.headers['Cache-Control'] = 'public, max-age=2592000'
            # 폰트 파일 - 1년 캐싱
            elif request.path.endswith(('.woff', '.woff2', '.ttf', '.eot')):
                response.headers['Cache-Control'] = 'public, max-age=31536000'
        
        return response
    
    # robots.txt 제공
    @app.route('/robots.txt')
    def robots_txt():
        return send_from_directory(app.static_folder, 'robots.txt')
    
    # sitemap.xml 생성 (SEO 최적화)
    @app.route('/sitemap.xml')
    def sitemap():
        from flask import make_response, url_for
        from datetime import datetime
        from utils.mongo_models import ServiceOption, GalleryGroup
        
        base_url = 'https://www.stylegrapher.com'
        
        # 정적 페이지 목록
        static_pages = [
            {'loc': '/', 'priority': '1.0', 'changefreq': 'daily'},
            {'loc': '/services', 'priority': '0.9', 'changefreq': 'weekly'},
            {'loc': '/gallery', 'priority': '0.8', 'changefreq': 'weekly'},
            {'loc': '/booking-choice', 'priority': '0.8', 'changefreq': 'monthly'},
            {'loc': '/customer-story', 'priority': '0.7', 'changefreq': 'weekly'},
            {'loc': '/commercial-portfolio', 'priority': '0.7', 'changefreq': 'monthly'},
            {'loc': '/about', 'priority': '0.6', 'changefreq': 'monthly'},
            {'loc': '/ask', 'priority': '0.7', 'changefreq': 'monthly'},
            {'loc': '/terms-of-service', 'priority': '0.3', 'changefreq': 'yearly'},
            {'loc': '/privacy-policy', 'priority': '0.3', 'changefreq': 'yearly'},
        ]
        
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 정적 페이지 추가
        for page in static_pages:
            xml_content += f'''  <url>
    <loc>{base_url}{page['loc']}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>
  </url>\n'''
        
        # 서비스 옵션 페이지 추가
        try:
            service_options = ServiceOption.query_all()
            for option in service_options:
                xml_content += f'''  <url>
    <loc>{base_url}/service_option/{option.id}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n'''
        except Exception as e:
            print(f"Sitemap - 서비스 옵션 조회 오류: {str(e)}")
        
        # 갤러리 상세 페이지 추가
        try:
            gallery_groups = GalleryGroup.query_all_ordered()
            for group in gallery_groups:
                xml_content += f'''  <url>
    <loc>{base_url}/gallery/detail/{group.id}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>\n'''
        except Exception as e:
            print(f"Sitemap - 갤러리 조회 오류: {str(e)}")
        
        xml_content += '</urlset>'
        
        response = make_response(xml_content)
        response.headers['Content-Type'] = 'application/xml'
        response.headers['Cache-Control'] = 'public, max-age=3600'  # 1시간 캐싱
        return response
    
    # 404 오류 핸들러
    @app.errorhandler(404)
    def page_not_found(error):
        log_security_event("404_ERROR", f"Path: {request.path}")
        return "Not Found", 404
    
    # 429 오류 핸들러
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        log_security_event("RATE_LIMIT", f"IP: {get_client_ip()}")
        return "Too Many Requests", 429
    
    # Jinja2 필터 추가
    @app.template_filter('from_json')
    def from_json_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    
    # 전역 컨텍스트 - 언어 설정
    @app.context_processor
    def inject_language_data():
        from flask_babel import get_locale
        current_locale = get_locale()
        return dict(
            current_lang=str(current_locale) if current_locale else 'ko',
            supported_languages=SUPPORTED_LANGUAGES
        )
    
    # 언어 변경 라우트
    @app.route('/set-language/<lang>')
    def set_language(lang):
        if lang in SUPPORTED_LANGUAGES:
            session['lang'] = lang
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           'application/json' in request.headers.get('Accept', '') or \
           request.headers.get('Sec-Fetch-Mode') == 'cors':
            return jsonify({'success': True, 'lang': lang})
        
        referrer = request.referrer
        if referrer:
            return redirect(referrer)
        return redirect(url_for('main.index'))
    
    # 전역 컨텍스트 - 사이드 메뉴용 카테고리별 서비스
    @app.context_processor
    def inject_menu_data():
        categories_data = {
            'ai_analysis': {
                'title': 'AI 분석',
                'icon': 'bi-cpu',
                'services': []
            },
            'consulting': {
                'title': '컨설팅 프로그램',
                'icon': 'bi-person-check',
                'services': []
            },
            'oneday': {
                'title': '원데이 스타일링',
                'icon': 'bi-star',
                'services': []
            },
            'photo': {
                'title': '프리미엄 화보 제작',
                'icon': 'bi-camera',
                'services': []
            }
        }
        
        try:
            services = Service.query_all()
            for service in services:
                if service.category and service.category in categories_data:
                    categories_data[service.category]['services'].append(service)
        except Exception as e:
            print(f"Error loading menu data: {str(e)}")
        
        return dict(menu_categories=categories_data)
    
    # 전역 컨텍스트 - 사이트 색상 및 모드 설정
    @app.context_processor
    def inject_site_colors():
        try:
            settings = SiteSettings.get_current_settings()
            if settings:
                # 사이트 모드 가져오기 (기본값: dark)
                site_mode = getattr(settings, 'site_mode', 'dark')
                if site_mode not in ['light', 'dark']:
                    site_mode = 'dark'
                
                return dict(
                    site_mode=site_mode,
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
        
        return dict(
            site_mode='dark',
            site_colors={
                'main_rgb': None,
                'sub_rgb': None,
                'background_rgb': None,
                'main_hex': None,
                'sub_hex': None,
                'background_hex': None
            }
        )
    
    # 블루프린트 등록
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    
    # 번역 헬퍼 함수 등록
    register_template_helpers(app)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)
