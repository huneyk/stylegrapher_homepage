# Stylegrapher Homepage - 로컬 실행 가이드

## 사전 요구사항

- Python 3.9+
- MongoDB Atlas 계정 (또는 로컬 MongoDB)

## 실행 방법

### 1. 가상환경 생성 및 활성화

```bash
python -m venv stylegrapher
source stylegrapher/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 항목을 설정합니다.

```
MONGO_URI=<MongoDB 연결 URI>
OPENAI_API_KEY=<OpenAI API 키>

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<이메일 주소>
MAIL_PASSWORD=<앱 비밀번호>
MAIL_DEFAULT_SENDER=<발신자 이메일>
```

### 4. 앱 실행

```bash
python app.py
```

서버가 `http://localhost:8000` 에서 실행됩니다.

또는 wsgi 엔트리포인트를 사용할 수도 있습니다.

```bash
python wsgi.py
```

이 경우 `http://localhost:5001` 에서 실행됩니다.
