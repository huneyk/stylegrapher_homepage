#!/usr/bin/env python3
"""
기존 MongoDB binary_data 이미지를 GridFS로 마이그레이션하는 스크립트

사용법:
    python migrate_to_gridfs.py [옵션]

옵션:
    --dry-run       실제로 마이그레이션하지 않고 예상 결과만 출력
    --batch-size N  한 번에 처리할 문서 수 (기본: 50)
    --stats         현재 저장소 통계만 출력

예시:
    python migrate_to_gridfs.py --dry-run      # 테스트 실행
    python migrate_to_gridfs.py                # 실제 마이그레이션
    python migrate_to_gridfs.py --stats        # 통계 확인
"""

import sys
import argparse
from datetime import datetime

# 프로젝트 경로 설정
sys.path.insert(0, '.')

from utils.gridfs_helper import (
    get_mongo_connection,
    migrate_legacy_to_gridfs,
    get_gridfs_stats
)


def print_stats():
    """저장소 통계 출력"""
    stats = get_gridfs_stats()
    
    print("\n" + "=" * 60)
    print("📊 저장소 통계")
    print("=" * 60)
    
    if 'error' in stats:
        print(f"❌ 오류: {stats['error']}")
        return
    
    print(f"GridFS 파일 수: {stats['gridfs_files_count']:,}개")
    
    total_size_mb = stats['gridfs_total_size'] / (1024 * 1024)
    print(f"GridFS 총 크기: {total_size_mb:.2f} MB")
    
    print(f"레거시 문서 수: {stats['legacy_count']:,}개")
    print(f"마이그레이션 필요: {stats['legacy_with_binary']:,}개 (binary_data 있는 문서)")
    print("=" * 60 + "\n")


def dry_run_migration():
    """마이그레이션 시뮬레이션"""
    gridfs, db, legacy_collection = get_mongo_connection()
    
    if gridfs is None or legacy_collection is None:
        print("❌ MongoDB 연결 실패")
        return
    
    print("\n" + "=" * 60)
    print("🔍 마이그레이션 시뮬레이션 (Dry Run)")
    print("=" * 60)
    
    # 마이그레이션 대상 문서 수 확인
    to_migrate = legacy_collection.count_documents({'binary_data': {'$exists': True}})
    print(f"마이그레이션 대상: {to_migrate:,}개 문서")
    
    # 이미 GridFS에 있는 문서 확인
    already_in_gridfs = 0
    sample_docs = legacy_collection.find(
        {'binary_data': {'$exists': True}},
        {'_id': 1}
    ).limit(100)
    
    for doc in sample_docs:
        if gridfs.exists(doc['_id']):
            already_in_gridfs += 1
    
    print(f"이미 GridFS에 존재: 최소 {already_in_gridfs}개 (샘플 100개 중)")
    print(f"예상 마이그레이션 수: 약 {max(0, to_migrate - already_in_gridfs):,}개")
    
    # 용량 예측
    pipeline = [
        {'$match': {'binary_data': {'$exists': True}}},
        {'$project': {'size': {'$bsonSize': '$binary_data'}}},
        {'$group': {'_id': None, 'total': {'$sum': '$size'}}}
    ]
    result = list(legacy_collection.aggregate(pipeline))
    if result:
        estimated_size_mb = result[0]['total'] / (1024 * 1024)
        print(f"예상 용량: 약 {estimated_size_mb:.2f} MB")
    
    print("=" * 60)
    print("💡 실제 마이그레이션을 실행하려면 --dry-run 옵션 없이 실행하세요.")
    print("=" * 60 + "\n")


def run_migration(batch_size=50):
    """실제 마이그레이션 실행"""
    print("\n" + "=" * 60)
    print("🚀 GridFS 마이그레이션 시작")
    print(f"   배치 크기: {batch_size}")
    print(f"   시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 마이그레이션 전 통계
    print("\n[마이그레이션 전 통계]")
    print_stats()
    
    # 마이그레이션 실행
    success, fail, skip = migrate_legacy_to_gridfs(batch_size=batch_size)
    
    # 결과 출력
    print("\n" + "=" * 60)
    print("📋 마이그레이션 결과")
    print("=" * 60)
    print(f"✅ 성공: {success:,}개")
    print(f"❌ 실패: {fail:,}개")
    print(f"⏭️ 건너뜀: {skip:,}개 (이미 GridFS에 존재)")
    print(f"   완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 마이그레이션 후 통계
    print("\n[마이그레이션 후 통계]")
    print_stats()
    
    if fail > 0:
        print("⚠️ 일부 문서 마이그레이션에 실패했습니다. 로그를 확인하세요.")
    else:
        print("✅ 마이그레이션이 성공적으로 완료되었습니다!")


def main():
    parser = argparse.ArgumentParser(
        description='MongoDB binary_data를 GridFS로 마이그레이션',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제로 마이그레이션하지 않고 예상 결과만 출력'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='한 번에 처리할 문서 수 (기본: 50)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='현재 저장소 통계만 출력'
    )
    
    args = parser.parse_args()
    
    # MongoDB 연결 확인
    gridfs, db, _ = get_mongo_connection()
    if gridfs is None:
        print("❌ MongoDB 연결에 실패했습니다.")
        print("   MONGO_URI 환경 변수를 확인하세요.")
        sys.exit(1)
    
    print(f"✅ MongoDB 연결 성공: {db.name}")
    
    if args.stats:
        print_stats()
    elif args.dry_run:
        dry_run_migration()
    else:
        # 확인 메시지
        print("\n⚠️ 주의: 이 작업은 기존 이미지 데이터를 GridFS로 마이그레이션합니다.")
        print("   데이터베이스 백업을 권장합니다.")
        
        confirm = input("\n계속하시겠습니까? (yes/no): ")
        if confirm.lower() != 'yes':
            print("마이그레이션이 취소되었습니다.")
            sys.exit(0)
        
        run_migration(batch_size=args.batch_size)


if __name__ == '__main__':
    main()

