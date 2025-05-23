from app import create_app
from extensions import db
from models import User, Service, Gallery, Booking, ServiceOption, CarouselItem, GalleryGroup, CollageText
import json
from datetime import datetime, UTC

def init_db():
    app = create_app()
    with app.app_context():
        # 데이터베이스 테이블 생성
        db.drop_all()  # 기존 테이블 삭제
        db.create_all()  # 새로 테이블 생성
        
        # 테스트용 갤러리 그룹 생성
        gallery_groups = [
            GalleryGroup(title='웨딩 포토 1', created_at=datetime.now(UTC)),
            GalleryGroup(title='프로필 촬영 1', created_at=datetime.now(UTC)),
            GalleryGroup(title='패밀리 촬영', created_at=datetime.now(UTC)),
            GalleryGroup(title='웨딩 포토 2', created_at=datetime.now(UTC)),
            GalleryGroup(title='프로필 촬영 2', created_at=datetime.now(UTC)),
            GalleryGroup(title='커플 촬영', created_at=datetime.now(UTC))
        ]
        
        for group in gallery_groups:
            db.session.add(group)
        
        db.session.commit()
        
        # 각 그룹에 이미지 추가
        for i, group in enumerate(gallery_groups):
            gallery = Gallery(
                image_path=f'slide{(i % 5) + 1}.jpg',  # 기존 테스트 이미지 재사용
                group_id=group.id
            )
            db.session.add(gallery)
        
        # 초기 CollageText 데이터 추가
        collage_texts = [
            CollageText(text="당신만의 특별한 순간을", order=1),
            CollageText(text="스타일그래퍼가", order=2),
            CollageText(text="완성해드립니다", order=3)
        ]
        
        for text in collage_texts:
            db.session.add(text)
        
        # 초기 캐러셀 데이터 추가
        carousel_items = [
            CarouselItem(
                title='Stylegrapher 스타일그래퍼',
                subtitle='당신만의 특별한 순간을 완성해드립니다',
                image_path='slide1.jpg',
                order=0
            ),
            CarouselItem(
                title='프로페셔널한 촬영',
                subtitle='최고의 퀄리티로 담아내는 당신의 모습',
                image_path='slide2.jpg',
                order=1
            ),
            CarouselItem(
                title='스타일 컨설팅',
                subtitle='당신만의 매력을 찾아드립니다',
                image_path='slide3.jpg',
                order=2
            ),
            CarouselItem(
                title='자연스러운 순간',
                subtitle='편안한 분위기에서 진행되는 촬영',
                image_path='slide4.jpg',
                order=3
            ),
            CarouselItem(
                title='특별한 추억',
                subtitle='소중한 순간을 영원히 간직하세요',
                image_path='slide5.jpg',
                order=4
            )
        ]
        
        for item in carousel_items:
            db.session.add(item)

        # 여기서 서비스 데이터 추가
        services_data = [
            {
                'name': '개인화보',
                'description': '특별한 순간을 아름답게 담아드립니다',
                'category': '촬영',
                'details': json.dumps([
                    '전문 포토그래퍼의 1:1 촬영',
                    '헤어메이크업 서비스 포함',
                    '온라인 갤러리 제공',
                    '고해상도 원본 파일 제공'
                ]),
                'packages': json.dumps([
                    {
                        'name': '베이직 패키지',
                        'description': '1시간 촬영, 5컷 보정',
                        'price': '150000'
                    },
                    {
                        'name': '스탠다드 패키지',
                        'description': '2시간 촬영, 10컷 보정',
                        'price': '250000'
                    },
                    {
                        'name': '프리미엄 패키지',
                        'description': '3시간 촬영, 20컷 보정',
                        'price': '350000'
                    }
                ])
            },
            {
                'name': '프로필',
                'description': '전문적인 프로필 촬영 서비스를 제공합니다',
                'category': '촬영',
                'details': json.dumps([
                    '이력서/링크드인용 프로필',
                    '배우/모델 프로필',
                    '기업 임원 프로필',
                    '전문가용 프로필'
                ]),
                'packages': json.dumps([
                    {
                        'name': '기본 프로필',
                        'description': '30분 촬영, 3컷 보정',
                        'price': '100000'
                    },
                    {
                        'name': '전문가 프로필',
                        'description': '1시간 촬영, 5컷 보정',
                        'price': '180000'
                    }
                ])
            },
            {
                'name': '퍼스널 컬러 진단',
                'description': '나에게 어울리는 컬러를 찾아드립니다',
                'category': '컨설팅',
                'details': json.dumps([
                    '전문가의 1:1 컨설팅',
                    '계절별 퍼스널 컬러 진단',
                    '메이크업 컬러 추천',
                    '의상 컬러 가이드',
                    '진단 결과서 제공'
                ]),
                'packages': json.dumps([
                    {
                        'name': '기본 진단',
                        'description': '1시간 기본 진단 + 결과서',
                        'price': '80000'
                    },
                    {
                        'name': '프리미엄 진단',
                        'description': '2시간 상세 진단 + 메이크업 컬러 처방 + 스타일링 가이드',
                        'price': '150000'
                    }
                ])
            },
            {
                'name': '메이크업 레슨',
                'description': '나만의 메이크업 스킬을 배워보세요',
                'category': '메이크업',
                'details': json.dumps([
                    '1:1 맞춤 메이크업 레슨',
                    '개인 얼굴형 분석',
                    '메이크업 제품 추천',
                    '데일리/오피스/파티 메이크업',
                    '셀프 메이크업 노하우 전수'
                ]),
                'packages': json.dumps([
                    {
                        'name': '원데이 클래스',
                        'description': '3시간 기초 메이크업 레슨',
                        'price': '150000'
                    },
                    {
                        'name': '프리미엄 패키지',
                        'description': '4회 과정 심화 메이크업 레슨',
                        'price': '500000'
                    }
                ])
            },
            {
                'name': '메이크업/헤어 스타일링',
                'description': '전문가의 손길로 완성하는 스타일링',
                'category': '메이크업',
                'details': json.dumps([
                    '전문 메이크업 아티스트의 시술',
                    '헤어 스타일링',
                    '피부 타입별 맞춤 메이크업',
                    '상황별 맞춤 스타일링',
                    '지속력 높은 고급 제품 사용'
                ]),
                'packages': json.dumps([
                    {
                        'name': '메이크업 단품',
                        'description': '메이크업 시술',
                        'price': '100000'
                    },
                    {
                        'name': '헤어 단품',
                        'description': '헤어 스타일링',
                        'price': '80000'
                    },
                    {
                        'name': '토탈 패키지',
                        'description': '메이크업 + 헤어 스타일링',
                        'price': '150000'
                    }
                ])
            },
            {
                'name': '패션 스타일링',
                'description': '당신만의 스타일을 찾아드립니다',
                'category': '컨설팅',
                'details': json.dumps([
                    '체형 분석 및 진단',
                    '스타일 컨설팅',
                    '퍼스널 쇼핑 가이드',
                    '워드로브 정리',
                    '스타일링 팁 제공'
                ]),
                'packages': json.dumps([
                    {
                        'name': '스타일 진단',
                        'description': '1시간 스타일 분석 및 제안',
                        'price': '100000'
                    },
                    {
                        'name': '쇼핑 메이트',
                        'description': '3시간 동행 쇼핑 및 스타일링',
                        'price': '250000'
                    },
                    {
                        'name': '토탈 스타일링',
                        'description': '스타일 진단 + 쇼핑 메이트 + 옷장 정리',
                        'price': '400000'
                    }
                ])
            }
        ]
        
        for service_data in services_data:
            service = Service(**service_data)
            db.session.add(service)
        
        # 관리자 계정 생성
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
        
        db.session.commit()
        print("Database initialized!")

if __name__ == '__main__':
    init_db() 