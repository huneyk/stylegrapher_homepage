"""
이메일 발송 유틸리티 - 재시도 로직 및 실패 큐 관리
"""
import time
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from functools import wraps

from flask import current_app
from flask_mail import Message

from extensions import mail
from utils.mongo_models import get_mongo_db

# 로깅 설정
logger = logging.getLogger('email_utils')
logger.setLevel(logging.INFO)

# 콘솔 핸들러 추가
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


def send_email_with_retry(
    subject: str,
    sender: str,
    recipients: List[str],
    body: str,
    reply_to: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    record_type: str = 'booking',
    record_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    이메일 발송 (재시도 로직 포함)
    
    Args:
        subject: 이메일 제목
        sender: 발신자 이메일
        recipients: 수신자 이메일 목록
        body: 이메일 본문
        reply_to: 회신 주소 (선택)
        max_retries: 최대 재시도 횟수 (기본 3회)
        retry_delay: 재시도 간격 (초, 기본 2초, 지수 백오프 적용)
        record_type: 관련 레코드 타입 (booking/inquiry)
        record_id: 관련 레코드 ID (실패 시 큐에 저장용)
    
    Returns:
        Tuple[bool, Optional[str]]: (성공 여부, 에러 메시지)
    """
    # 설정 검증
    if not sender:
        error_msg = "MAIL_DEFAULT_SENDER가 설정되지 않았습니다. 환경변수를 확인하세요."
        logger.error(f"❌ 이메일 발송 실패: {error_msg}")
        _save_failed_email(subject, sender, recipients, body, reply_to, error_msg, record_type, record_id)
        return False, error_msg
    
    if not recipients:
        error_msg = "수신자 이메일이 없습니다."
        logger.error(f"❌ 이메일 발송 실패: {error_msg}")
        return False, error_msg
    
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            msg = Message(
                subject=subject,
                sender=sender,
                recipients=recipients,
                body=body
            )
            
            if reply_to:
                msg.reply_to = reply_to
            
            mail.send(msg)
            
            logger.info(f"✅ 이메일 발송 성공 (시도 {attempt}/{max_retries}): {', '.join(recipients)}")
            return True, None
            
        except AssertionError as e:
            # Flask-Mail 설정 오류 (sender 누락 등) - 재시도 불필요
            error_msg = f"Flask-Mail 설정 오류: {str(e)}"
            logger.error(f"❌ 이메일 발송 실패 (설정 오류): {error_msg}")
            _save_failed_email(subject, sender, recipients, body, reply_to, error_msg, record_type, record_id)
            return False, error_msg
            
        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"⚠️ 이메일 발송 실패 (시도 {attempt}/{max_retries}): {last_error}"
            )
            
            if attempt < max_retries:
                # 지수 백오프: 2초 → 4초 → 8초
                wait_time = retry_delay * (2 ** (attempt - 1))
                logger.info(f"   {wait_time}초 후 재시도...")
                time.sleep(wait_time)
    
    # 모든 재시도 실패
    error_msg = f"최대 재시도 횟수({max_retries}회) 초과. 마지막 오류: {last_error}"
    logger.error(f"❌ 이메일 발송 최종 실패: {error_msg}")
    _save_failed_email(subject, sender, recipients, body, reply_to, error_msg, record_type, record_id)
    return False, error_msg


def _save_failed_email(
    subject: str,
    sender: str,
    recipients: List[str],
    body: str,
    reply_to: Optional[str],
    error_message: str,
    record_type: str,
    record_id: Optional[str]
):
    """
    실패한 이메일을 MongoDB 큐에 저장 (나중에 재시도용)
    """
    try:
        db = get_mongo_db()
        
        failed_email = {
            'subject': subject,
            'sender': sender,
            'recipients': recipients,
            'body': body,
            'reply_to': reply_to,
            'error_message': error_message,
            'record_type': record_type,
            'record_id': record_id,
            'retry_count': 0,
            'max_retries': 5,
            'status': 'pending',  # pending, retrying, sent, failed
            'created_at': datetime.now(timezone.utc),
            'last_attempt_at': datetime.now(timezone.utc),
            'next_retry_at': datetime.now(timezone.utc)
        }
        
        db.failed_emails.insert_one(failed_email)
        logger.info(f"📋 실패한 이메일을 큐에 저장: {subject[:50]}...")
        
    except Exception as e:
        logger.error(f"❌ 실패한 이메일 큐 저장 오류: {str(e)}")


def retry_failed_emails(max_emails: int = 10) -> dict:
    """
    실패한 이메일 큐에서 재시도
    
    Args:
        max_emails: 한 번에 처리할 최대 이메일 수
    
    Returns:
        dict: 처리 결과 통계
    """
    try:
        db = get_mongo_db()
        
        # 재시도 대상 이메일 조회
        now = datetime.now(timezone.utc)
        failed_emails = list(db.failed_emails.find({
            'status': {'$in': ['pending', 'retrying']},
            'retry_count': {'$lt': 5},
            'next_retry_at': {'$lte': now}
        }).limit(max_emails))
        
        results = {'total': len(failed_emails), 'success': 0, 'failed': 0}
        
        for email_doc in failed_emails:
            # 상태 업데이트
            db.failed_emails.update_one(
                {'_id': email_doc['_id']},
                {'$set': {'status': 'retrying', 'last_attempt_at': now}}
            )
            
            try:
                msg = Message(
                    subject=email_doc['subject'],
                    sender=email_doc['sender'],
                    recipients=email_doc['recipients'],
                    body=email_doc['body']
                )
                
                if email_doc.get('reply_to'):
                    msg.reply_to = email_doc['reply_to']
                
                mail.send(msg)
                
                # 성공 - 큐에서 제거 또는 상태 업데이트
                db.failed_emails.update_one(
                    {'_id': email_doc['_id']},
                    {'$set': {'status': 'sent', 'sent_at': now}}
                )
                
                logger.info(f"✅ 큐 이메일 발송 성공: {email_doc['subject'][:50]}...")
                results['success'] += 1
                
            except Exception as e:
                retry_count = email_doc.get('retry_count', 0) + 1
                
                if retry_count >= 5:
                    # 최대 재시도 초과 - 영구 실패 처리
                    db.failed_emails.update_one(
                        {'_id': email_doc['_id']},
                        {'$set': {
                            'status': 'failed',
                            'retry_count': retry_count,
                            'final_error': str(e)
                        }}
                    )
                    logger.error(f"❌ 큐 이메일 영구 실패: {email_doc['subject'][:50]}...")
                else:
                    # 다음 재시도 스케줄
                    next_retry_minutes = 5 * (2 ** retry_count)  # 10분, 20분, 40분, 80분
                    next_retry_at = datetime.now(timezone.utc)
                    
                    db.failed_emails.update_one(
                        {'_id': email_doc['_id']},
                        {'$set': {
                            'status': 'pending',
                            'retry_count': retry_count,
                            'error_message': str(e),
                            'next_retry_at': next_retry_at
                        }}
                    )
                    logger.warning(f"⚠️ 큐 이메일 재시도 실패 ({retry_count}/5): {email_doc['subject'][:50]}...")
                
                results['failed'] += 1
        
        return results
        
    except Exception as e:
        logger.error(f"❌ 실패한 이메일 재시도 중 오류: {str(e)}")
        return {'total': 0, 'success': 0, 'failed': 0, 'error': str(e)}


def get_failed_email_count() -> int:
    """실패한 이메일 큐의 대기 중인 이메일 수 반환"""
    try:
        db = get_mongo_db()
        return db.failed_emails.count_documents({
            'status': {'$in': ['pending', 'retrying']}
        })
    except Exception:
        return 0


def send_customer_email(
    email: str,
    subject: str,
    body: str,
    record_type: str = 'booking',
    record_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    고객에게 이메일 발송 (편의 함수)
    """
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')
    
    return send_email_with_retry(
        subject=subject,
        sender=sender,
        recipients=[email],
        body=body,
        record_type=record_type,
        record_id=record_id
    )


def send_admin_notification(
    recipients: List[str],
    subject: str,
    body: str,
    reply_to: Optional[str] = None,
    record_type: str = 'booking',
    record_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    관리자에게 알림 이메일 발송 (편의 함수)
    """
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')
    
    return send_email_with_retry(
        subject=subject,
        sender=sender,
        recipients=recipients,
        body=body,
        reply_to=reply_to,
        record_type=record_type,
        record_id=record_id
    )






