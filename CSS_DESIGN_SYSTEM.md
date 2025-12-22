# 🎨 Stylegrapher CSS 디자인 시스템

이 문서는 Stylegrapher 홈페이지의 CSS 스타일 가이드입니다.  
스타일시트 파일: `static/css/style.css`

---

## 📋 목차

1. [색상 변수](#1-색상-변수)
2. [본문 텍스트 스타일](#2-본문-텍스트-스타일-stg-body-text)
3. [카드 제목 스타일](#3-카드-제목-스타일-stg-card-title)
4. [카드 컨테이너 스타일](#4-카드-컨테이너-스타일-stg-card-format)
5. [버튼 스타일](#5-버튼-스타일-stg-button)
6. [페이지 타이틀 스타일](#6-페이지-타이틀-스타일-stg-page-title)
7. [테이블 스타일](#7-테이블-스타일-stg-table)
8. [플로팅 메뉴 스타일](#8-플로팅-메뉴-스타일)
9. [라이트/다크 모드](#9-라이트다크-모드)
10. [반응형 브레이크포인트](#10-반응형-브레이크포인트)
11. [클래스 요약표](#11-클래스-요약표)
12. [애니메이션](#12-애니메이션)

---

## 1. 색상 변수

CSS 커스텀 프로퍼티(CSS Custom Properties)를 사용합니다.

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

---

## 2. 본문 텍스트 스타일 (STG Body Text)

사이트 전체 본문 텍스트의 기준 스타일입니다.

### CSS 변수

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

### 사용 가능한 클래스

| 클래스명 | 설명 |
|---------|------|
| `.stg_body_text` | 기본 본문 텍스트 (underscore 버전) |
| `.stg-body-text` | 기본 본문 텍스트 (hyphen 버전) |
| `.stg_card_text` | 카드 내부 본문용 |
| `.stg-card-text` | 카드 내부 본문용 |

### 자동 적용되는 요소

다음 요소들에는 자동으로 본문 텍스트 스타일이 적용됩니다:

- `p`, `li` 태그
- `.body-text`, `.card-text`, `.message-text`
- `.philosophy-text`, `.icons-text`, `.era-text`
- `.experience-text`, `.mission-text`
- `.booking-content`, `.additional-card-text`
- `.service-card-description`, `.category-prism-description`
- `.service-option-description`, `.stg_card_description`

---

## 3. 카드 제목 스타일 (STG Card Title)

모든 카드 제목의 기준 스타일입니다.

### CSS 변수

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
```

### 기본 스타일

```css
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

### 사용 가능한 클래스

| 클래스명 | 설명 |
|---------|------|
| `.stg_card_title` | 카드 제목 (underscore 버전) |
| `.stg-card-title` | 카드 제목 (hyphen 버전) |
| `.service-option-name` | 서비스 옵션명 (stg_card_title과 함께 사용) |

---

## 4. 카드 컨테이너 스타일 (STG Card Format)

모든 카드 컨테이너의 기준 스타일입니다.

### 기본 스타일

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

/* 호버 효과 */
.stg_card_format:hover {
    transform: translateY(-8px);
    border-color: rgba(200, 170, 255, 0.5);
    box-shadow: var(--hover-glow);
}
```

### 내부 요소 클래스

| 클래스명 | 용도 |
|---------|------|
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

### 변형 클래스

| 클래스명 | 설명 |
|---------|------|
| `.stg_card_format--additional` | 추가 카드 (min-height: 300px, 더 강한 호버 효과) |
| `.stg_card_format--padded` | 패딩 추가 (md 이상에서 2.5rem) |

---

## 5. 버튼 스타일 (STG Button)

모든 버튼의 기준 스타일입니다.

### CSS 변수

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
```

### 기본 스타일

```css
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
}
```

### 사용 가능한 클래스

| 클래스명 | 용도 |
|---------|------|
| `.stg_button` | 기본 버튼 |
| `.stg_button--sm` | 작은 버튼 (0.5rem 0.8rem) |
| `.stg_button--lg` | 큰 버튼 (0.9rem 1.5rem) |
| `.stg_button--block` | 전체 너비 |
| `.option-button` | 옵션 버튼 (stg_button 스타일 상속) |

### 내부 요소

| 클래스명 | 용도 |
|---------|------|
| `.stg_button_text` | 버튼 텍스트 |
| `.stg_button_arrow` | 버튼 화살표 (호버 시 표시) |

---

## 6. 페이지 타이틀 스타일 (STG Page Title)

### CSS 변수

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
```

### 기본 스타일

```css
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

### 반응형 크기

| 화면 크기 | 폰트 크기 |
|----------|----------|
| 992px 이상 | 40px |
| 992px 이하 | 2.5rem |
| 768px 이하 | 2.2rem |
| 576px 이하 | 2rem |

---

## 7. 테이블 스타일 (STG Table)

### CSS 변수

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

### 사용 가능한 클래스

| 클래스명 | 용도 |
|---------|------|
| `.stg_table` | 테이블 기본 (min-width: 480px) |
| `.stg_table_wrapper` | 가로 스크롤 래퍼 |
| `.stg_table_name` | 이름 컬럼 (좌측 정렬) |
| `.stg_table_desc` | 설명 컬럼 (좌측 정렬) |
| `.stg_table_duration` | 시간 컬럼 (중앙 정렬) |
| `.stg_table_price` | 가격 컬럼 (우측 정렬) |
| `.stg_table_notes` | 비고 컬럼 (중앙 정렬) |

---

## 8. 플로팅 메뉴 스타일

### CSS 변수

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

### 사용 가능한 클래스

| 클래스명 | 용도 |
|---------|------|
| `.stg_floating_menu` | 플로팅 메뉴 버튼 (130px, backdrop-filter 적용) |

---

## 9. 라이트/다크 모드

사이트는 **Light Mode**를 기본으로 합니다.

### Light Mode (기본)

```css
/* body에 클래스 없음 또는 body.light-mode */
```

**특징:**
- 배경: 밝은 그라데이션 (`linear-gradient(135deg, #f8f9fa, rgb(var(--background-color-rgb)), #f8f9fa)`)
- 텍스트: 검정색 기반
- 카드: 흰색 배경 (`rgba(255, 255, 255, 0.95)`)
- 글로우 효과 감소

### Dark Mode

```css
/* body 태그에 다크모드 클래스 적용 */
body:not(.light-mode) { ... }
```

**특징:**
- 배경: 깊은 보라색 (`--deep-violet: #120024`)
- 텍스트: 흰색 기반
- 네온 글로우 효과 활성화
- Glassmorphism 효과

---

## 10. 반응형 브레이크포인트

```css
/* Desktop (기본) */
/* 992px 이상 */

/* Tablet */
@media (max-width: 992px) { ... }

/* Mobile Large */
@media (max-width: 768px) { ... }

/* Mobile Small */
@media (max-width: 576px) { ... }
```

---

## 11. 클래스 요약표

### STG 표준 클래스 (신규)

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

### 기본 컴포넌트 클래스

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

---

## 12. 애니메이션

### 기본 애니메이션

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

### Staggered 애니메이션 클래스

순차적인 애니메이션 효과를 위한 클래스입니다.

| 클래스 | 딜레이 |
|--------|--------|
| `.stagger-1` | 0.1초 |
| `.stagger-2` | 0.2초 |
| `.stagger-3` | 0.3초 |
| `.stagger-4` | 0.4초 |
| `.stagger-5` | 0.5초 |

---

## 📝 기타 스타일

### Feature List (기능 리스트)

```css
.feature-list { 
    list-style: none; 
    padding: 0; 
    margin: 0; 
    text-align: left; 
}

.feature-item { 
    display: flex; 
    align-items: flex-start; 
    gap: 0.6rem; 
    margin-bottom: 0.5rem; 
    line-height: 1.4; 
}

.feature-item .bi-check-circle-fill { 
    color: #8B5CF6; 
    font-size: 0.7rem; 
    margin-top: 0.35rem; 
}
```

### STG Card Sub Format (서브 카드)

```css
:root {
    --stg-card-sub-border-color-light: rgba(139, 92, 246, 0.35);
    --stg-card-sub-border-color-dark: rgba(181, 126, 220, 0.4);
    --stg-card-sub-shadow-light: 0 4px 20px rgba(139, 92, 246, 0.12);
    --stg-card-sub-border-width: 1.5px;
    --stg-card-sub-border-radius: 24px;
}
```

### STG Kakao Format (카카오 문의 섹션)

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

---

© 2025 Stylegrapher. All rights reserved.













