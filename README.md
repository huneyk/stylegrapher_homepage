# Stylegrapher Homepage

스타일그래퍼 공식 홈페이지 - Flask 기반 웹 애플리케이션

## 📋 프로젝트 개요

스타일그래퍼는 AI 얼굴분석, 퍼스널컬러 진단, 스타일링 컨설팅, 화보 및 프로필 촬영 서비스를 제공하는 전문 스타일링 스튜디오의 공식 웹사이트입니다.

### 주요 기능
- **서비스 소개**: AI 분석, 컨설팅 프로그램, 원데이 스타일링, 프리미엄 화보 제작
- **갤러리**: GridFS 기반 이미지 관리 시스템
- **다국어 지원**: 한국어, 영어, 일본어, 중국어, 스페인어 (Flask-Babel)
- **반응형 디자인**: 모바일/태블릿/데스크톱 최적화
- **관리자 패널**: 서비스, 갤러리, 예약 관리

---

## 🛠 기술 스택

### Backend
- **Framework**: Flask 2.2.3
- **Database**: MongoDB Atlas (주), SQLite (마이그레이션 스크립트용)
- **ORM**: PyMongo, Flask-SQLAlchemy (레거시)
- **이미지 저장**: GridFS
- **인증**: Flask-Login
- **다국어**: Flask-Babel, OpenAI GPT-4o-mini (자동 번역)
- **AI Agent**: CrewAI, LangChain (이메일 자동 처리)

### Frontend
- **CSS Framework**: Bootstrap 5.3.0
- **Icons**: Bootstrap Icons 1.11.0
- **Fonts**: Google Fonts (Cormorant Garamond, Noto Sans KR, Nanum Gothic, Nanum Myeongjo)
- **Design**: Custom "The Violet Prism" 테마

### Deployment
- **WSGI Server**: Gunicorn
- **Platform**: Render.com

---

## 🎨 CSS 디자인 시스템 (style.css)

### 1. 색상 변수 (CSS Custom Properties)

```css
:root {
    /* Primary Colors - Light Violet Theme (Light Mode 기본) */
    --deep-violet: #f8f9fa;
    --rich-black: #ffffff;
    --neon-lavender: #8B5CF6;
    --electric-violet: #A78BFA;
    --soft-violet: #F0E8FF;
    
    /* Gradient Colors */
    --glow-start: rgba(139, 92, 246, 0.3);
    --glow-end: rgba(167, 139, 250, 0.2);
    
    /* Text Colors - Light Mode */
    --text-primary: #000000;
    --text-secondary: #6c757d;
    --text-muted: #8e8e8e;
    
    /* Glass Effect - Light Mode */
    --glass-bg: rgba(255, 255, 255, 0.9);
    --glass-border: rgba(139, 92, 246, 0.25);
    --glass-blur: 20px;
    
    /* Shadows - Light Mode */
    --neon-glow: 0 0 20px rgba(139, 92, 246, 0.3), 0 0 40px rgba(167, 139, 250, 0.15);
    --card-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    --hover-glow: 0 0 30px rgba(139, 92, 246, 0.3), 0 0 60px rgba(167, 139, 250, 0.2);
    
    /* Transitions */
    --transition-smooth: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    --transition-fast: all 0.2s ease;
    
    /* Dynamic Site Colors (Flask에서 오버라이드) */
    --main-color-rgb: 139, 92, 246;
    --sub-color-rgb: 167, 139, 250;
    --background-color-rgb: 255, 255, 255;
    --main-color: rgb(var(--main-color-rgb));
    --sub-color: rgb(var(--sub-color-rgb));
    --background-color: rgb(var(--background-color-rgb));
    
    /* Light Mode Specific */
    --primary-purple: #663399;
    --light-purple: #9966cc;
    --dark-purple: #4B0082;
}
```

### 2. STG Body Text - 본문 텍스트 기준

사이트 전체 본문 텍스트의 기준 스타일입니다.

```css
:root {
    --stg-body-font-family: 'Nanum Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
    --stg-body-font-size: 16px;
    --stg-body-line-height: 1.8;
    --stg-body-font-weight: 400;
    --stg-body-color-dark: rgba(255, 255, 255, 0.9);
    --stg-body-color-light: #6C757D;
    --stg-body-margin: 0px 0px 24px;
    --stg-body-padding: 0px 8px;
}
```

**사용 클래스:**
- `.stg_body_text` - underscore 버전
- `.stg-body-text` - hyphen 버전
- `.stg_card_text`, `.stg-card-text` - 카드 내 본문용

**적용 대상 요소:**
- `p`, `li` 태그
- `.body-text`, `.card-text`, `.message-text`
- `.philosophy-text`, `.icons-text`, `.era-text`
- `.experience-text`, `.mission-text`
- `.booking-content`, `.additional-card-text`
- `.service-card-description`, `.category-prism-description`
- `.service-option-description`, `.stg_card_description`

### 3. STG Card Title - 카드 제목 기준

모든 카드 제목의 기준 스타일입니다. (단일 소스 정의)

```css
:root {
    --stg-card-title-font-family: 'Nanum Gothic', sans-serif;
    --stg-card-title-font-size: 22.4px;
    --stg-card-title-font-size-mobile: 18px;
    --stg-card-title-font-weight: 600;
    --stg-card-title-color-light: #44237A;
    --stg-card-title-color-dark: rgb(var(--main-color-rgb));
    --stg-card-title-bg-light: #9379BC1A;
    --stg-card-title-bg-dark: rgba(200, 170, 255, 0.12);
    --stg-card-title-border-light: rgba(139, 92, 246, 0.2);
    --stg-card-title-border-dark: rgba(200, 170, 255, 0.2);
    --stg-card-title-padding: 12px 24px;
    --stg-card-title-padding-mobile: 10px 18px;
    --stg-card-title-border-radius: 12px;
    --stg-card-title-text-shadow-dark: 0 0 20px rgba(200, 170, 255, 0.5);
}

/* 기본 스타일 */
.stg_card_title,
.stg-card-title {
    font-family: var(--stg-card-title-font-family) !important;
    font-size: var(--stg-card-title-font-size) !important;
    font-weight: var(--stg-card-title-font-weight) !important;
    color: var(--stg-card-title-color-light) !important;
    background: var(--stg-card-title-bg-light);
    padding: var(--stg-card-title-padding);
    border-radius: var(--stg-card-title-border-radius);
    border: 1px solid var(--stg-card-title-border-light);
    display: inline-block;
    margin-bottom: 1rem;
}
```

**사용 클래스:**
- `.stg_card_title` - underscore 버전
- `.stg-card-title` - hyphen 버전 (동일 스타일)
- `.service-option-name` - stg_card_title 클래스와 함께 사용

### 4. STG Card Format - 카드 컨테이너 기준

모든 카드 컨테이너의 기준 스타일입니다.

```css
.stg_card_format {
    /* Glass Effect */
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border: 1px solid var(--glass-border);
    border-radius: 24px;
    box-shadow: var(--card-shadow);
    transition: var(--transition-smooth);
    position: relative;
    overflow: hidden;
    
    /* Layout */
    text-align: center;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
}

/* 카드 상단 그라데이션 라인 */
.stg_card_format::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--neon-lavender), var(--electric-violet), var(--neon-lavender));
    box-shadow: 0 0 20px rgba(200, 170, 255, 0.6);
}

.stg_card_format:hover {
    transform: translateY(-8px);
    border-color: rgba(200, 170, 255, 0.5);
    box-shadow: var(--hover-glow);
}
```

**내부 요소 클래스:**
| 클래스 | 용도 |
|--------|------|
| `.stg_card_content` | 컨텐츠 래퍼 (min-height: 260px) |
| `.stg_card_icon` | 아이콘 영역 (font-size: 3rem) |
| `.stg_card_title` | 제목 (별도 정의 참조) |
| `.stg_card_description` | 설명 (stg_body_text 스타일 적용) |
| `.stg_card_description--short` | 짧은 설명 변형 |
| `.stg_card_options` | 옵션 버튼 그리드 (2열) |
| `.stg_card_option_wrapper` | 옵션 버튼 래퍼 |
| `.stg_card_option_btn` | 옵션 버튼 |
| `.stg_card_option_text` | 옵션 버튼 텍스트 |
| `.stg_card_option_arrow` | 옵션 버튼 화살표 |

**변형 클래스:**
- `.stg_card_format--additional` - 추가 카드 (min-height: 300px, 더 강한 호버 효과)
- `.stg_card_format--padded` - 패딩 추가 (md 이상에서 2.5rem)

### 5. STG Button - 버튼 기준

모든 버튼의 기준 스타일입니다.

```css
:root {
    --stg-button-font-family: 'Nanum Gothic', sans-serif;
    --stg-button-font-size: 0.9rem;
    --stg-button-font-weight: 400;
    --stg-button-padding: 9.6px 12.8px;
    --stg-button-border-radius: 12px;
    --stg-button-transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    
    /* Button Colors (Light Mode) */
    --stg-button-bg: #44237A1A;
    --stg-button-color: #44237ACC;
    --stg-button-border: transparent;
    --stg-button-hover-bg: #44237A33;
    --stg-button-hover-color: #44237AFF;
    --stg-button-hover-shadow: none;
}

/* 기본 스타일 */
.stg_button {
    font-family: var(--stg-button-font-family) !important;
    font-size: var(--stg-button-font-size) !important;
    font-weight: var(--stg-button-font-weight) !important;
    padding: var(--stg-button-padding);
    border-radius: var(--stg-button-border-radius);
    transition: var(--stg-button-transition);
    width: 202px;
    height: 42px;
    background: var(--stg-button-bg);
    color: var(--stg-button-color) !important;
    border: none;
    /* Shine Effect 내장 */
}
```

**사용 클래스:**
| 클래스 | 용도 |
|--------|------|
| `.stg_button` | 기본 버튼 |
| `.stg_button--sm` | 작은 버튼 (0.5rem 0.8rem) |
| `.stg_button--lg` | 큰 버튼 (0.9rem 1.5rem) |
| `.stg_button--block` | 전체 너비 |
| `.option-button` | 옵션 버튼 (stg_button 스타일 상속)

**내부 요소:**
- `.stg_button_text` - 버튼 텍스트
- `.stg_button_arrow` - 버튼 화살표 (호버 시 표시)

### 6. STG Page Title - 페이지 타이틀 기준

```css
:root {
    --stg-page-title-font-family: 'Nanum Gothic', sans-serif;
    --stg-page-title-font-size: 40px;
    --stg-page-title-font-weight: 400;
    --stg-page-title-letter-spacing: 0.1em;
    --stg-page-title-color-dark: #44237A;
    --stg-page-title-color-light: #44237A;
    --stg-page-title-text-shadow-dark: 0 0 50px rgba(181, 126, 220, 0.5);
}

.stg_page_title {
    font-family: var(--stg-page-title-font-family) !important;
    font-size: var(--stg-page-title-font-size) !important;
    font-weight: var(--stg-page-title-font-weight) !important;
    letter-spacing: var(--stg-page-title-letter-spacing);
    color: var(--stg-page-title-color-dark) !important;
    text-shadow: var(--stg-page-title-text-shadow-dark);
    margin-bottom: 0.5rem;
}
```

**반응형:**
- `992px 이하`: 2.5rem
- `768px 이하`: 2.2rem
- `576px 이하`: 2rem

**사용 클래스:**
- `.stg_page_title`

### 7. Light Mode / Dark Mode

사이트는 Dark Mode를 기본으로 하며, Light Mode는 `body.light-mode` 클래스로 활성화됩니다.

**Light Mode 특징:**
- 배경: 밝은 그라데이션 (`linear-gradient(135deg, #f8f9fa, rgb(var(--background-color-rgb)), #f8f9fa)`)
- 텍스트: 검정색 기반
- 카드: 흰색 배경 (`rgba(255, 255, 255, 0.95)`)
- 글로우 효과 감소

**Dark Mode 특징:**
- 배경: 깊은 보라색 (`--deep-violet: #120024`)
- 텍스트: 흰색 기반
- 네온 글로우 효과 활성화
- Glassmorphism 효과

### 8. 반응형 브레이크포인트

```css
/* Desktop */
@media (min-width: 992px) { ... }

/* Tablet */
@media (max-width: 992px) { ... }

/* Mobile Large */
@media (max-width: 768px) { ... }

/* Mobile Small */
@media (max-width: 576px) { ... }
```

### 9. 주요 컴포넌트 클래스

#### STG 표준 클래스 (신규)

| 클래스 | 용도 |
|--------|------|
| `.stg_body_text`, `.stg-body-text` | 본문 텍스트 기준 |
| `.stg_card_text`, `.stg-card-text` | 카드 내 본문 텍스트 |
| `.stg_card_title`, `.stg-card-title` | 카드 제목 기준 |
| `.stg_card_format` | 카드 컨테이너 기준 |
| `.stg_card_format--additional` | 추가 카드 변형 |
| `.stg_card_format--padded` | 패딩 추가 변형 |
| `.stg_card_sub_format` | 서브 카드 스타일 (얇은 테두리) |
| `.stg_button` | 버튼 기준 |
| `.stg_page_title` | 페이지 타이틀 기준 |
| `.stg_table` | 테이블 기준 |
| `.stg_table_wrapper` | 테이블 래퍼 (가로 스크롤) |
| `.stg_floating_menu` | 플로팅 메뉴 버튼 |
| `.stg_kakao_format` | 카카오 문의 섹션 |

#### 기본 컴포넌트 클래스

| 클래스 | 용도 |
|--------|------|
| `.glass-card` | Glassmorphism 카드 |
| `.navbar`, `.navbar.scrolled` | 네비게이션 바 |
| `.hamburger-menu` | 햄버거 메뉴 버튼 |
| `.side-menu` | 사이드 메뉴 |
| `.floating-menu-right` | 플로팅 메뉴 컨테이너 |
| `.floating-item` | 플로팅 메뉴 아이템 |
| `.btn`, `.btn-neon`, `.btn-primary` | Bootstrap 버튼 |
| `.card`, `.card-title`, `.card-text` | Bootstrap 기본 카드 |
| `.service-simple-card` | 서비스 카드 |
| `.additional-card` | 추가 서비스 카드 |
| `.gallery-item`, `.gallery-preview-card` | 갤러리 아이템 |
| `.footer`, `.footer-info` | 푸터 |
| `.kakao-modal` | 카카오톡 연결 모달 |
| `.alert` | 알림 메시지 |
| `.feature-list`, `.feature-item` | 기능 리스트 (보라색 bullet) |
| `.kakao-btn-dark` | 카카오톡 버튼 (다크 테마) |

### 10. STG Table - 테이블 기준

```css
:root {
    --stg-table-font-family: var(--stg-body-font-family);
    --stg-table-font-size: 15px;
    --stg-table-line-height: 1.7;
    --stg-table-font-weight: 400;
    --stg-table-header-bg-dark: #44237AE6;
    --stg-table-header-bg-light: rgba(139, 92, 246, 0.55);
    --stg-table-header-color: #FFFFFF;
    --stg-table-border-color-dark: rgba(139, 92, 246, 0.6);
    --stg-table-border-color-light: rgba(139, 92, 246, 0.55);
}
```

**사용 클래스:**
| 클래스 | 용도 |
|--------|------|
| `.stg_table` | 테이블 기본 (min-width: 480px) |
| `.stg_table_wrapper` | 가로 스크롤 래퍼 |
| `.stg_table_name` | 이름 컬럼 (좌측 정렬) |
| `.stg_table_desc` | 설명 컬럼 (좌측 정렬) |
| `.stg_table_duration` | 시간 컬럼 (중앙 정렬) |
| `.stg_table_price` | 가격 컬럼 (우측 정렬) |
| `.stg_table_notes` | 비고 컬럼 (중앙 정렬) |

### 11. STG Floating Menu - 플로팅 메뉴

```css
:root {
    --stg-floating-menu-bg: rgba(68, 35, 122, 0.5);
    --stg-floating-menu-color: #FFFFFF;
    --stg-floating-menu-font-family: 'Nanum Gothic', -apple-system, sans-serif;
    --stg-floating-menu-font-size: 16px;
    --stg-floating-menu-padding: 8px 15px 8px 8px;
    --stg-floating-menu-border-radius: 28px;
}
```

**사용 클래스:**
- `.stg_floating_menu` - 플로팅 메뉴 버튼 (130px, backdrop-filter 적용)

### 12. STG Card Sub Format - 서브 카드 스타일

```css
:root {
    --stg-card-sub-border-color-light: rgba(139, 92, 246, 0.35);
    --stg-card-sub-border-color-dark: rgba(181, 126, 220, 0.4);
    --stg-card-sub-shadow-light: 0 4px 20px rgba(139, 92, 246, 0.12);
    --stg-card-sub-border-width: 1.5px;
    --stg-card-sub-border-radius: 24px;
}
```

**사용 클래스:**
- `.stg_card_sub_format` - outline 스타일의 카드 테두리 (갤러리 섹션 등)

### 13. STG Kakao Format - 카카오 문의 섹션

```css
.stg_kakao_format {
    position: relative;
    padding: 2rem 0;
    text-align: center;
}
```

**내부 요소:**
- `.stg_kakao_content` - 컨텐츠 래퍼
- `.stg_kakao_text` - 안내 텍스트 (stg_body_text 상속)

### 14. Feature List - 기능 리스트

```css
.feature-list { list-style: none; padding: 0; margin: 0; text-align: left; }
.feature-item { display: flex; align-items: flex-start; gap: 0.6rem; margin-bottom: 0.5rem; line-height: 1.4; }
.feature-item .bi-check-circle-fill { color: #8B5CF6; font-size: 0.7rem; margin-top: 0.35rem; }
```

### 15. 애니메이션

```css
/* 네온 펄스 */
@keyframes neonPulse {
    0%, 100% { box-shadow: var(--neon-glow); }
    50% { box-shadow: var(--hover-glow); }
}

/* 페이드 인 */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

/* 스피너 */
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* 모달 슬라이드 인 */
@keyframes modalSlideIn {
    from { opacity: 0; transform: translateY(-30px) scale(0.95); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
```

**Staggered 애니메이션 클래스:**
- `.stagger-1` ~ `.stagger-5` - 순차적 애니메이션 (0.1s ~ 0.5s delay)

---

## 🗄 데이터베이스 구조

### MongoDB 컬렉션 (Primary Database)

데이터베이스명: `STG-DB`

#### 1. users (사용자)
```javascript
{
    _id: Integer,           // Auto-increment ID
    username: String,       // 사용자명 (unique)
    email: String,          // 이메일
    password_hash: String,  // 암호화된 비밀번호
    is_admin: Boolean       // 관리자 여부
}
// 인덱스: username (unique)
```

#### 2. services (서비스)
```javascript
{
    _id: Integer,
    name: String,           // 서비스명
    description: String,    // 서비스 설명
    category: String,       // 카테고리 (ai_analysis, consulting, oneday, photo)
    details: String,        // JSON 형식 상세 내용
    packages: String        // JSON 형식 패키지 정보
}
// 인덱스: category
```

**카테고리 종류:**
- `ai_analysis` - AI 분석
- `consulting` - 컨설팅 프로그램
- `oneday` - 원데이 스타일링
- `photo` - 프리미엄 화보 제작

#### 3. service_options (서비스 옵션)
```javascript
{
    _id: Integer,
    service_id: Integer,              // 상위 서비스 ID
    name: String,                     // 옵션명
    description: String,              // 기본 설명 (카드 표시용)
    detailed_description: String,     // 상세 설명 (상세 페이지용)
    details: String,                  // JSON 형식 상세 내용 리스트
    packages: String,                 // JSON 형식 패키지/가격 정보
    booking_method: String,           // 예약 방법
    payment_info: String,             // 결제 정보
    guide_info: String,               // 안내 사항
    refund_policy: String,            // 환불 규정 (레거시)
    refund_policy_text: String,       // 환불 규정 텍스트
    refund_policy_table: String,      // 환불 규정 테이블 데이터
    overtime_charge_table: String     // 시간외 업차지 테이블
}
// 인덱스: service_id
```

#### 4. gallery_groups (갤러리 그룹)
```javascript
{
    _id: Integer,
    title: String,              // 그룹 제목
    display_order: Integer,     // 표시 순서 (높을수록 상위)
    is_pinned: Boolean,         // 상단 고정 여부
    created_at: DateTime,
    updated_at: DateTime
}
// 인덱스: (is_pinned DESC, display_order DESC, created_at DESC)
```

#### 5. galleries (갤러리 이미지)
```javascript
{
    _id: Integer,
    image_path: String,     // 이미지 경로 (GridFS file_id 또는 URL)
    caption: String,        // 캡션
    order: Integer,         // 그룹 내 순서
    group_id: Integer,      // 소속 갤러리 그룹 ID
    created_at: DateTime
}
// 인덱스: group_id
```

#### 6. bookings (예약)
```javascript
{
    _id: Integer,
    name: String,           // 예약자명
    phone: String,          // 전화번호
    email: String,          // 이메일
    service_id: Integer,    // 서비스 ID
    message: String,        // 예약 메시지 (희망 일시 포함)
    status: String,         // 상태 (대기, 확정, 취소)
    created_at: DateTime,
    
    // AI 처리 관련 필드
    is_spam: Boolean,               // 스팸 여부
    spam_reason: String,            // 스팸 판단 이유
    is_irrelevant: Boolean,         // RAG와 관련 없는 내용 여부
    irrelevant_reason: String,      // 관련 없는 내용 판단 이유
    detected_language: String,      // 감지된 언어 (ko, en, ja, zh)
    sentiment: String,              // 감성 (positive, neutral, negative)
    sentiment_detail: String,       // 감성 상세 (formal, casual, urgent)
    ai_response: String,            // AI가 생성한 응답
    translated_message: String,     // 번역된 원문 (한국어로)
    response_sent: Boolean,         // 응답 전송 여부
    response_sent_at: DateTime,     // 응답 발송 시간
    admin_notified: Boolean,        // 관리자 알림 여부
    ai_processed: Boolean,          // AI 처리 완료 여부
    ai_processed_at: DateTime       // AI 처리 시간
}
// 인덱스: created_at DESC
```

#### 7. inquiries (문의)
```javascript
{
    _id: Integer,
    name: String,           // 문의자명
    phone: String,          // 전화번호
    email: String,          // 이메일
    service_id: Integer,    // 관련 서비스 ID
    message: String,        // 문의 내용
    status: String,         // 상태 (대기, 처리중, 완료)
    created_at: DateTime,
    
    // AI 처리 관련 필드
    is_spam: Boolean,               // 스팸 여부
    spam_reason: String,            // 스팸 판단 이유
    is_irrelevant: Boolean,         // RAG와 관련 없는 내용 여부
    irrelevant_reason: String,      // 관련 없는 내용 판단 이유
    detected_language: String,      // 감지된 언어 (ko, en, ja, zh)
    sentiment: String,              // 감성 (positive, neutral, negative)
    sentiment_detail: String,       // 감성 상세 (formal, casual, urgent)
    ai_response: String,            // AI가 생성한 응답
    translated_message: String,     // 번역된 원문 (한국어로)
    response_sent: Boolean,         // 응답 전송 여부
    response_sent_at: DateTime,     // 응답 발송 시간
    admin_notified: Boolean,        // 관리자 알림 여부
    ai_processed: Boolean,          // AI 처리 완료 여부
    ai_processed_at: DateTime       // AI 처리 시간
}
// 인덱스: created_at DESC
```

#### 8. collage_texts (페이드 텍스트)
```javascript
{
    _id: Integer,
    text: String,           // 표시 텍스트
    order: Integer,         // 순서
    created_at: DateTime,
    updated_at: DateTime
}
// 인덱스: order
```

#### 9. site_settings (사이트 설정)
```javascript
{
    _id: Integer,
    site_mode: String,              // 'light' 또는 'dark' (기본: 'dark')
    main_color_r: Integer,          // 메인 컬러 R (기본: 181)
    main_color_g: Integer,          // 메인 컬러 G (기본: 126)
    main_color_b: Integer,          // 메인 컬러 B (기본: 220)
    sub_color_r: Integer,           // 서브 컬러 R (기본: 138)
    sub_color_g: Integer,           // 서브 컬러 G (기본: 43)
    sub_color_b: Integer,           // 서브 컬러 B (기본: 226)
    background_color_r: Integer,    // 배경 컬러 R (기본: 255)
    background_color_g: Integer,    // 배경 컬러 G (기본: 255)
    background_color_b: Integer,    // 배경 컬러 B (기본: 255)
    created_at: DateTime,
    updated_at: DateTime
}
```

**기본 색상값:**
- Main Color: `#B57EDC` (Neon Lavender)
- Sub Color: `#8A2BE2` (Electric Violet)
- Background Color: `#FFFFFF` (White, Light Mode용)

#### 10. terms_of_service (이용약관)
```javascript
{
    _id: Integer,
    content: String,        // HTML 또는 텍스트 내용
    created_at: DateTime,
    updated_at: DateTime
}
```

#### 11. privacy_policy (개인정보처리방침)
```javascript
{
    _id: Integer,
    content: String,        // HTML 또는 텍스트 내용
    created_at: DateTime,
    updated_at: DateTime
}
```

#### 12. company_info (회사 정보 - RAG용)
```javascript
{
    _id: Integer,
    company_name: String,                   // 회사명
    email: String,                          // 대표 이메일
    business_type: String,                  // 업종
    service_areas: String,                  // 서비스 분야
    customer_service_principles: String,    // 고객 응대 원칙
    additional_info: String,                // 추가 정보
    created_at: DateTime,
    updated_at: DateTime
}
```

#### 13. admin_notification_emails (관리자 알림 이메일)
```javascript
{
    _id: Integer,
    email: String,              // 이메일 주소 (unique)
    name: String,               // 담당자 이름
    is_active: Boolean,         // 활성화 상태
    receive_inquiries: Boolean, // 문의 알림 수신 여부
    receive_bookings: Boolean,  // 예약 알림 수신 여부
    created_at: DateTime,
    updated_at: DateTime
}
// 인덱스: email (unique), is_active
```

#### 14. translations (다국어 번역 데이터)
```javascript
{
    _id: String,            // "{source_type}_{source_id}" 형식
    source_type: String,    // 데이터 타입 (service, service_option 등)
    source_id: Integer,     // 원본 데이터 ID
    fields: {
        [field_name]: {
            original: String,       // 원본 텍스트 (한국어)
            translations: {
                en: String,         // 영어 번역
                ja: String,         // 일본어 번역
                zh: String,         // 중국어 번역
                es: String          // 스페인어 번역
            },
            updated_at: DateTime
        }
    },
    created_at: DateTime,
    updated_at: DateTime
}
// 인덱스: (source_type, source_id) unique
```

### GridFS (이미지 저장)

갤러리 이미지는 GridFS를 통해 저장됩니다.

```javascript
// fs.files 컬렉션
{
    _id: ObjectId,
    filename: String,
    contentType: String,    // 'image/jpeg', 'image/png' 등
    length: Number,
    uploadDate: DateTime,
    metadata: {
        original_filename: String,
        group_id: Integer
    }
}

// fs.chunks 컬렉션
{
    _id: ObjectId,
    files_id: ObjectId,
    n: Number,
    data: Binary
}
```

### SQLAlchemy 모델 (레거시 - 마이그레이션용)

`models.py`에 정의된 SQLAlchemy 모델은 마이그레이션 스크립트용으로 유지됩니다.
실제 운영에서는 `utils/mongo_models.py`의 MongoDB 모델을 사용합니다.

---

## 📁 디렉토리 구조

```
stylegrapher_homepage_reform/
├── app.py                      # Flask 애플리케이션 팩토리
├── wsgi.py                     # WSGI 엔트리포인트
├── config.py                   # 설정 파일
├── extensions.py               # Flask 확장 초기화
├── models.py                   # SQLAlchemy 모델 (레거시)
│
├── routes/
│   ├── __init__.py
│   ├── main.py                 # 메인 라우트 (사용자 페이지)
│   └── admin.py                # 관리자 라우트
│
├── utils/
│   ├── mongo_models.py         # MongoDB 모델 헬퍼
│   ├── gridfs_helper.py        # GridFS 유틸리티
│   ├── security.py             # 보안 유틸리티
│   ├── translation_helper.py   # 번역 헬퍼
│   ├── translation.py          # 다국어 번역 시스템 (GPT API + JSON 캐싱)
│   ├── rag_context.py          # RAG Context 모듈 (AI Agent용 컨텍스트)
│   ├── email_agents.py         # CrewAI 기반 이메일 처리 Agent 시스템
│   ├── monitor.py              # 보안 모니터링 시스템
│   └── social_media.py         # 소셜 미디어 API 통합 (Instagram, YouTube)
│
├── templates/
│   ├── base.html               # 기본 템플릿 (Light/Dark Mode CSS 포함)
│   ├── index.html              # 메인 페이지
│   ├── services.html           # 서비스 목록
│   ├── service_detail.html     # 서비스 상세
│   ├── gallery.html            # 갤러리
│   ├── about.html              # 소개 페이지
│   └── admin/                  # 관리자 템플릿
│
├── static/
│   ├── css/
│   │   └── style.css           # 메인 스타일시트
│   ├── images/                 # 정적 이미지
│   └── robots.txt
│
├── translations/               # Flask-Babel 번역 파일
│   ├── en/LC_MESSAGES/
│   ├── ja/LC_MESSAGES/
│   ├── zh/LC_MESSAGES/
│   └── es/LC_MESSAGES/
│
├── instance/                   # 인스턴스 설정 (gitignore)
├── migrations/                 # Flask-Migrate (레거시)
│
├── requirements.txt            # Python 의존성
├── Procfile                    # Render 배포 설정
├── render.yaml                 # Render 서비스 설정
└── README.md                   # 이 파일
```

---

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 생성:

```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

### 3. 실행

```bash
# 개발 서버
python app.py

# 또는
flask run --host=0.0.0.0 --port=5001
```

### 4. 관리자 계정 생성

```bash
python create_admin.py
```

---

## 📝 업데이트 내역

### 2025년 3월 12일
- MongoDB Atlas로 데이터베이스 마이그레이션 완료
- DictAsModel 오류 수정

### 2025년 12월 1일
- CSS 디자인 시스템 표준화
  - STG Body Text 변수 정의
  - STG Card Title 표준 클래스 생성
  - STG Card Format 컨테이너 표준화
  - STG Button 표준 클래스 생성
  - STG Page Title 표준화
- Light Mode / Dark Mode 스타일 분리
- 반응형 디자인 개선
- 다국어 지원 확장 (5개 언어)

### 2025년 12월 4일
- **AI Agent 시스템 추가**
  - CrewAI 기반 이메일 처리 시스템 (`email_agents.py`)
  - RAG Context 모듈 추가 (`rag_context.py`)
  - 문의/예약 자동 응답 생성
  - 스팸/관련없는 내용 자동 분류
  - 다국어 감지 및 자동 번역
  
- **다국어 번역 시스템 강화**
  - OpenAI GPT-4o-mini 기반 자동 번역 (`translation.py`)
  - JSON 파일 캐싱 시스템 (읽기 성능 최적화)
  - MongoDB + JSON 캐시 이중 저장
  
- **새로운 MongoDB 컬렉션**
  - `company_info` - 회사 정보 (RAG용)
  - `admin_notification_emails` - 관리자 알림 이메일
  - `translations` - 다국어 번역 데이터
  
- **문의/예약 모델 확장**
  - AI 처리 관련 필드 추가 (is_spam, detected_language, sentiment, ai_response 등)
  - 스팸 분류 및 관련성 판단 기능
  
- **보안 모니터링 시스템**
  - SecurityMonitor 클래스 추가 (`monitor.py`)
  - Rate limit 및 공격 패턴 탐지
  - 이메일 알림 기능
  
- **CSS 디자인 시스템 확장**
  - STG Table 표준 클래스 추가
  - STG Floating Menu 스타일 추가
  - STG Card Sub Format 추가
  - STG Kakao Format 추가
  - Feature List 스타일 추가
  
- **유틸리티 모듈 추가**
  - `social_media.py` - Instagram/YouTube API 통합

---

## 📞 문의

- **웹사이트**: [Stylegrapher](https://stylegrapher.com)
- **카카오톡**: 스타일그래퍼
- **이메일**: stylegrapher.ysg@gmail.com

---

© 2025 Stylegrapher. All rights reserved.



