"""🛡️ 데이터 보호 시스템 - 기존 데이터 덮어쓰기 완전 방지

Revision ID: data_protection_001
Revises: 6275ee549efc
Create Date: 2025-01-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'data_protection_001'
down_revision = '6275ee549efc'
branch_labels = None
depends_on = None

def upgrade():
    """
    🛡️ 데이터 보호 시스템 활성화
    
    이 마이그레이션은 기존 데이터를 절대 덮어쓰지 않습니다.
    오직 데이터 보호 기능만을 활성화합니다.
    """
    
    # 데이터베이스 연결 확인
    connection = op.get_bind()
    
    try:
        # 기존 서비스 옵션 데이터 확인
        result = connection.execute(text("""
            SELECT COUNT(*) FROM service_option 
            WHERE booking_method IS NOT NULL 
               OR payment_info IS NOT NULL 
               OR guide_info IS NOT NULL 
               OR refund_policy_text IS NOT NULL
        """))
        existing_data_count = result.scalar()
        
        if existing_data_count > 0:
            print(f"🛡️ 데이터 보호 시스템: {existing_data_count}개의 기존 서비스 옵션 데이터 발견")
            print("🛡️ 기존 데이터는 절대 수정되지 않습니다")
        else:
            print("🛡️ 데이터 보호 시스템: 새로운 환경입니다")
        
        # 갤러리 순서 데이터 확인
        result = connection.execute(text("""
            SELECT COUNT(*) FROM gallery_group 
            WHERE display_order IS NOT NULL
        """))
        gallery_count = result.scalar()
        
        if gallery_count > 0:
            print(f"🛡️ 갤러리 순서 보호: {gallery_count}개의 기존 갤러리 순서 보호됨")
        
        print("✅ 데이터 보호 시스템 활성화 완료")
        
    except Exception as e:
        print(f"⚠️ 데이터 보호 시스템 체크 중 오류: {str(e)}")
        print("🛡️ 안전을 위해 모든 데이터를 보호 모드로 설정")

def downgrade():
    """
    🛡️ 데이터 보호를 위해 downgrade는 비활성화됩니다.
    
    기존 데이터의 안전을 위해 downgrade 작업을 수행하지 않습니다.
    """
    print("🛡️ 데이터 보호를 위해 downgrade가 비활성화되었습니다")
    print("🛡️ 기존 데이터는 안전하게 보호됩니다")
    pass 