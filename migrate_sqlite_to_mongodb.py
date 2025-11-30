#!/usr/bin/env python3
"""
SQLite에서 MongoDB로 모든 데이터를 마이그레이션하는 스크립트

사용법:
    python migrate_sqlite_to_mongodb.py

주의사항:
    - 마이그레이션 전에 MongoDB 백업을 권장합니다
    - 이 스크립트는 기존 MongoDB 데이터를 덮어쓰지 않고, 없는 데이터만 추가합니다
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Flask 앱 컨텍스트 설정
from app import create_app
from extensions import db
from sqlalchemy import text
from utils.mongo_models import (
    get_mongo_db, init_collections,
    User, Service, ServiceOption, GalleryGroup, Gallery,
    Booking, Inquiry, CollageText, SiteSettings,
    TermsOfService, PrivacyPolicy
)

app = create_app()


def migrate_users():
    """사용자 마이그레이션"""
    print("\n📦 사용자 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['users']
    
    with app.app_context():
        result = db.session.execute(text("SELECT id, uq_user_username, email, password_hash, is_admin FROM user"))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            user_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': user_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': user_id,
                'username': row[1],
                'email': row[2],
                'password_hash': row[3],
                'is_admin': bool(row[4]) if row[4] is not None else False
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 사용자: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_services():
    """서비스 마이그레이션"""
    print("\n📦 서비스 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['services']
    
    with app.app_context():
        result = db.session.execute(text("SELECT id, name, description, category, details, packages FROM service"))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            service_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': service_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': service_id,
                'name': row[1],
                'description': row[2],
                'category': row[3],
                'details': row[4],
                'packages': row[5]
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 서비스: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_service_options():
    """서비스 옵션 마이그레이션"""
    print("\n📦 서비스 옵션 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['service_options']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, service_id, name, description, detailed_description,
                   details, packages, booking_method, payment_info, guide_info,
                   refund_policy, refund_policy_text, refund_policy_table, overtime_charge_table
            FROM service_option
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            option_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': option_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': option_id,
                'service_id': row[1],
                'name': row[2],
                'description': row[3],
                'detailed_description': row[4],
                'details': row[5],
                'packages': row[6],
                'booking_method': row[7],
                'payment_info': row[8],
                'guide_info': row[9],
                'refund_policy': row[10],
                'refund_policy_text': row[11],
                'refund_policy_table': row[12],
                'overtime_charge_table': row[13]
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 서비스 옵션: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_gallery_groups():
    """갤러리 그룹 마이그레이션"""
    print("\n📦 갤러리 그룹 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['gallery_groups']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, title, display_order, is_pinned, created_at, updated_at
            FROM gallery_group
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            group_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': group_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': group_id,
                'title': row[1],
                'display_order': row[2] if row[2] is not None else 0,
                'is_pinned': bool(row[3]) if row[3] is not None else False,
                'created_at': row[4] if row[4] else datetime.utcnow(),
                'updated_at': row[5] if row[5] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 갤러리 그룹: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_galleries():
    """갤러리 이미지 마이그레이션"""
    print("\n📦 갤러리 이미지 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['galleries']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, image_path, caption, "order", group_id, created_at
            FROM gallery
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            gallery_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': gallery_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': gallery_id,
                'image_path': row[1],
                'caption': row[2],
                'order': row[3] if row[3] is not None else 0,
                'group_id': row[4],
                'created_at': row[5] if row[5] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 갤러리 이미지: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_bookings():
    """예약 마이그레이션"""
    print("\n📦 예약 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['bookings']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, name, email, service_id, message, status, created_at
            FROM booking
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            booking_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': booking_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': booking_id,
                'name': row[1],
                'email': row[2],
                'service_id': row[3],
                'message': row[4],
                'status': row[5] if row[5] else '대기',
                'created_at': row[6] if row[6] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 예약: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_inquiries():
    """문의 마이그레이션"""
    print("\n📦 문의 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['inquiries']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, name, phone, email, service_id, message, status, created_at
            FROM inquiry
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            inquiry_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': inquiry_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': inquiry_id,
                'name': row[1],
                'phone': row[2],
                'email': row[3],
                'service_id': row[4],
                'message': row[5],
                'status': row[6] if row[6] else '대기',
                'created_at': row[7] if row[7] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 문의: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_collage_texts():
    """Fade Text 마이그레이션"""
    print("\n📦 Fade Text 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['collage_texts']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, text, "order", created_at, updated_at
            FROM collage_text
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            text_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': text_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': text_id,
                'text': row[1],
                'order': row[2] if row[2] is not None else 0,
                'created_at': row[3] if row[3] else datetime.utcnow(),
                'updated_at': row[4] if row[4] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ Fade Text: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_site_settings():
    """사이트 설정 마이그레이션"""
    print("\n📦 사이트 설정 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['site_settings']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, main_color_r, main_color_g, main_color_b,
                   sub_color_r, sub_color_g, sub_color_b,
                   background_color_r, background_color_g, background_color_b,
                   created_at, updated_at
            FROM site_settings
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            settings_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': settings_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': settings_id,
                'main_color_r': row[1] if row[1] is not None else 181,
                'main_color_g': row[2] if row[2] is not None else 126,
                'main_color_b': row[3] if row[3] is not None else 220,
                'sub_color_r': row[4] if row[4] is not None else 138,
                'sub_color_g': row[5] if row[5] is not None else 43,
                'sub_color_b': row[6] if row[6] is not None else 226,
                'background_color_r': row[7] if row[7] is not None else 18,
                'background_color_g': row[8] if row[8] is not None else 0,
                'background_color_b': row[9] if row[9] is not None else 36,
                'created_at': row[10] if row[10] else datetime.utcnow(),
                'updated_at': row[11] if row[11] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 사이트 설정: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_terms_of_service():
    """이용약관 마이그레이션"""
    print("\n📦 이용약관 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['terms_of_service']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, content, created_at, updated_at
            FROM terms_of_service
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            terms_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': terms_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': terms_id,
                'content': row[1],
                'created_at': row[2] if row[2] else datetime.utcnow(),
                'updated_at': row[3] if row[3] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 이용약관: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def migrate_privacy_policy():
    """개인정보처리방침 마이그레이션"""
    print("\n📦 개인정보처리방침 마이그레이션 중...")
    
    mongo_db = get_mongo_db()
    collection = mongo_db['privacy_policy']
    
    with app.app_context():
        result = db.session.execute(text("""
            SELECT id, content, created_at, updated_at
            FROM privacy_policy
        """))
        rows = result.fetchall()
        
        migrated = 0
        skipped = 0
        
        for row in rows:
            policy_id = row[0]
            
            # 이미 존재하는지 확인
            if collection.find_one({'_id': policy_id}):
                skipped += 1
                continue
            
            doc = {
                '_id': policy_id,
                'content': row[1],
                'created_at': row[2] if row[2] else datetime.utcnow(),
                'updated_at': row[3] if row[3] else datetime.utcnow()
            }
            collection.insert_one(doc)
            migrated += 1
        
        print(f"   ✅ 개인정보처리방침: {migrated}개 마이그레이션, {skipped}개 건너뜀")
        return migrated, skipped


def run_migration():
    """전체 마이그레이션 실행"""
    print("=" * 60)
    print("🚀 SQLite → MongoDB 데이터 마이그레이션 시작")
    print("=" * 60)
    
    # MongoDB 컬렉션 초기화
    print("\n📁 MongoDB 컬렉션 초기화 중...")
    init_collections()
    
    # 각 테이블 마이그레이션
    total_migrated = 0
    total_skipped = 0
    
    results = []
    
    try:
        results.append(('사용자', migrate_users()))
        results.append(('서비스', migrate_services()))
        results.append(('서비스 옵션', migrate_service_options()))
        results.append(('갤러리 그룹', migrate_gallery_groups()))
        results.append(('갤러리 이미지', migrate_galleries()))
        results.append(('예약', migrate_bookings()))
        results.append(('문의', migrate_inquiries()))
        results.append(('Fade Text', migrate_collage_texts()))
        results.append(('사이트 설정', migrate_site_settings()))
        results.append(('이용약관', migrate_terms_of_service()))
        results.append(('개인정보처리방침', migrate_privacy_policy()))
    except Exception as e:
        print(f"\n❌ 마이그레이션 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 마이그레이션 결과 요약")
    print("=" * 60)
    
    for name, (migrated, skipped) in results:
        total_migrated += migrated
        total_skipped += skipped
        status = "✅" if migrated > 0 else "⏭️"
        print(f"   {status} {name}: {migrated}개 마이그레이션, {skipped}개 건너뜀")
    
    print("-" * 60)
    print(f"   📦 총계: {total_migrated}개 마이그레이션, {total_skipped}개 건너뜀")
    print("=" * 60)
    
    if total_migrated > 0:
        print("\n✅ 마이그레이션이 성공적으로 완료되었습니다!")
        print("   이제 MongoDB에서 모든 데이터를 사용할 수 있습니다.")
    else:
        print("\n⏭️ 마이그레이션할 새 데이터가 없습니다.")
        print("   모든 데이터가 이미 MongoDB에 존재합니다.")
    
    return True


if __name__ == '__main__':
    run_migration()
