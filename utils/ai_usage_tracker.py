"""
AI 사용량 추적 시스템

OpenAI API 호출 시 토큰 사용량을 MongoDB에 기록하고 통계를 제공합니다.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# MongoDB 연결
_mongo_client = None
_usage_collection = None
_connection_pid = None


def get_usage_collection():
    """AI 사용량 컬렉션 반환 (fork-safe)"""
    global _mongo_client, _usage_collection, _connection_pid
    
    current_pid = os.getpid()
    
    if _connection_pid is not None and _connection_pid != current_pid:
        _mongo_client = None
        _usage_collection = None
    
    if _usage_collection is not None:
        return _usage_collection
    
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
        _usage_collection = db['ai_usage']
        _connection_pid = current_pid
        
        # 인덱스 생성
        _usage_collection.create_index([("timestamp", -1)])
        _usage_collection.create_index([("usage_type", 1), ("timestamp", -1)])
        _usage_collection.create_index([("model", 1)])
        
        return _usage_collection
    except Exception as e:
        print(f"AI 사용량 추적 MongoDB 연결 실패: {str(e)}")
        return None


def log_ai_usage(
    usage_type: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float = 0.0,
    metadata: Optional[Dict] = None
) -> bool:
    """
    AI API 사용량 기록
    
    Args:
        usage_type: 사용 유형 (translation, email_agent, chat 등)
        model: 사용된 모델 (gpt-4o-mini, gpt-4o 등)
        prompt_tokens: 입력 토큰 수
        completion_tokens: 출력 토큰 수
        total_tokens: 총 토큰 수
        cost_usd: 예상 비용 (USD)
        metadata: 추가 메타데이터
    
    Returns:
        성공 여부
    """
    collection = get_usage_collection()
    if collection is None:
        return False
    
    try:
        doc = {
            "timestamp": datetime.utcnow(),
            "usage_type": usage_type,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "metadata": metadata or {}
        }
        collection.insert_one(doc)
        return True
    except Exception as e:
        print(f"AI 사용량 기록 오류: {str(e)}")
        return False


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    토큰 수 기반 비용 계산 (USD)
    
    OpenAI 가격 기준 (2024년 기준, 변동 가능)
    """
    # 모델별 가격 (1K 토큰당 USD)
    pricing = {
        'gpt-4o': {'input': 0.005, 'output': 0.015},
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
    }
    
    model_pricing = pricing.get(model, pricing['gpt-4o-mini'])
    
    input_cost = (prompt_tokens / 1000) * model_pricing['input']
    output_cost = (completion_tokens / 1000) * model_pricing['output']
    
    return round(input_cost + output_cost, 6)


def get_usage_stats(hours: int = 24) -> Dict:
    """
    지정된 시간 동안의 사용량 통계
    
    Args:
        hours: 조회할 시간 범위 (기본 24시간)
    
    Returns:
        사용량 통계 딕셔너리
    """
    collection = get_usage_collection()
    if collection is None:
        return {
            'total_requests': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_type': {},
            'by_model': {},
            'hourly': []
        }
    
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # 기본 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_requests": {"$sum": 1},
                "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                "total_completion_tokens": {"$sum": "$completion_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost": {"$sum": "$cost_usd"}
            }}
        ]
        result = list(collection.aggregate(pipeline))
        
        stats = {
            'total_requests': 0,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_type': {},
            'by_model': {},
            'hourly': [],
            'hours': hours
        }
        
        if result:
            stats.update({
                'total_requests': result[0].get('total_requests', 0),
                'total_prompt_tokens': result[0].get('total_prompt_tokens', 0),
                'total_completion_tokens': result[0].get('total_completion_tokens', 0),
                'total_tokens': result[0].get('total_tokens', 0),
                'total_cost': round(result[0].get('total_cost', 0), 4)
            })
        
        # 유형별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": "$usage_type",
                "count": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"tokens": -1}}
        ]
        by_type = list(collection.aggregate(pipeline))
        stats['by_type'] = {
            item['_id']: {
                'count': item['count'],
                'tokens': item['tokens'],
                'cost': round(item['cost'], 4)
            } for item in by_type if item['_id']
        }
        
        # 모델별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": "$model",
                "count": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"tokens": -1}}
        ]
        by_model = list(collection.aggregate(pipeline))
        stats['by_model'] = {
            item['_id']: {
                'count': item['count'],
                'tokens': item['tokens'],
                'cost': round(item['cost'], 4)
            } for item in by_model if item['_id']
        }
        
        # 시간별 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"},
                    "hour": {"$hour": "$timestamp"}
                },
                "count": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1, "_id.hour": 1}}
        ]
        hourly = list(collection.aggregate(pipeline))
        stats['hourly'] = [
            {
                'datetime': f"{item['_id']['year']}-{item['_id']['month']:02d}-{item['_id']['day']:02d} {item['_id']['hour']:02d}:00",
                'count': item['count'],
                'tokens': item['tokens'],
                'cost': round(item['cost'], 4)
            } for item in hourly
        ]
        
        return stats
        
    except Exception as e:
        print(f"사용량 통계 조회 오류: {str(e)}")
        return {
            'total_requests': 0,
            'total_tokens': 0,
            'total_cost': 0,
            'by_type': {},
            'by_model': {},
            'hourly': [],
            'error': str(e)
        }


def get_recent_usage(limit: int = 100) -> List[Dict]:
    """최근 사용 내역 조회"""
    collection = get_usage_collection()
    if collection is None:
        return []
    
    try:
        cursor = collection.find().sort("timestamp", -1).limit(limit)
        return list(cursor)
    except Exception as e:
        print(f"최근 사용 내역 조회 오류: {str(e)}")
        return []


def get_daily_summary(days: int = 30) -> List[Dict]:
    """일별 사용량 요약"""
    collection = get_usage_collection()
    if collection is None:
        return []
    
    try:
        since = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"}
                },
                "requests": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}
        ]
        
        result = list(collection.aggregate(pipeline))
        return [
            {
                'date': f"{item['_id']['year']}-{item['_id']['month']:02d}-{item['_id']['day']:02d}",
                'requests': item['requests'],
                'tokens': item['tokens'],
                'cost': round(item['cost'], 4)
            } for item in result
        ]
    except Exception as e:
        print(f"일별 요약 조회 오류: {str(e)}")
        return []


def get_ai_insights() -> Dict:
    """
    AI 사용 인사이트 분석
    
    Returns:
        인사이트 분석 결과
    """
    collection = get_usage_collection()
    
    insights = {
        'summary': {},
        'trends': {},
        'recommendations': [],
        'top_usage': [],
        'cost_analysis': {}
    }
    
    if collection is None:
        return insights
    
    try:
        now = datetime.utcnow()
        
        # 지난 7일 vs 이전 7일 비교
        last_7_days = now - timedelta(days=7)
        prev_7_days = now - timedelta(days=14)
        
        # 최근 7일 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": last_7_days}}},
            {"$group": {
                "_id": None,
                "requests": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }}
        ]
        recent = list(collection.aggregate(pipeline))
        recent_data = recent[0] if recent else {'requests': 0, 'tokens': 0, 'cost': 0}
        
        # 이전 7일 통계
        pipeline = [
            {"$match": {"timestamp": {"$gte": prev_7_days, "$lt": last_7_days}}},
            {"$group": {
                "_id": None,
                "requests": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }}
        ]
        previous = list(collection.aggregate(pipeline))
        prev_data = previous[0] if previous else {'requests': 0, 'tokens': 0, 'cost': 0}
        
        # 트렌드 계산
        def calc_trend(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)
        
        insights['trends'] = {
            'requests_change': calc_trend(recent_data['requests'], prev_data['requests']),
            'tokens_change': calc_trend(recent_data['tokens'], prev_data['tokens']),
            'cost_change': calc_trend(recent_data['cost'], prev_data['cost'])
        }
        
        insights['summary'] = {
            'last_7_days': {
                'requests': recent_data['requests'],
                'tokens': recent_data['tokens'],
                'cost': round(recent_data['cost'], 4)
            },
            'previous_7_days': {
                'requests': prev_data['requests'],
                'tokens': prev_data['tokens'],
                'cost': round(prev_data['cost'], 4)
            }
        }
        
        # 가장 많이 사용하는 기능
        pipeline = [
            {"$match": {"timestamp": {"$gte": last_7_days}}},
            {"$group": {
                "_id": "$usage_type",
                "count": {"$sum": 1},
                "tokens": {"$sum": "$total_tokens"},
                "cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_usage = list(collection.aggregate(pipeline))
        insights['top_usage'] = [
            {
                'type': item['_id'] or 'unknown',
                'count': item['count'],
                'tokens': item['tokens'],
                'cost': round(item['cost'], 4)
            } for item in top_usage
        ]
        
        # 비용 분석
        total_cost = recent_data['cost']
        insights['cost_analysis'] = {
            'daily_average': round(total_cost / 7, 4) if total_cost else 0,
            'monthly_projection': round((total_cost / 7) * 30, 2),
            'most_expensive_type': insights['top_usage'][0]['type'] if insights['top_usage'] else None
        }
        
        # 추천사항 생성
        recommendations = []
        
        if insights['trends']['cost_change'] > 50:
            recommendations.append({
                'type': 'warning',
                'message': f"비용이 지난 주 대비 {insights['trends']['cost_change']}% 증가했습니다. 사용량을 검토해주세요."
            })
        
        if insights['cost_analysis']['monthly_projection'] > 100:
            recommendations.append({
                'type': 'info',
                'message': f"현재 추세로 월간 예상 비용은 ${insights['cost_analysis']['monthly_projection']:.2f}입니다."
            })
        
        # 모델별 비용 효율성 분석
        pipeline = [
            {"$match": {"timestamp": {"$gte": last_7_days}}},
            {"$group": {
                "_id": "$model",
                "avg_tokens": {"$avg": "$total_tokens"},
                "total_cost": {"$sum": "$cost_usd"},
                "count": {"$sum": 1}
            }}
        ]
        model_analysis = list(collection.aggregate(pipeline))
        
        for model in model_analysis:
            if model['_id'] == 'gpt-4o' and model['count'] > 10:
                recommendations.append({
                    'type': 'tip',
                    'message': f"gpt-4o 모델 사용이 많습니다. 간단한 작업은 gpt-4o-mini로 대체하면 비용을 절약할 수 있습니다."
                })
                break
        
        insights['recommendations'] = recommendations
        
        return insights
        
    except Exception as e:
        print(f"AI 인사이트 분석 오류: {str(e)}")
        insights['error'] = str(e)
        return insights


# 세션 관련 함수들
def get_session_stats() -> Dict:
    """
    Flask 세션 통계 (MongoDB 저장된 세션 정보 기반)
    
    Returns:
        세션 통계
    """
    # Flask의 기본 세션은 클라이언트 사이드이므로
    # 여기서는 로그인 사용자와 활성 연결에 대한 추정치를 반환
    
    try:
        from utils.mongo_models import User
        
        stats = {
            'total_users': User.count(),
            'recent_activity': [],
            'language_distribution': {},
            'active_sessions_estimate': 0
        }
        
        # 최근 로그인 활동은 별도 로깅 필요 (여기서는 기본 구조만)
        return stats
        
    except Exception as e:
        print(f"세션 통계 조회 오류: {str(e)}")
        return {
            'total_users': 0,
            'recent_activity': [],
            'language_distribution': {},
            'error': str(e)
        }


# 사용 유형 상수
USAGE_TYPE_TRANSLATION = 'translation'
USAGE_TYPE_EMAIL_AGENT = 'email_agent'
USAGE_TYPE_CHAT = 'chat'
USAGE_TYPE_SPAM_CHECK = 'spam_check'
USAGE_TYPE_CONTENT_ANALYSIS = 'content_analysis'
