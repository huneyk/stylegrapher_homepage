# StyleGrapher 보안 시스템 설정 가이드

## 🛡️ 보안 기능 개요

StyleGrapher 홈페이지에는 다층 보안 시스템이 구현되어 있습니다:

### 주요 보안 기능
1. **자동 위협 탐지**: 악성 봇, 스캐너, 공격 시도 자동 차단
2. **Rate Limiting**: IP별 요청 수 제한으로 DDoS 공격 방지
3. **보안 헤더**: XSS, 클릭재킹 등 웹 취약점 방어
4. **실시간 모니터링**: 보안 이벤트 실시간 추적 및 알림
5. **봇 관리**: robots.txt를 통한 크롤링 제어

## 🔧 보안 설정

### 1. 환경 변수 설정

`.env` 파일에 다음 보안 관련 설정을 추가하세요:

```bash
# 보안 알림 이메일 설정
SECURITY_EMAIL_USER=your-email@gmail.com
SECURITY_EMAIL_PASSWORD=your-app-password
SECURITY_ALERT_RECIPIENTS=admin1@company.com,admin2@company.com

# SMTP 설정 (Gmail 예시)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

### 2. Gmail 앱 비밀번호 생성

Gmail을 사용하는 경우:
1. Google 계정 → 보안 → 2단계 인증 활성화
2. 앱 비밀번호 생성
3. 생성된 비밀번호를 `SECURITY_EMAIL_PASSWORD`에 설정

## 📊 보안 대시보드 사용법

### 접근 방법
1. 관리자 로그인: `/admin`
2. 대시보드에서 "보안 대시보드" 클릭
3. 실시간 보안 상태 확인

### 대시보드 기능
- **실시간 통계**: 최근 1시간 보안 이벤트 요약
- **공격 유형 분석**: 주요 공격 패턴 및 빈도
- **상위 공격 IP**: 가장 위험한 IP 주소 목록
- **최근 이벤트**: 실시간 보안 이벤트 로그
- **리포트 다운로드**: 1시간/24시간 보안 리포트

## 🚨 자동 알림 시스템

### 알림 발생 조건
- **Rate Limit 초과**: 30분 내 10회 이상
- **공격 탐지**: 30분 내 20개 이상 차단된 요청
- **분산 공격**: 5개 이상 서로 다른 의심스러운 IP

### 알림 내용
- 공격 유형 및 심각도
- 공격 IP 주소 및 패턴
- 최근 보안 이벤트 요약
- 권장 대응 조치

## 🔍 차단되는 공격 패턴

### 1. WordPress 공격
- `/wp-content/`, `/wp-admin/`, `/wp-login.php`
- `/xmlrpc.php`, `/wp-config.php`

### 2. 시스템 파일 접근 시도
- `/.env`, `/config.php`, `/admin.php`
- `/phpmyadmin/`, `/phpMyAdmin/`

### 3. 스크립트 공격
- `.php`, `.asp`, `.aspx`, `.jsp` 파일 요청
- SQL injection 패턴

### 4. 의심스러운 User-Agent
- 보안 스캐너: `sqlmap`, `nikto`, `nmap`
- 자동화 도구: `curl`, `wget`, `python-requests`
- 빈 User-Agent

## 📈 성능 최적화

### Rate Limiting 설정
```python
# 기본 설정 (utils/security.py)
- IP당 분당 120회 요청 제한
- 시간 윈도우: 60초
- 메모리 기반 저장소 (개발용)
```

### 프로덕션 환경 권장사항
1. **Redis 사용**: Rate limiting 데이터 영구 저장
2. **로그 시스템**: ELK Stack 또는 Splunk 연동
3. **CDN 설정**: CloudFlare와 같은 CDN으로 1차 필터링
4. **방화벽**: 서버 레벨 방화벽 설정

## 🛠️ 고급 설정

### IP 차단 추가
```python
from utils.security import block_ip

# 특정 IP 수동 차단
block_ip("192.168.1.100")
```

### 알림 임계값 조정
```python
# utils/monitor.py
self.alert_threshold = {
    'rate_limit': 20,  # 기본값: 10
    'blocked_requests': 50,  # 기본값: 20
    'unique_suspicious_ips': 10  # 기본값: 5
}
```

## 📝 로그 분석

### 보안 로그 형식
```
2024-07-03 09:24:35 - SECURITY - WARNING - BLOCKED_REQUEST - IP: 52.178.199.177 - UA: - Details: Suspicious path: /wp-22.php
```

### 로그 위치
- 콘솔 출력: Flask 앱 실행 로그
- 모니터링 시스템: 메모리 저장 (최근 1시간)
- 보안 리포트: JSON 형식 다운로드

## 🔄 정기 점검 사항

### 일일 점검
1. 보안 대시보드 확인
2. 주요 공격 IP 분석
3. 비정상적인 트래픽 패턴 확인

### 주간 점검
1. 보안 리포트 다운로드 및 분석
2. 차단 규칙 효과성 검토
3. 알림 임계값 조정

### 월간 점검
1. 보안 정책 업데이트
2. 새로운 공격 패턴 추가
3. 시스템 성능 최적화

## ⚠️ 주의사항

1. **과도한 차단 방지**: 정상 사용자 차단 없도록 임계값 조정
2. **성능 모니터링**: Rate limiting이 정상 트래픽에 영향 없는지 확인
3. **정기 업데이트**: 새로운 공격 패턴 지속적으로 추가
4. **백업**: 보안 설정 및 로그 정기 백업

## 📞 긴급 대응

### 대규모 공격 시
1. Render 대시보드에서 서버 스케일링
2. 의심스러운 IP 대역 차단
3. 임시적으로 Rate Limit 강화
4. 보안 전문가 연락

### 문제 해결
- 과도한 차단으로 정상 사용자 접근 불가 시 임계값 완화
- 알림 폭주 시 알림 조건 조정
- 성능 저하 시 보안 기능 일시 비활성화

---

**보안은 지속적인 프로세스입니다. 정기적인 모니터링과 업데이트를 통해 안전한 서비스를 유지하세요.** 