# 🛡️ 관리자 계정 생성 가이드

## 개요

`create_admin.py` 스크립트는 기존 데이터를 보호하면서 안전하게 관리자 계정만 생성하는 도구입니다.

## 🔒 안전 보장

- ✅ **기존 데이터 보호**: 기존 데이터는 절대 덮어쓰거나 삭제하지 않습니다
- ✅ **중복 확인**: 기존 관리자 계정 존재 여부를 먼저 확인합니다
- ✅ **입력 검증**: 사용자명과 이메일 중복을 확인합니다
- ✅ **비밀번호 보안**: 안전한 해시 방식으로 비밀번호를 저장합니다

## 🛡️ 기존 데이터 덮어쓰기 방지 기능

### 문제 해결됨: 예약 방법, 결제 방법 등 데이터 보호
- **기존 문제**: 관리자가 서비스 옵션을 편집할 때 실수로 빈 값을 저장하면 기존 데이터가 삭제됨
- **해결 방법**: 
  - 기존 데이터가 있는 필드는 빈 값으로 덮어쓰지 않도록 수정
  - 관리자 페이지에서 저장 시 확인창으로 실수 방지
  - 의도적으로 삭제하려는 경우에만 데이터 삭제 허용

### 갤러리 표출 순서 보호
- 갤러리 순서는 명시적으로 변경할 때만 업데이트됩니다
- 새 갤러리 업로드 시 기존 갤러리 순서에 영향을 주지 않습니다

## 📋 사용 방법

### 1. 가상환경 활성화 (이미 활성화된 경우 생략)
```bash
source stylegrapher/bin/activate
```

### 2. 관리자 계정 생성
```bash
python create_admin.py
```

### 3. 화면 안내에 따라 정보 입력
- **관리자 사용자명**: 로그인에 사용할 사용자명
- **관리자 이메일**: 선택사항 (비워둘 수 있음)
- **관리자 비밀번호**: 최소 6자 이상

## 📝 실행 예시

```bash
$ python create_admin.py

============================================================
🛡️  스타일그래퍼 관리자 계정 생성 도구
============================================================
이 스크립트는 기존 데이터를 보호하면서 관리자 계정만 생성합니다.
기존 데이터는 절대 덮어쓰거나 삭제하지 않습니다.
------------------------------------------------------------

🔐 새로운 관리자 계정 정보를 입력하세요:
관리자 사용자명: admin
관리자 이메일 (선택사항): admin@stylegrapher.com
관리자 비밀번호: 
비밀번호 확인: 

✅ 관리자 계정이 성공적으로 생성되었습니다!
   사용자명: admin
   이메일: admin@stylegrapher.com
   관리자 권한: 활성화

🌐 관리자 로그인 URL: http://localhost:5001/admin/login
```

## 🚀 생성 후 로그인

### 1. Flask 앱 실행 (아직 실행하지 않은 경우)
```bash
python app.py
```

### 2. 관리자 페이지 접속
브라우저에서 다음 URL로 접속:
```
http://localhost:5001/admin/login
```

### 3. 로그인
생성한 관리자 계정 정보로 로그인하세요.

## ⚠️ 중요 사항

- **기존 관리자가 있는 경우**: 새로운 관리자 추가 여부를 묻습니다
- **사용자명 중복**: 기존 사용자명과 중복될 수 없습니다
- **이메일 중복**: 기존 이메일과 중복될 수 없습니다
- **비밀번호**: 최소 6자 이상이어야 합니다

## 🔧 문제 해결

### 데이터베이스 연결 오류
```bash
# 데이터베이스 테이블이 없는 경우
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 가상환경 관련 오류
```bash
# 가상환경이 활성화되지 않은 경우
source stylegrapher/bin/activate
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. 가상환경이 활성화되어 있는지
2. 필요한 패키지가 설치되어 있는지 (`pip install -r requirements.txt`)
3. 데이터베이스 파일이 존재하는지

## 🔧 기존 데이터 복구

만약 실수로 데이터가 삭제된 경우:
1. 데이터베이스 백업이 있다면 복원하세요
2. 관리자 페이지에서 다시 입력하세요
3. 앞으로는 데이터 보호 기능이 자동으로 작동합니다 