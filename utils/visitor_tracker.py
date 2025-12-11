"""
방문자 추적 시스템

사용자 세션 정보를 MongoDB에 기록하고 분석합니다.
- IP 주소
- 위치 (GeoIP)
- 브라우저/User-Agent
- 접속 페이지
- 토큰 사용량
- 비용
"""

import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pymongo import MongoClient
from dotenv import load_dotenv
import requests

load_dotenv()

# MongoDB 연결
_mongo_client = None
_visitors_collection = None
_connection_pid = None


def get_visitors_collection():
    """방문자 컬렉션 반환 (fork-safe)"""
    global _mongo_client, _visitors_collection, _connection_pid
    
    current_pid = os.getpid()
    
    if _connection_pid is not None and _connection_pid != current_pid:
        _mongo_client = None
        _visitors_collection = None
    
    if _visitors_collection is not None:
        return _visitors_collection
    
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        return None
    
    try:
        _mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000
        )
        db = _mongo_client['STG-DB']
        _visitors_collection = db['visitor_sessions']
        _connection_pid = current_pid
        
        # 인덱스 생성
        _visitors_collection.create_index([("timestamp", -1)])
        _visitors_collection.create_index([("ip_address", 1)])
        _visitors_collection.create_index([("session_id", 1)])
        
        return _visitors_collection
    except Exception as e:
        print(f"방문자 추적 MongoDB 연결 실패: {str(e)}")
        return None


def get_ip_location(ip_address: str) -> Dict:
    """
    IP 주소로 위치 정보 조회 (무료 API 사용)
    
    Args:
        ip_address: IP 주소
    
    Returns:
        위치 정보 딕셔너리
    """
    # 로컬 IP 처리
    if ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
        return {
            'country': 'Local',
            'country_code': 'LO',
            'city': 'localhost',
            'region': '',
            'isp': 'Local Network'
        }
    
    try:
        # ip-api.com 무료 API 사용 (분당 45회 제한)
        response = requests.get(
            f'http://ip-api.com/json/{ip_address}',
            timeout=3
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return {
                    'country': data.get('country', 'Unknown'),
                    'country_code': data.get('countryCode', ''),
                    'city': data.get('city', 'Unknown'),
                    'region': data.get('regionName', ''),
                    'isp': data.get('isp', ''),
                    'lat': data.get('lat'),
                    'lon': data.get('lon')
                }
    except Exception as e:
        print(f"IP 위치 조회 오류: {str(e)}")
    
    return {
        'country': 'Unknown',
        'country_code': '',
        'city': 'Unknown',
        'region': '',
        'isp': ''
    }


def parse_user_agent(user_agent: str) -> Dict:
    """
    User-Agent 문자열 파싱
    
    Args:
        user_agent: User-Agent 문자열
    
    Returns:
        브라우저/OS 정보
    """
    if not user_agent:
        return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}
    
    ua_lower = user_agent.lower()
    
    # 브라우저 감지
    browser = 'Unknown'
    if 'edg/' in ua_lower or 'edge/' in ua_lower:
        browser = 'Edge'
    elif 'chrome/' in ua_lower and 'safari/' in ua_lower:
        browser = 'Chrome'
    elif 'firefox/' in ua_lower:
        browser = 'Firefox'
    elif 'safari/' in ua_lower and 'chrome/' not in ua_lower:
        browser = 'Safari'
    elif 'opera' in ua_lower or 'opr/' in ua_lower:
        browser = 'Opera'
    elif 'msie' in ua_lower or 'trident/' in ua_lower:
        browser = 'Internet Explorer'
    elif 'bot' in ua_lower or 'crawler' in ua_lower or 'spider' in ua_lower:
        browser = 'Bot/Crawler'
    elif 'curl' in ua_lower:
        browser = 'cURL'
    elif 'python' in ua_lower:
        browser = 'Python'
    
    # OS 감지
    os_name = 'Unknown'
    if 'windows' in ua_lower:
        os_name = 'Windows'
    elif 'macintosh' in ua_lower or 'mac os' in ua_lower:
        os_name = 'macOS'
    elif 'linux' in ua_lower and 'android' not in ua_lower:
        os_name = 'Linux'
    elif 'android' in ua_lower:
        os_name = 'Android'
    elif 'iphone' in ua_lower or 'ipad' in ua_lower:
        os_name = 'iOS'
    
    # 디바이스 감지
    device = 'Desktop'
    if 'mobile' in ua_lower or 'android' in ua_lower or 'iphone' in ua_lower:
        device = 'Mobile'
    elif 'tablet' in ua_lower or 'ipad' in ua_lower:
        device = 'Tablet'
    elif 'bot' in ua_lower or 'crawler' in ua_lower:
        device = 'Bot'
    
    return {
        'browser': browser,
        'os': os_name,
        'device': device,
        'raw': user_agent[:200]  # 원본 저장 (200자 제한)
    }


def log_visitor(
    ip_address: str,
    user_agent: str,
    page_url: str,
    session_id: Optional[str] = None,
    language: str = 'ko',
    referrer: Optional[str] = None,
    tokens_used: int = 0,
    cost_usd: float = 0.0,
    service_page: Optional[str] = None
) -> Optional[str]:
    """
    방문자 정보 기록
    
    Args:
        ip_address: IP 주소
        user_agent: User-Agent 문자열
        page_url: 접속 페이지 URL
        session_id: 세션 ID
        language: 선택된 언어
        referrer: 이전 페이지
        tokens_used: 사용된 토큰 수
        cost_usd: 비용
        service_page: 접속한 서비스 페이지명
    
    Returns:
        생성된 문서 ID 또는 None
    """
    collection = get_visitors_collection()
    if collection is None:
        return None
    
    try:
        # 위치 정보 조회
        location = get_ip_location(ip_address)
        
        # User-Agent 파싱
        ua_info = parse_user_agent(user_agent)
        
        # 서비스 페이지 추출
        if not service_page and page_url:
            # URL에서 서비스 페이지 추출
            if '/service/' in page_url:
                service_page = 'Service'
            elif '/gallery' in page_url:
                service_page = 'Gallery'
            elif '/about' in page_url:
                service_page = 'About'
            elif '/booking' in page_url:
                service_page = 'Booking'
            elif '/inquiry' in page_url:
                service_page = 'Inquiry'
            elif '/contact' in page_url:
                service_page = 'Contact'
            elif page_url in ['/', ''] or '/index' in page_url:
                service_page = 'Home'
            else:
                service_page = 'Other'
        
        doc = {
            "timestamp": datetime.utcnow(),
            "ip_address": ip_address,
            "location": location,
            "user_agent": ua_info,
            "page_url": page_url,
            "service_page": service_page,
            "session_id": session_id,
            "language": language,
            "referrer": referrer,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd
        }
        
        result = collection.insert_one(doc)
        return str(result.inserted_id)
        
    except Exception as e:
        print(f"방문자 기록 오류: {str(e)}")
        return None


def update_visitor_tokens(session_id: str, tokens_used: int, cost_usd: float) -> bool:
    """
    세션의 토큰 사용량 업데이트
    
    Args:
        session_id: 세션 ID
        tokens_used: 추가 토큰 수
        cost_usd: 추가 비용
    
    Returns:
        성공 여부
    """
    collection = get_visitors_collection()
    if collection is None:
        return False
    
    try:
        # 해당 세션의 가장 최근 기록 업데이트
        collection.update_one(
            {"session_id": session_id},
            {
                "$inc": {
                    "tokens_used": tokens_used,
                    "cost_usd": cost_usd
                }
            },
            sort=[("timestamp", -1)]
        )
        return True
    except Exception as e:
        print(f"토큰 업데이트 오류: {str(e)}")
        return False


def get_visitor_sessions(
    days: int = 30,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = 'timestamp',
    sort_order: int = -1,
    ip_filter: Optional[str] = None,
    country_filter: Optional[str] = None
) -> tuple:
    """
    방문자 세션 목록 조회
    
    Args:
        days: 조회 기간 (일)
        limit: 조회 개수
        offset: 오프셋 (페이징)
        sort_by: 정렬 기준
        sort_order: 정렬 순서 (-1: 내림차순, 1: 오름차순)
        ip_filter: IP 필터
        country_filter: 국가 필터
    
    Returns:
        (세션 목록, 전체 개수)
    """
    collection = get_visitors_collection()
    if collection is None:
        return [], 0
    
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        # 필터 조건
        query = {"timestamp": {"$gte": since}}
        
        if ip_filter:
            query["ip_address"] = {"$regex": ip_filter, "$options": "i"}
        
        if country_filter:
            query["location.country"] = {"$regex": country_filter, "$options": "i"}
        
        # 전체 개수
        total_count = collection.count_documents(query)
        
        # 정렬 및 페이징
        cursor = collection.find(query).sort(sort_by, sort_order).skip(offset).limit(limit)
        sessions = list(cursor)
        
        return sessions, total_count
        
    except Exception as e:
        print(f"세션 조회 오류: {str(e)}")
        return [], 0


def get_visitor_stats(days: int = 30) -> Dict:
    """
    방문자 통계
    
    Args:
        days: 조회 기간 (일)
    
    Returns:
        통계 딕셔너리
    """
    collection = get_visitors_collection()
    if collection is None:
        return {
            'total_sessions': 0,
            'unique_visitors': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_country': {},
            'by_browser': {},
            'by_device': {},
            'by_page': {},
            'by_language': {}
        }
    
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        stats = {
            'total_sessions': 0,
            'unique_visitors': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_country': {},
            'by_browser': {},
            'by_device': {},
            'by_page': {},
            'by_language': {}
        }
        
        # 기본 통계
        stats['total_sessions'] = collection.count_documents({"timestamp": {"$gte": since}})
        
        # 고유 방문자 수
        unique_ips = collection.distinct("ip_address", {"timestamp": {"$gte": since}})
        stats['unique_visitors'] = len(unique_ips)
        
        # 토큰/비용 합계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_tokens": {"$sum": "$tokens_used"},
                "total_cost": {"$sum": "$cost_usd"}
            }}
        ]
        result = list(collection.aggregate(pipeline))
        if result:
            stats['total_tokens'] = result[0].get('total_tokens', 0)
            stats['total_cost'] = round(result[0].get('total_cost', 0), 4)
        
        # 국가별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$location.country", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        for item in collection.aggregate(pipeline):
            if item['_id']:
                stats['by_country'][item['_id']] = item['count']
        
        # 브라우저별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$user_agent.browser", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        for item in collection.aggregate(pipeline):
            if item['_id']:
                stats['by_browser'][item['_id']] = item['count']
        
        # 디바이스별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$user_agent.device", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        for item in collection.aggregate(pipeline):
            if item['_id']:
                stats['by_device'][item['_id']] = item['count']
        
        # 페이지별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$service_page", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        for item in collection.aggregate(pipeline):
            if item['_id']:
                stats['by_page'][item['_id']] = item['count']
        
        # 언어별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        for item in collection.aggregate(pipeline):
            if item['_id']:
                stats['by_language'][item['_id']] = item['count']
        
        return stats
        
    except Exception as e:
        print(f"통계 조회 오류: {str(e)}")
        return {
            'total_sessions': 0,
            'unique_visitors': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_country': {},
            'by_browser': {},
            'by_device': {},
            'by_page': {},
            'by_language': {},
            'error': str(e)
        }


def delete_visitor_session(session_id: str) -> bool:
    """세션 기록 삭제"""
    collection = get_visitors_collection()
    if collection is None:
        return False
    
    try:
        from bson import ObjectId
        result = collection.delete_one({"_id": ObjectId(session_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"세션 삭제 오류: {str(e)}")
        return False


def export_visitor_data(days: int = 30) -> List[Dict]:
    """방문자 데이터 내보내기"""
    collection = get_visitors_collection()
    if collection is None:
        return []
    
    try:
        since = datetime.utcnow() - timedelta(days=days)
        cursor = collection.find({"timestamp": {"$gte": since}}).sort("timestamp", -1)
        
        data = []
        for doc in cursor:
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('timestamp'), datetime):
                doc['timestamp'] = doc['timestamp'].isoformat()
            data.append(doc)
        
        return data
    except Exception as e:
        print(f"데이터 내보내기 오류: {str(e)}")
        return []
