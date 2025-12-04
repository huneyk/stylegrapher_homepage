# Stylegrapher Homepage

스타일그래퍼 공식 홈페이지입니다.

---

## 📌 이 프로젝트는 무엇인가요?

**스타일그래퍼**는 AI 얼굴분석, 퍼스널컬러 진단, 스타일링 컨설팅, 프로필 촬영 서비스를 제공하는 스튜디오의 웹사이트입니다.

### 🎯 주요 기능

| 기능 | 설명 |
|------|------|
| 📱 **서비스 소개** | AI 분석, 컨설팅, 원데이 스타일링, 프리미엄 화보 |
| 🖼️ **갤러리** | 포트폴리오 이미지 관리 |
| 🌐 **다국어 지원** | 한국어, 영어, 일본어, 중국어, 스페인어 |
| 📱 **반응형 디자인** | 모바일, 태블릿, PC 모두 최적화 |
| 🔐 **관리자 페이지** | 서비스, 갤러리, 예약 관리 |
| 🤖 **AI 자동 응답** | 문의/예약 이메일 자동 처리 |

---

## 🛠️ 어떤 기술을 사용하나요?

### 백엔드 (서버)

| 항목 | 기술 |
|------|------|
| 웹 프레임워크 | Flask (Python) |
| 데이터베이스 | MongoDB Atlas |
| 이미지 저장 | GridFS |
| 다국어 번역 | Flask-Babel + OpenAI GPT |
| AI 자동화 | CrewAI, LangChain |

### 프론트엔드 (화면)

| 항목 | 기술 |
|------|------|
| CSS 프레임워크 | Bootstrap 5.3 |
| 아이콘 | Bootstrap Icons |
| 폰트 | Google Fonts (나눔고딕, 나눔명조) |
| 디자인 테마 | The Violet Prism |

### 배포

| 항목 | 기술 |
|------|------|
| 서버 | Gunicorn |
| 호스팅 | Render.com |

---

## 📁 폴더 구조

프로젝트의 주요 폴더와 파일을 설명합니다.

```
stylegrapher_homepage_reform/
│
├── 📄 app.py                 ← 메인 프로그램 파일
├── 📄 config.py              ← 설정 파일
├── 📄 models.py              ← 데이터 모델 정의
│
├── 📂 routes/                ← 페이지 경로 관리
│   ├── main.py               ← 일반 사용자 페이지
│   └── admin.py              ← 관리자 페이지
│
├── 📂 templates/             ← HTML 템플릿 파일들
│   ├── base.html             ← 기본 레이아웃
│   ├── index.html            ← 메인 페이지
│   ├── services.html         ← 서비스 목록
│   ├── gallery.html          ← 갤러리
│   └── admin/                ← 관리자 페이지 템플릿
│
├── 📂 static/                ← 정적 파일들
│   ├── css/style.css         ← 스타일시트
│   └── images/               ← 이미지 파일
│
├── 📂 utils/                 ← 유틸리티 도구들
│   ├── mongo_models.py       ← MongoDB 연결
│   ├── translation.py        ← 자동 번역
│   ├── email_agents.py       ← 이메일 자동 처리
│   └── rag_context.py        ← AI 컨텍스트
│
├── 📂 translations/          ← 다국어 번역 파일
│   ├── en/                   ← 영어
│   ├── ja/                   ← 일본어
│   ├── zh/                   ← 중국어
│   └── es/                   ← 스페인어
│
└── 📄 requirements.txt       ← 필요한 패키지 목록
```

---

## 🚀 프로젝트 실행 방법

### 1단계: 준비하기

터미널(명령 프롬프트)을 열고 다음 명령어를 순서대로 입력하세요.

```bash
# 가상환경 만들기 (프로젝트 전용 공간)
python -m venv venv

# 가상환경 활성화
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 필요한 패키지 설치하기
pip install -r requirements.txt
```

### 2단계: 환경 변수 설정하기

프로젝트 폴더에 `.env` 파일을 만들고 아래 내용을 입력하세요.

```env
MONGO_URI=여기에_MongoDB_주소_입력
SECRET_KEY=비밀키_입력
FLASK_ENV=development
```

### 3단계: 서버 실행하기

```bash
python app.py
```

웹 브라우저에서 `http://localhost:5001` 주소로 접속하면 사이트를 볼 수 있습니다.

### 4단계: 관리자 계정 만들기 (선택)

```bash
python create_admin.py
```

---

## 🗄️ 데이터베이스 구조

MongoDB Atlas를 사용하며, 데이터베이스 이름은 `STG-DB`입니다.

### 주요 컬렉션 (테이블)

| 컬렉션명 | 저장하는 정보 |
|---------|-------------|
| `users` | 사용자 계정 (관리자) |
| `services` | 서비스 정보 |
| `service_options` | 서비스 세부 옵션 |
| `gallery_groups` | 갤러리 그룹 |
| `galleries` | 갤러리 이미지 |
| `bookings` | 예약 정보 |
| `inquiries` | 문의 내역 |
| `site_settings` | 사이트 설정 (색상 등) |
| `translations` | 다국어 번역 데이터 |
| `company_info` | 회사 정보 (AI용) |

### 서비스 카테고리

| 코드 | 의미 |
|------|------|
| `ai_analysis` | AI 분석 |
| `consulting` | 컨설팅 프로그램 |
| `oneday` | 원데이 스타일링 |
| `photo` | 프리미엄 화보 제작 |

---

## 🎨 CSS 디자인 가이드

CSS 스타일 관련 상세 내용은 별도 문서를 참고하세요.

👉 **[CSS_DESIGN_SYSTEM.md](./CSS_DESIGN_SYSTEM.md)**

---

## 🤖 AI 기능

### 이메일 자동 처리 시스템

문의나 예약이 들어오면 AI가 자동으로:

1. ✅ 스팸 여부 판단
2. 🌐 언어 감지 (한/영/일/중)
3. 😊 감정 분석 (긍정/중립/부정)
4. 📝 자동 응답 생성
5. 📧 관리자에게 알림

### 자동 번역 시스템

- OpenAI GPT-4o-mini 사용
- 5개 언어 지원 (한/영/일/중/스)
- JSON 파일로 캐싱하여 빠른 응답

---

## 📝 업데이트 기록

### 2025년 12월 4일
- AI Agent 시스템 추가 (이메일 자동 처리)
- 다국어 번역 시스템 강화
- 보안 모니터링 시스템 추가

### 2025년 12월 1일
- CSS 디자인 시스템 표준화
- Light/Dark 모드 분리
- 반응형 디자인 개선

### 2025년 3월 12일
- MongoDB Atlas로 데이터베이스 이전

---

## 📞 문의

| 채널 | 연락처 |
|------|--------|
| 🌐 웹사이트 | [stylegrapher.com](https://stylegrapher.com) |
| 💬 카카오톡 | 스타일그래퍼 |
| ✉️ 이메일 | stylegrapher.ysg@gmail.com |

---

## 📚 관련 문서

- [CSS 디자인 시스템](./CSS_DESIGN_SYSTEM.md) - 스타일 가이드
- [프론트엔드 가이드](./frontend_guidelines_document.md) - 프론트엔드 개발 지침
- [백엔드 구조](./backend_structure_document.md) - 백엔드 아키텍처
- [관리자 설정](./ADMIN_SETUP.md) - 관리자 계정 설정

---

© 2025 Stylegrapher. All rights reserved.
