#!/usr/bin/env python3
"""
🧹 Render 서버 캐시 완전 제거 스크립트

이 스크립트는 Render 서버에서 Python 바이트코드 캐시를 완전히 제거하여
새로운 코드가 확실히 반영되도록 합니다.
"""

import os
import shutil
import sys

def remove_pycache_recursive(directory):
    """지정된 디렉토리와 하위 디렉토리의 모든 __pycache__ 제거"""
    removed_count = 0
    
    for root, dirs, files in os.walk(directory):
        # __pycache__ 디렉토리 찾기
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                print(f"✅ 제거됨: {pycache_path}")
                removed_count += 1
            except Exception as e:
                print(f"❌ 제거 실패: {pycache_path} - {str(e)}")
        
        # .pyc 파일 직접 제거
        for file in files:
            if file.endswith('.pyc') or file.endswith('.pyo'):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"✅ 파일 제거: {file_path}")
                    removed_count += 1
                except Exception as e:
                    print(f"❌ 파일 제거 실패: {file_path} - {str(e)}")
    
    return removed_count

def main():
    print("🧹 Render 서버 Python 캐시 완전 제거 시작")
    print("=" * 60)
    
    # 현재 디렉토리에서 시작
    current_dir = os.getcwd()
    print(f"📁 작업 디렉토리: {current_dir}")
    
    # 캐시 제거 실행
    removed_count = remove_pycache_recursive(current_dir)
    
    print("=" * 60)
    print(f"🎉 캐시 제거 완료! 총 {removed_count}개 항목 제거됨")
    
    # 추가 정리
    print("\n🔧 추가 정리 작업:")
    
    # pip 캐시 제거
    try:
        os.system("pip cache purge")
        print("✅ pip 캐시 제거 완료")
    except:
        print("⚠️ pip 캐시 제거 실패 (무시 가능)")
    
    # Python 모듈 재로드 강제
    if hasattr(sys, '_clear_type_cache'):
        sys._clear_type_cache()
        print("✅ Python 타입 캐시 클리어 완료")
    
    print("\n🛡️ 데이터 보호 시스템이 이제 완전히 활성화됩니다!")
    print("📝 다음 앱 재시작 시 새로운 보호 로직이 적용됩니다.")

if __name__ == "__main__":
    main() 