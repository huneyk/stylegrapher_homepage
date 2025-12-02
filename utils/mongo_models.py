"""
MongoDB 모델 헬퍼 모듈
SQLAlchemy와 유사한 인터페이스로 MongoDB를 사용할 수 있게 해주는 래퍼
"""
import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import json

load_dotenv()

# MongoDB 연결 설정 (fork-safe)
_mongo_client = None
_mongo_db = None
_connection_pid = None  # 연결이 생성된 프로세스 ID 추적

def get_mongo_db():
    """MongoDB 데이터베이스 연결 반환 (fork-safe)"""
    global _mongo_client, _mongo_db, _connection_pid
    
    current_pid = os.getpid()
    
    # fork 이후 새 프로세스에서 호출된 경우 연결 재생성
    if _connection_pid is not None and _connection_pid != current_pid:
        print(f"MongoDB 모델 헬퍼: Fork 감지 (기존 PID: {_connection_pid}, 현재 PID: {current_pid}), 연결 재생성")
        _mongo_client = None
        _mongo_db = None
    
    if _mongo_db is not None:
        return _mongo_db
    
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        raise Exception("MONGO_URI 환경 변수가 설정되지 않았습니다!")
    
    try:
        _mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000,
            retryWrites=True,
            retryReads=True,
            w='majority',
            readPreference='primaryPreferred'
        )
        # 연결 테스트
        _mongo_client.server_info()
        _mongo_db = _mongo_client['STG-DB']
        _connection_pid = current_pid  # 연결 생성 시 PID 저장
        print(f"MongoDB 모델 헬퍼: 데이터베이스 '{_mongo_db.name}' 연결 성공 (PID: {current_pid})")
        return _mongo_db
    except Exception as e:
        print(f"MongoDB 연결 오류: {str(e)}")
        raise


def init_collections():
    """컬렉션 초기화 및 인덱스 생성"""
    db = get_mongo_db()
    
    # users 컬렉션
    if 'users' not in db.list_collection_names():
        db.create_collection('users')
    db.users.create_index('username', unique=True)
    
    # services 컬렉션
    if 'services' not in db.list_collection_names():
        db.create_collection('services')
    db.services.create_index('category')
    
    # service_options 컬렉션
    if 'service_options' not in db.list_collection_names():
        db.create_collection('service_options')
    db.service_options.create_index('service_id')
    
    # gallery_groups 컬렉션
    if 'gallery_groups' not in db.list_collection_names():
        db.create_collection('gallery_groups')
    db.gallery_groups.create_index([('is_pinned', DESCENDING), ('display_order', DESCENDING), ('created_at', DESCENDING)])
    
    # galleries 컬렉션
    if 'galleries' not in db.list_collection_names():
        db.create_collection('galleries')
    db.galleries.create_index('group_id')
    
    # bookings 컬렉션
    if 'bookings' not in db.list_collection_names():
        db.create_collection('bookings')
    db.bookings.create_index([('created_at', DESCENDING)])
    
    # inquiries 컬렉션
    if 'inquiries' not in db.list_collection_names():
        db.create_collection('inquiries')
    db.inquiries.create_index([('created_at', DESCENDING)])
    
    # collage_texts 컬렉션
    if 'collage_texts' not in db.list_collection_names():
        db.create_collection('collage_texts')
    db.collage_texts.create_index('order')
    
    # site_settings 컬렉션
    if 'site_settings' not in db.list_collection_names():
        db.create_collection('site_settings')
    
    # terms_of_service 컬렉션
    if 'terms_of_service' not in db.list_collection_names():
        db.create_collection('terms_of_service')
    
    # privacy_policy 컬렉션
    if 'privacy_policy' not in db.list_collection_names():
        db.create_collection('privacy_policy')
    
    # admin_notification_emails 컬렉션
    if 'admin_notification_emails' not in db.list_collection_names():
        db.create_collection('admin_notification_emails')
    db.admin_notification_emails.create_index('email', unique=True)
    db.admin_notification_emails.create_index('is_active')
    
    print("MongoDB 컬렉션 및 인덱스 초기화 완료")


class MongoModel:
    """MongoDB 모델 기본 클래스"""
    collection_name = None
    
    def __init__(self, **kwargs):
        self._id = kwargs.get('_id') or kwargs.get('id')
        self.id = self._id
        for key, value in kwargs.items():
            if key != '_id':
                setattr(self, key, value)
    
    @classmethod
    def get_collection(cls):
        """컬렉션 반환"""
        db = get_mongo_db()
        return db[cls.collection_name]
    
    @classmethod
    def query_all(cls):
        """모든 문서 조회"""
        collection = cls.get_collection()
        docs = collection.find()
        return [cls.from_doc(doc) for doc in docs]
    
    @classmethod
    def query_filter(cls, **kwargs):
        """필터 조건으로 조회"""
        collection = cls.get_collection()
        docs = collection.find(kwargs)
        return [cls.from_doc(doc) for doc in docs]
    
    @classmethod
    def get_by_id(cls, doc_id):
        """ID로 단일 문서 조회"""
        collection = cls.get_collection()
        # int ID를 사용하는 경우
        doc = collection.find_one({'_id': int(doc_id) if isinstance(doc_id, str) and doc_id.isdigit() else doc_id})
        if doc:
            return cls.from_doc(doc)
        return None
    
    @classmethod
    def get_or_404(cls, doc_id):
        """ID로 조회, 없으면 404 에러"""
        result = cls.get_by_id(doc_id)
        if not result:
            from flask import abort
            abort(404)
        return result
    
    @classmethod
    def from_doc(cls, doc):
        """MongoDB 문서를 모델 객체로 변환"""
        if doc is None:
            return None
        obj = cls(**doc)
        obj._id = doc.get('_id')
        obj.id = doc.get('_id')
        return obj
    
    def to_doc(self):
        """모델 객체를 MongoDB 문서로 변환"""
        doc = {}
        for key, value in self.__dict__.items():
            if not key.startswith('_') or key == '_id':
                if key == '_id' and value is not None:
                    doc['_id'] = value
                elif key != 'id':
                    doc[key] = value
        return doc
    
    def save(self):
        """문서 저장 (insert 또는 update)"""
        collection = self.get_collection()
        doc = self.to_doc()
        
        if self._id is not None:
            # 업데이트 - _id는 제외하고 업데이트 (MongoDB에서 _id 수정 불가)
            update_doc = {k: v for k, v in doc.items() if k != '_id'}
            result = collection.update_one({'_id': self._id}, {'$set': update_doc}, upsert=True)
            print(f"📝 MongoDB update: matched={result.matched_count}, modified={result.modified_count}, _id={self._id}")
        else:
            # 새로운 ID 생성 (auto-increment 시뮬레이션)
            max_doc = collection.find_one(sort=[('_id', DESCENDING)])
            new_id = (max_doc['_id'] + 1) if max_doc and isinstance(max_doc.get('_id'), int) else 1
            doc['_id'] = new_id
            collection.insert_one(doc)
            self._id = new_id
            self.id = new_id
            print(f"📝 MongoDB insert: new_id={new_id}")
        
        return self
    
    def delete(self):
        """문서 삭제"""
        collection = self.get_collection()
        if self._id is not None:
            collection.delete_one({'_id': self._id})
    
    @classmethod
    def delete_by_id(cls, doc_id):
        """ID로 문서 삭제"""
        collection = cls.get_collection()
        collection.delete_one({'_id': int(doc_id) if isinstance(doc_id, str) and doc_id.isdigit() else doc_id})
    
    @classmethod
    def count(cls, filter_dict=None):
        """문서 개수 카운트"""
        collection = cls.get_collection()
        return collection.count_documents(filter_dict or {})


class User(MongoModel):
    """사용자 모델"""
    collection_name = 'users'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.username = kwargs.get('username', '')
        self.email = kwargs.get('email')
        self.password_hash = kwargs.get('password_hash', '')
        self.is_admin = kwargs.get('is_admin', False)
        self.is_active = True
        self.is_authenticated = True
        self.is_anonymous = False
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self._id)
    
    @classmethod
    def get_by_username(cls, username):
        """사용자명으로 조회"""
        collection = cls.get_collection()
        doc = collection.find_one({'username': username})
        return cls.from_doc(doc) if doc else None


class Service(MongoModel):
    """서비스 모델"""
    collection_name = 'services'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.description = kwargs.get('description', '')
        self.category = kwargs.get('category')
        self.details = kwargs.get('details')
        self.packages = kwargs.get('packages')
        self._options = None
    
    @property
    def options(self):
        """해당 서비스의 옵션들 조회"""
        if self._options is None:
            self._options = ServiceOption.query_filter(service_id=self._id)
        return self._options
    
    @classmethod
    def query_all(cls):
        """모든 서비스 조회"""
        collection = cls.get_collection()
        docs = collection.find().sort('_id', ASCENDING)
        return [cls.from_doc(doc) for doc in docs]


class ServiceOption(MongoModel):
    """서비스 옵션 모델"""
    collection_name = 'service_options'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service_id = kwargs.get('service_id')
        self.name = kwargs.get('name', '')
        self.description = kwargs.get('description', '')
        self.detailed_description = kwargs.get('detailed_description', '')
        self.details = kwargs.get('details')
        self.packages = kwargs.get('packages')
        self.booking_method = kwargs.get('booking_method')
        self.payment_info = kwargs.get('payment_info')
        self.guide_info = kwargs.get('guide_info')
        self.refund_policy = kwargs.get('refund_policy')
        self.refund_policy_text = kwargs.get('refund_policy_text')
        self.refund_policy_table = kwargs.get('refund_policy_table')
        self.overtime_charge_table = kwargs.get('overtime_charge_table')
        self._service = None
    
    @property
    def service(self):
        """상위 서비스 조회"""
        if self._service is None and self.service_id:
            self._service = Service.get_by_id(self.service_id)
        return self._service
    
    @classmethod
    def query_all(cls):
        """모든 서비스 옵션 조회"""
        collection = cls.get_collection()
        docs = collection.find().sort('_id', ASCENDING)
        return [cls.from_doc(doc) for doc in docs]


class GalleryGroup(MongoModel):
    """갤러리 그룹 모델"""
    collection_name = 'gallery_groups'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = kwargs.get('title', '')
        # display_order가 None인 경우도 처리
        display_order_val = kwargs.get('display_order')
        self.display_order = int(display_order_val) if display_order_val is not None else 0
        self.is_pinned = kwargs.get('is_pinned', False)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        self._images = None
    
    def to_doc(self):
        """MongoDB 문서로 변환 (display_order 필드 명시적 포함)"""
        doc = {
            'title': self.title,
            'display_order': int(self.display_order) if self.display_order is not None else 0,
            'is_pinned': bool(self.is_pinned) if self.is_pinned is not None else False,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        if self._id is not None:
            doc['_id'] = self._id
        return doc
    
    def save(self):
        """갤러리 그룹 저장 (display_order 명시적 저장)"""
        collection = self.get_collection()
        doc = self.to_doc()
        
        print(f"🔍 GalleryGroup.save() - id={self._id}, display_order={self.display_order}, doc={doc}")
        
        if self._id is not None:
            # 업데이트 - _id는 제외하고 업데이트
            update_doc = {k: v for k, v in doc.items() if k != '_id'}
            result = collection.update_one({'_id': self._id}, {'$set': update_doc}, upsert=True)
            print(f"📝 GalleryGroup update: matched={result.matched_count}, modified={result.modified_count}, _id={self._id}, display_order={self.display_order}")
            
            # 업데이트 후 확인
            updated_doc = collection.find_one({'_id': self._id})
            print(f"✅ GalleryGroup 저장 후 확인: display_order={updated_doc.get('display_order') if updated_doc else 'NOT FOUND'}")
        else:
            # 새로운 ID 생성
            max_doc = collection.find_one(sort=[('_id', DESCENDING)])
            new_id = (max_doc['_id'] + 1) if max_doc and isinstance(max_doc.get('_id'), int) else 1
            doc['_id'] = new_id
            collection.insert_one(doc)
            self._id = new_id
            self.id = new_id
            print(f"📝 GalleryGroup insert: new_id={new_id}, display_order={self.display_order}")
        
        return self
    
    @property
    def images(self):
        """해당 그룹의 이미지들 조회"""
        if self._images is None:
            self._images = Gallery.query_filter(group_id=self._id)
        return self._images
    
    @classmethod
    def query_all_ordered(cls):
        """정렬된 모든 갤러리 그룹 조회"""
        collection = cls.get_collection()
        docs = list(collection.find().sort([
            ('is_pinned', DESCENDING),
            ('display_order', DESCENDING),
            ('created_at', DESCENDING)
        ]))
        
        # 디버깅: MongoDB에서 조회된 원본 문서 출력
        print(f"🗂️ MongoDB에서 조회된 갤러리 그룹 원본 데이터:")
        for doc in docs:
            print(f"  - _id={doc.get('_id')}, title={doc.get('title')}, display_order={doc.get('display_order')}")
        
        return [cls.from_doc(doc) for doc in docs]
    
    @classmethod
    def query_paginated(cls, page=1, per_page=9):
        """페이지네이션된 갤러리 그룹 조회"""
        collection = cls.get_collection()
        skip = (page - 1) * per_page
        docs = collection.find().sort([
            ('is_pinned', DESCENDING),
            ('display_order', DESCENDING),
            ('created_at', DESCENDING)
        ]).skip(skip).limit(per_page)
        return [cls.from_doc(doc) for doc in docs]


class Gallery(MongoModel):
    """갤러리 이미지 모델"""
    collection_name = 'galleries'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_path = kwargs.get('image_path', '')
        self.caption = kwargs.get('caption')
        self.order = kwargs.get('order', 0)
        self.group_id = kwargs.get('group_id')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self._group = None
    
    @property
    def group(self):
        """상위 그룹 조회"""
        if self._group is None and self.group_id:
            self._group = GalleryGroup.get_by_id(self.group_id)
        return self._group
    
    @classmethod
    def query_by_group(cls, group_id):
        """그룹별 이미지 조회 (순서 정렬)"""
        collection = cls.get_collection()
        docs = collection.find({'group_id': group_id}).sort([('order', ASCENDING), ('_id', ASCENDING)])
        return [cls.from_doc(doc) for doc in docs]


class Booking(MongoModel):
    """예약 모델"""
    collection_name = 'bookings'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.phone = kwargs.get('phone', '')  # 휴대폰 번호 추가
        self.email = kwargs.get('email', '')
        self.service_id = kwargs.get('service_id')
        self.message = kwargs.get('message', '')
        self.status = kwargs.get('status', '대기')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self._service = None
        
        # AI 처리 관련 필드
        self.is_spam = kwargs.get('is_spam', False)  # 스팸 여부
        self.spam_reason = kwargs.get('spam_reason', '')  # 스팸 판단 이유
        self.detected_language = kwargs.get('detected_language', '')  # 감지된 언어
        self.sentiment = kwargs.get('sentiment', '')  # 감성
        self.sentiment_detail = kwargs.get('sentiment_detail', '')  # 감성 상세
        self.ai_response = kwargs.get('ai_response', '')  # AI가 생성한 응답
        self.translated_message = kwargs.get('translated_message', '')  # 번역된 원문
        self.response_sent = kwargs.get('response_sent', False)  # 응답 전송 여부
        self.response_sent_at = kwargs.get('response_sent_at')  # 응답 발송 시간
        self.response_email_subject = kwargs.get('response_email_subject', '')  # 발송된 이메일 제목
        self.admin_notified = kwargs.get('admin_notified', False)  # 관리자 알림 여부
        self.ai_processed = kwargs.get('ai_processed', False)  # AI 처리 완료 여부
        self.ai_processed_at = kwargs.get('ai_processed_at')  # AI 처리 시간
    
    @property
    def service(self):
        """연결된 서비스 조회"""
        if self._service is None and self.service_id:
            try:
                # service_id가 정수형인지 확인하고 변환
                if isinstance(self.service_id, int):
                    service_id_int = self.service_id
                elif isinstance(self.service_id, str) and self.service_id.isdigit():
                    service_id_int = int(self.service_id)
                else:
                    # ObjectId나 기타 형식은 그대로 사용
                    service_id_int = self.service_id
                self._service = Service.get_by_id(service_id_int)
            except Exception as e:
                print(f"⚠️ 예약 서비스 조회 실패 (service_id={self.service_id}, type={type(self.service_id)}): {str(e)}")
                self._service = None
        return self._service
    
    def get_datetimes(self):
        """메시지에서 희망 예약일시 부분 추출"""
        lines = (self.message or '').split('\n')
        datetimes = []
        for line in lines:
            if '순위:' in line:
                datetimes.append(line.strip())
        return datetimes
    
    def get_message_content(self):
        """메시지에서 희망 예약일시를 제외한 내용만 반환"""
        parts = (self.message or '').split('\n\n희망 예약일시:')
        return parts[0] if parts else ''
    
    @classmethod
    def query_all_ordered(cls, limit=None):
        """생성일 기준 내림차순 정렬된 예약 조회"""
        collection = cls.get_collection()
        cursor = collection.find().sort('created_at', DESCENDING)
        if limit:
            cursor = cursor.limit(limit)
        results = []
        for doc in cursor:
            try:
                booking = cls.from_doc(doc)
                if booking:
                    results.append(booking)
            except Exception as e:
                print(f"⚠️ 예약 문서 로드 오류 (건너뜀): _id={doc.get('_id')}, error={str(e)}")
        return results


class Inquiry(MongoModel):
    """문의 모델"""
    collection_name = 'inquiries'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get('name', '')
        self.phone = kwargs.get('phone', '')
        self.email = kwargs.get('email', '')
        self.service_id = kwargs.get('service_id')
        self.message = kwargs.get('message', '')
        self.status = kwargs.get('status', '대기')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self._service = None
        
        # AI 처리 관련 필드
        self.is_spam = kwargs.get('is_spam', False)  # 스팸 여부
        self.spam_reason = kwargs.get('spam_reason', '')  # 스팸 판단 이유
        self.detected_language = kwargs.get('detected_language', '')  # 감지된 언어 (ko, en, ja, zh 등)
        self.sentiment = kwargs.get('sentiment', '')  # 감성 (positive, neutral, negative)
        self.sentiment_detail = kwargs.get('sentiment_detail', '')  # 감성 상세 (formal, casual, urgent 등)
        self.ai_response = kwargs.get('ai_response', '')  # AI가 생성한 응답
        self.translated_message = kwargs.get('translated_message', '')  # 번역된 원문 (한국어로)
        self.response_sent = kwargs.get('response_sent', False)  # 고객에게 응답 전송 여부
        self.response_sent_at = kwargs.get('response_sent_at')  # 응답 발송 시간
        self.response_email_subject = kwargs.get('response_email_subject', '')  # 발송된 이메일 제목
        self.admin_notified = kwargs.get('admin_notified', False)  # 관리자에게 알림 전송 여부
        self.ai_processed = kwargs.get('ai_processed', False)  # AI 처리 완료 여부
        self.ai_processed_at = kwargs.get('ai_processed_at')  # AI 처리 시간
    
    @property
    def service(self):
        """연결된 서비스 조회"""
        if self._service is None and self.service_id:
            try:
                # service_id가 정수형인지 확인하고 변환
                if isinstance(self.service_id, int):
                    service_id_int = self.service_id
                elif isinstance(self.service_id, str) and self.service_id.isdigit():
                    service_id_int = int(self.service_id)
                else:
                    # ObjectId나 기타 형식은 그대로 사용
                    service_id_int = self.service_id
                self._service = Service.get_by_id(service_id_int)
            except Exception as e:
                print(f"⚠️ 문의 서비스 조회 실패 (service_id={self.service_id}, type={type(self.service_id)}): {str(e)}")
                self._service = None
        return self._service
    
    @classmethod
    def query_all_ordered(cls, limit=None):
        """생성일 기준 내림차순 정렬된 문의 조회"""
        collection = cls.get_collection()
        cursor = collection.find().sort('created_at', DESCENDING)
        if limit:
            cursor = cursor.limit(limit)
        results = []
        for doc in cursor:
            try:
                inquiry = cls.from_doc(doc)
                if inquiry:
                    results.append(inquiry)
            except Exception as e:
                print(f"⚠️ 문의 문서 로드 오류 (건너뜀): _id={doc.get('_id')}, error={str(e)}")
        return results
    
    @classmethod
    def query_spam(cls, limit=None):
        """스팸으로 분류된 문의 조회"""
        collection = cls.get_collection()
        cursor = collection.find({'is_spam': True}).sort('created_at', DESCENDING)
        if limit:
            cursor = cursor.limit(limit)
        results = []
        for doc in cursor:
            try:
                inquiry = cls.from_doc(doc)
                if inquiry:
                    results.append(inquiry)
            except Exception as e:
                print(f"⚠️ 스팸 문의 문서 로드 오류 (건너뜀): _id={doc.get('_id')}, error={str(e)}")
        return results
    
    @classmethod
    def query_non_spam(cls, limit=None):
        """정상 문의 조회 (스팸 제외)"""
        collection = cls.get_collection()
        cursor = collection.find({'$or': [{'is_spam': False}, {'is_spam': {'$exists': False}}]}).sort('created_at', DESCENDING)
        if limit:
            cursor = cursor.limit(limit)
        results = []
        for doc in cursor:
            try:
                inquiry = cls.from_doc(doc)
                if inquiry:
                    results.append(inquiry)
            except Exception as e:
                print(f"⚠️ 문의 문서 로드 오류 (건너뜀): _id={doc.get('_id')}, error={str(e)}")
        return results


class CollageText(MongoModel):
    """Fade Text 모델"""
    collection_name = 'collage_texts'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.text = kwargs.get('text', '')
        self.order = kwargs.get('order', 0)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @classmethod
    def query_all_ordered(cls):
        """순서별 정렬된 텍스트 조회"""
        collection = cls.get_collection()
        docs = collection.find().sort('order', ASCENDING)
        return [cls.from_doc(doc) for doc in docs]


class SiteSettings(MongoModel):
    """사이트 설정 모델"""
    collection_name = 'site_settings'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 사이트 모드: 'light' 또는 'dark' (기본값: 'dark')
        self.site_mode = kwargs.get('site_mode', 'dark')
        # Light Mode 색상 설정 (admin의 '사이트 색상 관리' 값)
        # 기본값: Neon Lavender #B57EDC
        self.main_color_r = kwargs.get('main_color_r', 181)
        self.main_color_g = kwargs.get('main_color_g', 126)
        self.main_color_b = kwargs.get('main_color_b', 220)
        # 기본값: Electric Violet #8A2BE2
        self.sub_color_r = kwargs.get('sub_color_r', 138)
        self.sub_color_g = kwargs.get('sub_color_g', 43)
        self.sub_color_b = kwargs.get('sub_color_b', 226)
        # 기본값: White #FFFFFF (라이트 모드용 배경)
        self.background_color_r = kwargs.get('background_color_r', 255)
        self.background_color_g = kwargs.get('background_color_g', 255)
        self.background_color_b = kwargs.get('background_color_b', 255)
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @classmethod
    def get_current_settings(cls):
        """현재 사이트 설정 가져오기"""
        collection = cls.get_collection()
        doc = collection.find_one()
        if doc:
            return cls.from_doc(doc)
        # 기본 설정 생성
        settings = cls()
        settings.save()
        return settings
    
    def get_main_color_rgb(self):
        return f"{self.main_color_r}, {self.main_color_g}, {self.main_color_b}"
    
    def get_sub_color_rgb(self):
        return f"{self.sub_color_r}, {self.sub_color_g}, {self.sub_color_b}"
    
    def get_background_color_rgb(self):
        return f"{self.background_color_r}, {self.background_color_g}, {self.background_color_b}"
    
    def get_main_color_hex(self):
        return f"#{self.main_color_r:02x}{self.main_color_g:02x}{self.main_color_b:02x}"
    
    def get_sub_color_hex(self):
        return f"#{self.sub_color_r:02x}{self.sub_color_g:02x}{self.sub_color_b:02x}"
    
    def get_background_color_hex(self):
        return f"#{self.background_color_r:02x}{self.background_color_g:02x}{self.background_color_b:02x}"


class TermsOfService(MongoModel):
    """이용약관 모델"""
    collection_name = 'terms_of_service'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get('content', '')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @classmethod
    def get_current_content(cls):
        """현재 이용약관 가져오기"""
        collection = cls.get_collection()
        doc = collection.find_one()
        if doc:
            return cls.from_doc(doc)
        # 기본 이용약관 생성
        terms = cls(content='이용약관 내용을 입력해주세요.')
        terms.save()
        return terms


class PrivacyPolicy(MongoModel):
    """개인정보처리방침 모델"""
    collection_name = 'privacy_policy'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.content = kwargs.get('content', '')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @classmethod
    def get_current_content(cls):
        """현재 개인정보처리방침 가져오기"""
        collection = cls.get_collection()
        doc = collection.find_one()
        if doc:
            return cls.from_doc(doc)
        # 기본 개인정보처리방침 생성
        policy = cls(content='개인정보처리방침 내용을 입력해주세요.')
        policy.save()
        return policy


class AdminNotificationEmail(MongoModel):
    """관리자 알림 이메일 모델"""
    collection_name = 'admin_notification_emails'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.email = kwargs.get('email', '')
        self.name = kwargs.get('name', '')  # 담당자 이름 (선택)
        self.is_active = kwargs.get('is_active', True)  # 활성화 상태
        self.receive_inquiries = kwargs.get('receive_inquiries', True)  # 문의 알림 수신
        self.receive_bookings = kwargs.get('receive_bookings', True)  # 예약 알림 수신
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    @classmethod
    def query_all_ordered(cls):
        """모든 알림 이메일 조회 (생성일 기준)"""
        collection = cls.get_collection()
        docs = collection.find().sort('created_at', ASCENDING)
        return [cls.from_doc(doc) for doc in docs]
    
    @classmethod
    def get_active_emails(cls, email_type='all'):
        """활성화된 이메일 목록 가져오기
        
        Args:
            email_type: 'all', 'inquiries', 'bookings'
        """
        collection = cls.get_collection()
        
        if email_type == 'inquiries':
            filter_query = {'is_active': True, 'receive_inquiries': True}
        elif email_type == 'bookings':
            filter_query = {'is_active': True, 'receive_bookings': True}
        else:
            filter_query = {'is_active': True}
        
        docs = collection.find(filter_query)
        return [doc['email'] for doc in docs]
    
    @classmethod
    def get_by_email(cls, email):
        """이메일 주소로 조회"""
        collection = cls.get_collection()
        doc = collection.find_one({'email': email})
        return cls.from_doc(doc) if doc else None
    
    @classmethod
    def initialize_default(cls):
        """기본 이메일 초기화 (없는 경우에만)"""
        collection = cls.get_collection()
        if collection.count_documents({}) == 0:
            default_email = cls(
                email='ysg.stylegrapher@gmail.com',
                name='스타일그래퍼 관리자',
                is_active=True,
                receive_inquiries=True,
                receive_bookings=True
            )
            default_email.save()
            print("📧 기본 알림 이메일 초기화 완료: ysg.stylegrapher@gmail.com")


# 편의 함수들
def get_next_id(collection_name):
    """다음 ID 값 생성 (auto-increment 시뮬레이션)"""
    db = get_mongo_db()
    collection = db[collection_name]
    max_doc = collection.find_one(sort=[('_id', DESCENDING)])
    return (max_doc['_id'] + 1) if max_doc and isinstance(max_doc.get('_id'), int) else 1
