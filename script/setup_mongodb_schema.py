from pymongo import MongoClient
from dotenv import load_dotenv
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()

def setup_gallery_collection():
    try:
        # MongoDB 연결
        mongo_uri = os.environ.get('MONGO_URI')
        if not mongo_uri:
            logger.error("MONGO_URI 환경변수가 설정되지 않았습니다.")
            return False
        
        client = MongoClient(mongo_uri)
        db = client['STG-DB']
        
        # 컬렉션 이름
        collection_name = 'gallery'
        
        # 이미 컬렉션이 존재하면 삭제 (선택적)
        if collection_name in db.list_collection_names():
            logger.info(f"기존 {collection_name} 컬렉션이 존재합니다. 스키마 업데이트를 진행합니다.")
        
        # 스키마 검증 규칙 정의
        validator = {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['_id', 'filename', 'content_type', 'binary_data', 'group_id', 'order', 'created_at'],
                'properties': {
                    '_id': {
                        'bsonType': 'string',
                        'description': '이미지의 고유 UUID'
                    },
                    'filename': {
                        'bsonType': 'string',
                        'description': '원본 파일명'
                    },
                    'content_type': {
                        'bsonType': 'string',
                        'description': '이미지 MIME 타입 (예: image/jpeg)'
                    },
                    'binary_data': {
                        'bsonType': 'binData',
                        'description': '이미지 바이너리 데이터'
                    },
                    'group_id': {
                        'bsonType': ['int', 'double'],
                        'description': '갤러리 그룹 ID'
                    },
                    'order': {
                        'bsonType': ['int', 'double'],
                        'description': '그룹 내 이미지 순서'
                    },
                    'title': {
                        'bsonType': 'string',
                        'description': '이미지 제목'
                    },
                    'metadata': {
                        'bsonType': 'object',
                        'properties': {
                            'width': {
                                'bsonType': ['int', 'double'],
                                'description': '이미지 너비(픽셀)'
                            },
                            'height': {
                                'bsonType': ['int', 'double'],
                                'description': '이미지 높이(픽셀)'
                            },
                            'original_width': {
                                'bsonType': ['int', 'double'],
                                'description': '원본 이미지 너비(픽셀)'
                            },
                            'original_height': {
                                'bsonType': ['int', 'double'],
                                'description': '원본 이미지 높이(픽셀)'
                            },
                            'size_bytes': {
                                'bsonType': ['int', 'double'],
                                'description': '파일 크기(바이트)'
                            }
                        }
                    },
                    'created_at': {
                        'bsonType': 'date',
                        'description': '생성 시간'
                    },
                    'updated_at': {
                        'bsonType': 'date',
                        'description': '최종 수정 시간'
                    },
                    'is_active': {
                        'bsonType': 'bool',
                        'description': '이미지 활성화 상태'
                    }
                }
            }
        }
        
        # 검증 옵션
        validation_options = {
            'validator': validator,
            'validationLevel': 'moderate',  # strict, moderate, off
            'validationAction': 'warn'      # error, warn
        }
        
        # 컬렉션 생성 또는 업데이트
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name, **validation_options)
            logger.info(f"{collection_name} 컬렉션이 생성되었습니다.")
        else:
            db.command('collMod', collection_name, **validation_options)
            logger.info(f"{collection_name} 컬렉션의 유효성 검사 규칙이 업데이트되었습니다.")
        
        # 인덱스 생성
        gallery_collection = db[collection_name]
        gallery_collection.create_index([("group_id", 1), ("order", 1)])
        gallery_collection.create_index("created_at")
        logger.info("인덱스가 생성되었습니다.")
        
        logger.info("MongoDB gallery 컬렉션 설정이 완료되었습니다.")
        return True
        
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
        return False

if __name__ == "__main__":
    success = setup_gallery_collection()
    if success:
        print("MongoDB gallery 컬렉션 스키마 설정이 성공적으로 완료되었습니다.")
    else:
        print("MongoDB gallery 컬렉션 스키마 설정 중 오류가 발생했습니다.")