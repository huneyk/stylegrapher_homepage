"""
GridFS 헬퍼 모듈 - MongoDB GridFS를 사용한 이미지 저장 및 조회
"""
import os
import io
import uuid
from datetime import datetime
from PIL import Image
from gridfs import GridFS
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# .env 파일 로드
load_dotenv()

# 전역 변수
_gridfs_instance = None
_mongo_db = None
_images_collection = None  # 기존 호환성을 위한 컬렉션


def get_mongo_connection():
    """MongoDB 연결 및 GridFS 인스턴스 반환"""
    global _gridfs_instance, _mongo_db, _images_collection
    
    if _gridfs_instance is not None:
        return _gridfs_instance, _mongo_db, _images_collection
    
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        print("GridFS: MONGO_URI 환경 변수가 설정되지 않았습니다!")
        return None, None, None
    
    try:
        print(f"GridFS: MongoDB에 연결 시도...")
        mongo_client = MongoClient(
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
        mongo_client.server_info()
        print("GridFS: MongoDB 연결 성공!")
        
        # 데이터베이스 선택
        db_name = 'STG-DB' if 'mongodb.net' in mongo_uri else 'stylegrapher_db'
        _mongo_db = mongo_client[db_name]
        
        # GridFS 인스턴스 생성 (gallery 컬렉션 사용)
        _gridfs_instance = GridFS(_mongo_db, collection='gallery_images')
        
        # 기존 호환성을 위한 컬렉션 (마이그레이션용)
        _images_collection = _mongo_db['gallery']
        
        print(f"GridFS: 데이터베이스 '{db_name}'에서 GridFS 'gallery_images' 사용 준비 완료")
        return _gridfs_instance, _mongo_db, _images_collection
        
    except Exception as e:
        print(f"GridFS: MongoDB 연결 오류: {str(e)}")
        return None, None, None


# 웹 최적화 설정
WEB_IMAGE_CONFIG = {
    'max_width': 800,           # 최대 너비 (px) - 웹 갤러리에 충분
    'max_height': 1200,         # 최대 높이 (px) - 세로 이미지 제한
    'jpeg_quality': 82,         # JPEG 품질 (80-85가 웹에 최적)
    'png_compression': 6,       # PNG 압축 레벨 (0-9)
    'progressive_jpeg': True,   # Progressive JPEG 사용 (빠른 로딩)
}


def resize_image_for_storage(img, max_width=None, max_height=None):
    """
    이미지를 웹 표출에 최적화된 크기로 리사이즈
    
    Args:
        img: PIL Image 객체
        max_width: 최대 너비 (픽셀), None이면 설정값 사용
        max_height: 최대 높이 (픽셀), None이면 설정값 사용
    
    Returns:
        리사이즈된 PIL Image 객체
    """
    max_width = max_width or WEB_IMAGE_CONFIG['max_width']
    max_height = max_height or WEB_IMAGE_CONFIG['max_height']
    
    original_width, original_height = img.size
    
    # 이미 작은 이미지는 리사이즈하지 않음
    if original_width <= max_width and original_height <= max_height:
        return img
    
    # 가로/세로 비율 계산하여 더 작은 비율 적용
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    ratio = min(width_ratio, height_ratio)
    
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)
    
    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return resized_img


def save_image_to_gridfs(file, group_id=None, order=0, custom_id=None):
    """
    이미지를 GridFS에 저장 (웹 최적화 적용)
    
    Args:
        file: 업로드된 파일 객체
        group_id: 갤러리 그룹 ID
        order: 그룹 내 순서
        custom_id: 커스텀 ID (지정하지 않으면 자동 생성)
    
    Returns:
        저장된 이미지의 ID (문자열)
    
    웹 최적화 설정:
        - 최대 크기: {max_width}x{max_height}px
        - JPEG 품질: {jpeg_quality}%
        - Progressive JPEG 사용
    """.format(**WEB_IMAGE_CONFIG)
    
    gridfs, db, _ = get_mongo_connection()
    
    if gridfs is None:
        raise Exception("GridFS 연결이 설정되지 않았습니다.")
    
    filename = secure_filename(file.filename)
    
    # 이미지 데이터 읽기
    img_data = file.read()
    original_size = len(img_data)
    
    # 이미지 리사이즈 (웹 최적화)
    img = Image.open(io.BytesIO(img_data))
    original_format = img.format or 'JPEG'
    original_dimensions = img.size
    resized_img = resize_image_for_storage(img)
    
    # 이미지를 바이트로 변환 (최적화 압축 적용)
    buffer = io.BytesIO()
    
    # PNG인 경우 투명도 유지하되 압축 최적화
    if original_format.upper() == 'PNG':
        # PNG는 투명도가 필요한 경우만 유지, 아니면 JPEG로 변환
        if resized_img.mode == 'RGBA' and resized_img.split()[3].getextrema()[0] < 255:
            # 실제 투명도가 있는 경우 PNG 유지
            resized_img.save(
                buffer, 
                format='PNG', 
                optimize=True,
                compress_level=WEB_IMAGE_CONFIG['png_compression']
            )
            content_type = 'image/png'
        else:
            # 투명도가 없으면 JPEG로 변환 (용량 절약)
            if resized_img.mode in ('RGBA', 'P'):
                resized_img = resized_img.convert('RGB')
            resized_img.save(
                buffer, 
                format='JPEG', 
                quality=WEB_IMAGE_CONFIG['jpeg_quality'],
                optimize=True,
                progressive=WEB_IMAGE_CONFIG['progressive_jpeg']
            )
            content_type = 'image/jpeg'
    elif original_format.upper() == 'GIF':
        resized_img.save(buffer, format='GIF', optimize=True)
        content_type = 'image/gif'
    else:
        # JPEG 최적화 저장
        if resized_img.mode in ('RGBA', 'P'):
            resized_img = resized_img.convert('RGB')
        resized_img.save(
            buffer, 
            format='JPEG', 
            quality=WEB_IMAGE_CONFIG['jpeg_quality'],
            optimize=True,
            progressive=WEB_IMAGE_CONFIG['progressive_jpeg']
        )
        content_type = 'image/jpeg'
    
    buffer.seek(0)
    img_binary = buffer.getvalue()
    compressed_size = len(img_binary)
    
    # 압축 결과 로깅
    compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    print(f"GridFS: 이미지 최적화 - 원본: {original_dimensions[0]}x{original_dimensions[1]} ({original_size/1024:.1f}KB) → "
          f"최적화: {resized_img.size[0]}x{resized_img.size[1]} ({compressed_size/1024:.1f}KB) "
          f"[{compression_ratio:.1f}% 절약]")
    
    # 고유 ID 생성
    image_id = custom_id or str(uuid.uuid4())
    
    # 메타데이터 설정
    metadata = {
        'original_filename': filename,
        'content_type': content_type,
        'created_at': datetime.now(),
        'width': resized_img.size[0],
        'height': resized_img.size[1],
        'storage_type': 'gridfs'
    }
    
    if group_id is not None:
        metadata['group_id'] = group_id
        metadata['order'] = order
    
    # GridFS에 저장
    gridfs.put(
        img_binary,
        _id=image_id,
        filename=filename,
        content_type=content_type,
        metadata=metadata
    )
    
    print(f"GridFS: 이미지 저장 완료 - ID: {image_id}, 크기: {len(img_binary)} bytes")
    return image_id


def get_image_from_gridfs(image_id):
    """
    GridFS에서 이미지 조회
    
    Args:
        image_id: 이미지 ID
    
    Returns:
        (binary_data, content_type) 튜플 또는 (None, None)
    """
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None:
        return None, None
    
    try:
        # 1. 먼저 GridFS에서 조회 시도
        if gridfs.exists(image_id):
            grid_out = gridfs.get(image_id)
            binary_data = grid_out.read()
            content_type = grid_out.content_type or 'image/jpeg'
            print(f"GridFS: 이미지 조회 성공 - ID: {image_id}, 크기: {len(binary_data)} bytes")
            return binary_data, content_type
        
        # 2. GridFS에 없으면 기존 컬렉션에서 조회 (마이그레이션 전 데이터)
        if legacy_collection is not None:
            legacy_doc = legacy_collection.find_one({'_id': image_id})
            if legacy_doc and 'binary_data' in legacy_doc:
                print(f"GridFS: 레거시 컬렉션에서 이미지 발견 - ID: {image_id}")
                return legacy_doc['binary_data'], legacy_doc.get('content_type', 'image/jpeg')
        
        print(f"GridFS: 이미지를 찾을 수 없음 - ID: {image_id}")
        return None, None
        
    except Exception as e:
        print(f"GridFS: 이미지 조회 오류 - ID: {image_id}, 에러: {str(e)}")
        return None, None


def delete_image_from_gridfs(image_id):
    """
    GridFS에서 이미지 삭제
    
    Args:
        image_id: 이미지 ID
    
    Returns:
        삭제 성공 여부 (bool)
    """
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None:
        return False
    
    try:
        # GridFS에서 삭제
        if gridfs.exists(image_id):
            gridfs.delete(image_id)
            print(f"GridFS: 이미지 삭제 완료 - ID: {image_id}")
            return True
        
        # 레거시 컬렉션에서도 삭제 시도
        if legacy_collection is not None:
            result = legacy_collection.delete_one({'_id': image_id})
            if result.deleted_count > 0:
                print(f"GridFS: 레거시 컬렉션에서 이미지 삭제 완료 - ID: {image_id}")
                return True
        
        print(f"GridFS: 삭제할 이미지가 없음 - ID: {image_id}")
        return False
        
    except Exception as e:
        print(f"GridFS: 이미지 삭제 오류 - ID: {image_id}, 에러: {str(e)}")
        return False


def check_image_exists(image_id):
    """
    이미지 존재 여부 확인
    
    Args:
        image_id: 이미지 ID
    
    Returns:
        존재 여부 (bool)
    """
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None:
        return False
    
    # GridFS 확인
    if gridfs.exists(image_id):
        return True
    
    # 레거시 컬렉션 확인
    if legacy_collection is not None:
        if legacy_collection.find_one({'_id': image_id}, {'_id': 1}):
            return True
    
    return False


def migrate_legacy_to_gridfs(batch_size=50):
    """
    기존 gallery 컬렉션의 binary_data를 GridFS로 마이그레이션
    
    Args:
        batch_size: 한 번에 처리할 문서 수
    
    Returns:
        (성공 수, 실패 수, 건너뛴 수) 튜플
    """
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None or legacy_collection is None:
        print("GridFS 마이그레이션: MongoDB 연결이 설정되지 않았습니다.")
        return 0, 0, 0
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    try:
        # binary_data가 있는 문서만 조회
        cursor = legacy_collection.find(
            {'binary_data': {'$exists': True}},
            no_cursor_timeout=True
        ).batch_size(batch_size)
        
        for doc in cursor:
            image_id = doc['_id']
            
            # 이미 GridFS에 있는지 확인
            if gridfs.exists(image_id):
                skip_count += 1
                print(f"GridFS 마이그레이션: 건너뜀 (이미 존재) - ID: {image_id}")
                continue
            
            try:
                # 메타데이터 추출
                metadata = {
                    'original_filename': doc.get('filename', 'unknown'),
                    'content_type': doc.get('content_type', 'image/jpeg'),
                    'created_at': doc.get('created_at', datetime.now()),
                    'storage_type': 'gridfs',
                    'migrated_from': 'legacy_binary_data'
                }
                
                if 'group_id' in doc:
                    metadata['group_id'] = doc['group_id']
                if 'order' in doc:
                    metadata['order'] = doc['order']
                
                # GridFS에 저장
                gridfs.put(
                    doc['binary_data'],
                    _id=image_id,
                    filename=doc.get('filename', 'unknown'),
                    content_type=doc.get('content_type', 'image/jpeg'),
                    metadata=metadata
                )
                
                # 성공 시 기존 문서에서 binary_data 제거 (선택적)
                # legacy_collection.update_one(
                #     {'_id': image_id},
                #     {'$unset': {'binary_data': ''}}
                # )
                
                success_count += 1
                print(f"GridFS 마이그레이션: 성공 - ID: {image_id}")
                
            except Exception as e:
                fail_count += 1
                print(f"GridFS 마이그레이션: 실패 - ID: {image_id}, 에러: {str(e)}")
        
        cursor.close()
        
    except Exception as e:
        print(f"GridFS 마이그레이션 오류: {str(e)}")
    
    print(f"GridFS 마이그레이션 완료: 성공 {success_count}, 실패 {fail_count}, 건너뜀 {skip_count}")
    return success_count, fail_count, skip_count


def get_gridfs_stats():
    """
    GridFS 저장소 통계 조회
    
    Returns:
        통계 딕셔너리
    """
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None:
        return {'error': 'MongoDB 연결이 설정되지 않았습니다.'}
    
    stats = {
        'gridfs_files_count': 0,
        'gridfs_total_size': 0,
        'legacy_count': 0,
        'legacy_with_binary': 0
    }
    
    try:
        # GridFS 파일 수
        fs_files = db['gallery_images.files']
        stats['gridfs_files_count'] = fs_files.count_documents({})
        
        # GridFS 총 크기 계산
        pipeline = [{'$group': {'_id': None, 'total': {'$sum': '$length'}}}]
        result = list(fs_files.aggregate(pipeline))
        if result:
            stats['gridfs_total_size'] = result[0]['total']
        
        # 레거시 컬렉션 통계
        if legacy_collection is not None:
            stats['legacy_count'] = legacy_collection.count_documents({})
            stats['legacy_with_binary'] = legacy_collection.count_documents(
                {'binary_data': {'$exists': True}}
            )
        
    except Exception as e:
        stats['error'] = str(e)
    
    return stats

