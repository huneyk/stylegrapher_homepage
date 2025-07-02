#!/usr/bin/env python3
"""
관리자 계정 생성 스크립트

이 스크립트는 기존 데이터를 보호하면서 안전하게 관리자 계정만 생성합니다.
- 기존 관리자가 있는지 먼저 확인
- 없을 때만 새로 생성
- 기존 데이터는 절대 덮어쓰지 않음
"""

import os
import sys
import getpass
from flask import Flask
from extensions import db
from models import User
from config import Config

def create_admin_account():
    """관리자 계정을 안전하게 생성"""
    
    # Flask 앱 초기화
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 데이터베이스 초기화
    db.init_app(app)
    
    with app.app_context():
        try:
            # 기존 관리자 계정 확인
            existing_admin = User.query.filter_by(is_admin=True).first()
            
            if existing_admin:
                print(f"✅ 기존 관리자 계정이 이미 존재합니다: {existing_admin.username}")
                print("새로운 관리자를 추가하시겠습니까? (y/N): ", end="")
                response = input().lower().strip()
                
                if response not in ['y', 'yes', 'ㅇ']:
                    print("❌ 관리자 생성이 취소되었습니다.")
                    return False
            
            print("\n🔐 새로운 관리자 계정 정보를 입력하세요:")
            
            # 사용자명 입력
            while True:
                username = input("관리자 사용자명: ").strip()
                if not username:
                    print("❌ 사용자명을 입력해주세요.")
                    continue
                
                # 중복 확인
                existing_user = User.query.filter_by(username=username).first()
                if existing_user:
                    print(f"❌ '{username}' 사용자명이 이미 존재합니다. 다른 사용자명을 선택해주세요.")
                    continue
                
                break
            
            # 이메일 입력 (선택사항)
            email = input("관리자 이메일 (선택사항): ").strip()
            if email:
                # 중복 확인
                existing_email = User.query.filter_by(email=email).first()
                if existing_email:
                    print(f"❌ '{email}' 이메일이 이미 존재합니다. 다른 이메일을 선택해주세요.")
                    email = None
            else:
                email = None
            
            # 비밀번호 입력
            while True:
                password = getpass.getpass("관리자 비밀번호: ")
                if len(password) < 6:
                    print("❌ 비밀번호는 최소 6자 이상이어야 합니다.")
                    continue
                
                password_confirm = getpass.getpass("비밀번호 확인: ")
                if password != password_confirm:
                    print("❌ 비밀번호가 일치하지 않습니다.")
                    continue
                
                break
            
            # 관리자 계정 생성
            admin = User(
                username=username,
                email=email,
                is_admin=True
            )
            admin.set_password(password)
            
            # 데이터베이스에 저장
            db.session.add(admin)
            db.session.commit()
            
            print(f"\n✅ 관리자 계정이 성공적으로 생성되었습니다!")
            print(f"   사용자명: {username}")
            print(f"   이메일: {email if email else '(없음)'}")
            print(f"   관리자 권한: 활성화")
            print(f"\n🌐 관리자 로그인 URL: http://localhost:5001/admin/login")
            
            return True
            
        except Exception as e:
            print(f"❌ 관리자 계정 생성 중 오류가 발생했습니다: {str(e)}")
            db.session.rollback()
            return False

def main():
    """메인 함수"""
    print("=" * 60)
    print("🛡️  스타일그래퍼 관리자 계정 생성 도구")
    print("=" * 60)
    print("이 스크립트는 기존 데이터를 보호하면서 관리자 계정만 생성합니다.")
    print("기존 데이터는 절대 덮어쓰거나 삭제하지 않습니다.")
    print("-" * 60)
    
    try:
        success = create_admin_account()
        
        if success:
            print("\n🎉 관리자 계정 생성이 완료되었습니다!")
            print("\n📝 다음 단계:")
            print("1. Flask 앱 실행: python app.py")
            print("2. 브라우저에서 http://localhost:5001/admin/login 접속")
            print("3. 생성한 관리자 계정으로 로그인")
        else:
            print("\n❌ 관리자 계정 생성이 실패했습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n❌ 사용자에 의해 취소되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 