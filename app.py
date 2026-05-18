"""
Flask 애플리케이션 팩토리 - MongoDB 기반
"""
import os
import json
import threading
from datetime import datetime, timedelta
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

# 전역 메모리 캐시 (context_processor용 성능 최적화)
_context_cache = {}
_context_cache_timestamps = {}
_context_cache_lock = threading.Lock()
CONTEXT_CACHE_TIMEOUT = 300  # 5분

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
    
    # 캐싱 설정 (FileSystemCache - 파일 기반, gunicorn 멀티 워커 간 캐시 공유)
    # SimpleCache는 프로세스별 메모리에 저장되어 워커 간 캐시 무효화가 안 되므로
    # admin에서 데이터 수정 후 다국어 페이지에 즉시 반영되지 않는 문제가 발생함
    app.config['CACHE_TYPE'] = 'FileSystemCache'
    app.config['CACHE_DIR'] = os.path.join(app.root_path, 'static', 'cache', 'flask_cache')
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5분
    app.config['CACHE_THRESHOLD'] = 1000  # 최대 캐시 항목 수
    os.makedirs(app.config['CACHE_DIR'], exist_ok=True)
    cache.init_app(app)
    
    # SQLAlchemy 초기화 (마이그레이션 스크립트용으로 유지)
    db.init_app(app)
    migrate.init_app(app, db)
    
    # 확장 기능 초기화
    login_manager.init_app(app)
    mail.init_app(app)
    
    # Babel 초기화
    def get_locale():
        # 1. URL 파라미터에서 언어 확인 (최우선)
        lang = request.args.get('lang')
        if lang and lang in SUPPORTED_LANGUAGES:
            session['lang'] = lang
            session.permanent = True  # 세션 영구 저장
            return lang
        
        # 2. 쿠키에서 언어 확인 (세션과 별도로 클라이언트 측 저장)
        cookie_lang = request.cookies.get('preferred_lang')
        if cookie_lang and cookie_lang in SUPPORTED_LANGUAGES:
            # 쿠키 언어가 있으면 세션에도 동기화
            if session.get('lang') != cookie_lang:
                session['lang'] = cookie_lang
                session.permanent = True
            return cookie_lang
        
        # 3. 세션에서 언어 확인
        if 'lang' in session and session['lang'] in SUPPORTED_LANGUAGES:
            return session['lang']
        
        # 4. 브라우저 Accept-Language 헤더에서 언어 감지 (첫 접속 시)
        best_match = request.accept_languages.best_match(list(SUPPORTED_LANGUAGES.keys()))
        if best_match:
            # 브라우저 언어를 세션에 저장 (첫 접속 시에만)
            session['lang'] = best_match
            session.permanent = True
            return best_match
        
        # 5. 기본값
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
        
        # 정적 파일 캐싱 헤더 설정 (성능 최적화 강화)
        if request.path.startswith('/static/'):
            # CSS, JS 파일 - 1주일 캐싱 (immutable 추가)
            if request.path.endswith(('.css', '.js')):
                response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
            # 이미지 파일 - 1개월 캐싱 (immutable 추가)
            elif request.path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg', '.webp')):
                response.headers['Cache-Control'] = 'public, max-age=2592000, immutable'
            # 폰트 파일 - 1년 캐싱 (immutable 추가)
            elif request.path.endswith(('.woff', '.woff2', '.ttf', '.eot')):
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            # JSON 데이터 파일 (번역 등) - 5분 캐싱
            elif request.path.endswith('.json'):
                response.headers['Cache-Control'] = 'public, max-age=300'
            
            # Vary 헤더 추가 (압축 지원)
            response.headers['Vary'] = 'Accept-Encoding'
        
        # /image/ 경로는 별도로 처리됨 (routes/main.py)
        
        # 세션에 언어가 있지만 쿠키가 없는 경우 쿠키 설정 (브라우저 언어 감지 후 자동 설정)
        if 'lang' in session and session['lang'] in SUPPORTED_LANGUAGES:
            cookie_lang = request.cookies.get('preferred_lang')
            if not cookie_lang or cookie_lang != session['lang']:
                response.set_cookie('preferred_lang', session['lang'], 
                                   max_age=365*24*60*60, samesite='Lax')
        
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
    
    @app.template_filter('oneline')
    def oneline_filter(value):
        """줄바꿈을 공백으로 대체하여 한 줄로 만드는 필터"""
        if not value:
            return value
        import re
        # 줄바꿈 문자를 공백으로 대체하고 연속된 공백을 하나로 정리
        return re.sub(r'\s+', ' ', str(value)).strip()
    
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
            session.permanent = True  # 세션 영구 저장
        
        # AJAX 요청인 경우 JSON 응답 + 쿠키 설정
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           'application/json' in request.headers.get('Accept', '') or \
           request.headers.get('Sec-Fetch-Mode') == 'cors':
            response = jsonify({'success': True, 'lang': lang})
            # 클라이언트 측 쿠키도 설정 (1년 유지)
            response.set_cookie('preferred_lang', lang, max_age=365*24*60*60, samesite='Lax')
            return response
        
        # 일반 요청인 경우 리다이렉트 + 쿠키 설정
        referrer = request.referrer
        redirect_url = referrer if referrer else url_for('main.index')
        response = redirect(redirect_url)
        response.set_cookie('preferred_lang', lang, max_age=365*24*60*60, samesite='Lax')
        return response
    
    # 전역 컨텍스트 - 사이드 메뉴용 카테고리별 서비스 (캐싱 적용)
    def _get_cached_menu_data():
        """메뉴 데이터를 캐시에서 조회하거나 새로 생성"""
        cache_key = 'menu_data'
        
        with _context_cache_lock:
            # 캐시 유효성 확인
            if cache_key in _context_cache_timestamps:
                if datetime.now() - _context_cache_timestamps[cache_key] < timedelta(seconds=CONTEXT_CACHE_TIMEOUT):
                    return _context_cache[cache_key]
        
        # 카테고리 순서와 설정 (표시 순서대로 정렬)
        categories_order = ['ai_analysis', 'consulting', 'oneday', 'photo']
        categories_config = {
            'ai_analysis': {
                'title': 'AI 분석',
                'icon': 'bi-cpu',
                'key': 'stg-ai',
                'services': []
            },
            'consulting': {
                'title': '컨설팅 프로그램',
                'icon': 'bi-palette',
                'key': 'styling-consulting',
                'services': []
            },
            'oneday': {
                'title': '원데이 스타일링',
                'icon': 'bi-magic',
                'key': 'oneday-styling',
                'services': []
            },
            'photo': {
                'title': '프리미엄 화보 제작',
                'icon': 'bi-camera',
                'key': 'photo-profile',
                'services': []
            }
        }
        
        try:
            services = Service.query_all()
            for service in services:
                if service.category and service.category in categories_config:
                    categories_config[service.category]['services'].append(service)
        except Exception as e:
            print(f"Error loading menu data: {str(e)}")
        
        result = dict(
            menu_categories=categories_config,
            menu_categories_order=categories_order
        )
        
        # 캐시에 저장
        with _context_cache_lock:
            _context_cache[cache_key] = result
            _context_cache_timestamps[cache_key] = datetime.now()
        
        return result
    
    @app.context_processor
    def inject_menu_data():
        return _get_cached_menu_data()
    
    # 전역 컨텍스트 - 사이트 색상 설정 (Light mode 전용, 캐싱 적용)
    def _get_cached_site_colors():
        """사이트 색상 설정을 캐시에서 조회하거나 새로 생성"""
        cache_key = 'site_colors'
        
        with _context_cache_lock:
            # 캐시 유효성 확인
            if cache_key in _context_cache_timestamps:
                if datetime.now() - _context_cache_timestamps[cache_key] < timedelta(seconds=CONTEXT_CACHE_TIMEOUT):
                    return _context_cache[cache_key]
        
        result = dict(
            site_mode='light',
            site_colors={
                'main_rgb': None,
                'sub_rgb': None,
                'background_rgb': None,
                'main_hex': None,
                'sub_hex': None,
                'background_hex': None
            }
        )
        
        try:
            settings = SiteSettings.get_current_settings()
            if settings:
                result = dict(
                    site_mode='light',
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
        
        # 캐시에 저장
        with _context_cache_lock:
            _context_cache[cache_key] = result
            _context_cache_timestamps[cache_key] = datetime.now()
        
        return result
    
    @app.context_processor
    def inject_site_colors():
        return _get_cached_site_colors()
    
    # 블루프린트 등록
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix='/admin')
    
    # 번역 헬퍼 함수 등록
    register_template_helpers(app)
    
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8000)
