from flask import request, abort, jsonify
from functools import wraps
import time
from collections import defaultdict, deque
import logging

# 보안 로깅 설정
security_logger = logging.getLogger('security')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - SECURITY - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
security_logger.addHandler(handler)
security_logger.setLevel(logging.WARNING)

# Rate limiting 저장소 (실제 환경에서는 Redis 권장)
rate_limit_storage = defaultdict(lambda: deque())

# 악성 IP 및 User-Agent 패턴
BLOCKED_IPS = set()
SUSPICIOUS_PATHS = {
    '/wp-content/', '/wp-admin/', '/wp-login.php', '/wp-22.php',
    '/lv.php', '/xmrlpc.php', '/ae.php', '/plugins.php',
    '/xmlrpc.php', '/wp-config.php', '/.env',
    '/admin.php', '/phpmyadmin/', '/phpMyAdmin/'
}

SUSPICIOUS_USER_AGENTS = {
    'sqlmap', 'nikto', 'nmap', 'masscan', 'zmap',
    'curl', 'wget', 'python-requests', 'scanner'
}

def add_security_headers(response):
    """보안 헤더 추가"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://ajax.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'"
    return response

def is_suspicious_request():
    """의심스러운 요청 패턴 감지"""
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '').lower()
    path = request.path.lower()
    
    # 차단된 IP 확인
    if client_ip in BLOCKED_IPS:
        return True, f"Blocked IP: {client_ip}"
    
    # 의심스러운 경로 확인
    for suspicious_path in SUSPICIOUS_PATHS:
        if suspicious_path in path:
            return True, f"Suspicious path: {path}"
    
    # 의심스러운 User-Agent 확인
    for suspicious_ua in SUSPICIOUS_USER_AGENTS:
        if suspicious_ua in user_agent:
            return True, f"Suspicious User-Agent: {user_agent}"
    
    # 빈 User-Agent (일반적으로 봇)
    if not user_agent:
        return True, "Empty User-Agent"
    
    return False, None

def get_client_ip():
    """클라이언트 실제 IP 주소 추출"""
    # Render.com과 같은 프록시 환경에서 실제 IP 추출
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def rate_limit_check(key: str, limit: int = 60, window: int = 60):
    """Rate limiting 체크 (분당 요청 수 제한)"""
    now = time.time()
    window_start = now - window
    
    # 만료된 요청 제거
    while rate_limit_storage[key] and rate_limit_storage[key][0] < window_start:
        rate_limit_storage[key].popleft()
    
    # 현재 요청 수 확인
    if len(rate_limit_storage[key]) >= limit:
        return False
    
    # 현재 요청 추가
    rate_limit_storage[key].append(now)
    return True

def security_check():
    """종합 보안 검사 데코레이터"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = get_client_ip()
            
            # 의심스러운 요청 패턴 검사
            is_suspicious, reason = is_suspicious_request()
            if is_suspicious:
                security_logger.warning(f"Suspicious request blocked: {reason} - IP: {client_ip} - Path: {request.path}")
                abort(404)  # 404로 위장하여 정보 노출 방지
            
            # Rate limiting 검사
            if not rate_limit_check(f"ip:{client_ip}", limit=120, window=60):
                security_logger.warning(f"Rate limit exceeded - IP: {client_ip} - Path: {request.path}")
                abort(429)  # Too Many Requests
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def block_ip(ip_address):
    """IP 주소 차단"""
    BLOCKED_IPS.add(ip_address)
    security_logger.warning(f"IP blocked: {ip_address}")

def log_security_event(event_type, details):
    """보안 이벤트 로깅"""
    from utils.monitor import security_monitor
    
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    path = request.path
    
    # 콘솔 로그
    security_logger.warning(f"{event_type} - IP: {client_ip} - UA: {user_agent} - Details: {details}")
    
    # 모니터링 시스템에 기록
    security_monitor.log_security_event(event_type, client_ip, user_agent, path, details) 