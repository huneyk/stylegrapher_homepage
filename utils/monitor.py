import os
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import logging
from flask import current_app
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 보안 이벤트 저장소 (실제 환경에서는 데이터베이스 권장)
security_events = []
ip_stats = defaultdict(int)
attack_patterns = Counter()

class SecurityMonitor:
    def __init__(self):
        self.alert_threshold = {
            'rate_limit': 10,  # 10번 이상 rate limit 시 알림
            'blocked_requests': 20,  # 20개 이상 차단된 요청 시 알림
            'unique_suspicious_ips': 5  # 5개 이상의 서로 다른 의심스러운 IP 시 알림
        }
    
    def log_security_event(self, event_type, client_ip, user_agent, path, details):
        """보안 이벤트 기록"""
        event = {
            'timestamp': datetime.now(),
            'type': event_type,
            'client_ip': client_ip,
            'user_agent': user_agent,
            'path': path,
            'details': details
        }
        
        security_events.append(event)
        ip_stats[client_ip] += 1
        attack_patterns[event_type] += 1
        
        # 최근 1시간 이벤트만 유지
        cutoff_time = datetime.now() - timedelta(hours=1)
        global security_events
        security_events = [e for e in security_events if e['timestamp'] > cutoff_time]
        
        # 알림 체크
        self.check_alert_conditions()
    
    def check_alert_conditions(self):
        """알림 조건 확인"""
        recent_events = self.get_recent_events(minutes=30)
        
        # Rate limit 초과 횟수
        rate_limit_count = len([e for e in recent_events if e['type'] == 'RATE_LIMIT'])
        if rate_limit_count >= self.alert_threshold['rate_limit']:
            self.send_alert('RATE_LIMIT_SPIKE', f"Rate limit exceeded {rate_limit_count} times in 30 minutes")
        
        # 차단된 요청 수
        blocked_count = len([e for e in recent_events if e['type'] == 'BLOCKED_REQUEST'])
        if blocked_count >= self.alert_threshold['blocked_requests']:
            self.send_alert('ATTACK_DETECTED', f"{blocked_count} suspicious requests blocked in 30 minutes")
        
        # 고유 의심스러운 IP 수
        unique_ips = len(set(e['client_ip'] for e in recent_events))
        if unique_ips >= self.alert_threshold['unique_suspicious_ips']:
            self.send_alert('DISTRIBUTED_ATTACK', f"{unique_ips} different suspicious IPs detected")
    
    def get_recent_events(self, minutes=60):
        """최근 지정된 시간 내의 이벤트 조회"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [e for e in security_events if e['timestamp'] > cutoff_time]
    
    def get_top_attacking_ips(self, limit=10):
        """가장 많이 공격하는 IP 목록"""
        return Counter(ip_stats).most_common(limit)
    
    def get_attack_summary(self):
        """공격 패턴 요약"""
        recent_events = self.get_recent_events()
        
        return {
            'total_events': len(recent_events),
            'unique_ips': len(set(e['client_ip'] for e in recent_events)),
            'top_attack_types': attack_patterns.most_common(5),
            'top_ips': self.get_top_attacking_ips(5),
            'recent_events': recent_events[-10:]  # 최근 10개 이벤트
        }
    
    def send_alert(self, alert_type, message):
        """이메일 알림 전송"""
        try:
            # 환경변수에서 설정 읽기
            smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            email_user = os.environ.get('SECURITY_EMAIL_USER')
            email_password = os.environ.get('SECURITY_EMAIL_PASSWORD')
            alert_recipients = os.environ.get('SECURITY_ALERT_RECIPIENTS', '').split(',')
            
            if not email_user or not email_password or not alert_recipients[0]:
                logging.warning("Security alert email not configured")
                return
            
            # 이메일 작성
            msg = MIMEMultipart()
            msg['From'] = email_user
            msg['To'] = ', '.join(alert_recipients)
            msg['Subject'] = f'Security Alert: {alert_type} - StyleGrapher'
            
            body = f"""
Security Alert: {alert_type}

Details: {message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Recent Security Summary:
{json.dumps(self.get_attack_summary(), indent=2, default=str)}

Please review the security logs and take appropriate action if necessary.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # 이메일 전송
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(email_user, email_password)
            text = msg.as_string()
            server.sendmail(email_user, alert_recipients, text)
            server.quit()
            
            logging.info(f"Security alert sent: {alert_type}")
            
        except Exception as e:
            logging.error(f"Failed to send security alert: {str(e)}")
    
    def export_security_report(self, hours=24):
        """보안 리포트 생성"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        events = [e for e in security_events if e['timestamp'] > cutoff_time]
        
        report = {
            'report_period': f"Last {hours} hours",
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_events': len(events),
                'unique_ips': len(set(e['client_ip'] for e in events)),
                'attack_types': dict(Counter(e['type'] for e in events)),
                'top_attacking_ips': dict(Counter(e['client_ip'] for e in events).most_common(10))
            },
            'events': [
                {
                    'timestamp': e['timestamp'].isoformat(),
                    'type': e['type'],
                    'client_ip': e['client_ip'],
                    'path': e['path'],
                    'details': e['details']
                }
                for e in events
            ]
        }
        
        return report

# 전역 모니터 인스턴스
security_monitor = SecurityMonitor() 