"""
CrewAI 기반 이메일 처리 Agent 시스템
문의/예약 이메일을 자동으로 분석하고 응답을 생성하는 AI Agent 시스템
"""
import os
import json
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# CrewAI 임포트
try:
    from crewai import Agent, Task, Crew, Process
    from langchain_openai import ChatOpenAI
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    print("⚠️ CrewAI not installed. Email agent system will use fallback mode.")

# 언어 감지 라이브러리
try:
    from langdetect import detect, detect_langs
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("⚠️ langdetect not installed. Language detection will use fallback.")


@dataclass
class EmailAnalysisResult:
    """이메일 분석 결과"""
    is_spam: bool = False
    spam_reason: str = ""
    detected_language: str = "ko"
    sentiment: str = "neutral"
    sentiment_detail: str = ""
    ai_response: str = ""
    translated_message: str = ""
    success: bool = True
    error_message: str = ""


class EmailAgentSystem:
    """
    CrewAI 기반 이메일 처리 시스템
    
    Agent 구성:
    1. Content Validator - 스팸/악성 콘텐츠 검증
    2. Language Detector - 언어 감지
    3. Sentiment Analyzer - 감성 분석
    4. Response Generator - 응답 생성
    """
    
    # 스팸 키워드 목록
    SPAM_KEYWORDS = [
        # 마케팅/홍보
        '광고', '마케팅', '홍보', '판매', 'SEO', '검색엔진최적화', '백링크',
        '대출', '보험', '투자', '코인', '비트코인', '카지노', '도박',
        'promotion', 'marketing', 'advertisement', 'casino', 'gambling',
        'lottery', 'winner', 'prize', 'free money', 'earn money',
        # 비속어 (기본)
        '시발', '씨발', '개새끼', 'fuck', 'shit', 'damn',
    ]
    
    # 지원 언어
    SUPPORTED_LANGUAGES = {
        'ko': '한국어',
        'en': 'English',
        'ja': '日本語',
        'zh-cn': '中文',
        'zh': '中文'
    }
    
    def __init__(self):
        """에이전트 시스템 초기화"""
        self.openai_api_key = os.environ.get('OPENAI_API_KEY')
        
        if not self.openai_api_key:
            print("⚠️ OPENAI_API_KEY not set. AI features will be limited.")
        
        # LLM 설정
        if CREWAI_AVAILABLE and self.openai_api_key:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.7,
                api_key=self.openai_api_key
            )
            self._setup_agents()
        else:
            self.llm = None
            self.agents = {}
    
    def _setup_agents(self):
        """CrewAI 에이전트 설정"""
        # 1. 콘텐츠 검증 Agent
        self.content_validator = Agent(
            role='Content Validator',
            goal='이메일 내용이 정상적인 문의인지 스팸/광고인지 판단합니다',
            backstory='''당신은 이메일 콘텐츠 분석 전문가입니다. 
            스타일링 서비스 회사의 문의 이메일을 분석하여 
            정상적인 고객 문의와 스팸/광고/악성 콘텐츠를 구분합니다.
            비속어, 욕설, 무관한 마케팅 내용을 정확히 감지합니다.''',
            llm=self.llm,
            verbose=True
        )
        
        # 2. 언어 감지 Agent
        self.language_detector = Agent(
            role='Language Detector',
            goal='이메일의 작성 언어를 정확히 감지합니다',
            backstory='''당신은 다국어 전문가입니다.
            한국어, 영어, 일본어, 중국어를 정확히 구분합니다.
            혼합된 언어의 경우 주요 언어를 파악합니다.''',
            llm=self.llm,
            verbose=True
        )
        
        # 3. 감성 분석 Agent
        self.sentiment_analyzer = Agent(
            role='Sentiment Analyzer',
            goal='이메일의 톤과 감성을 분석합니다',
            backstory='''당신은 고객 커뮤니케이션 전문가입니다.
            고객의 감정 상태(긍정/중립/부정)와 
            커뮤니케이션 스타일(공식적/친근/급함 등)을 파악합니다.
            이를 통해 적절한 응답 톤을 결정하는 데 도움을 줍니다.''',
            llm=self.llm,
            verbose=True
        )
        
        # 4. 응답 생성 Agent
        self.response_generator = Agent(
            role='Response Generator',
            goal='고객 문의에 대한 전문적이고 친절한 응답을 생성합니다',
            backstory='''당신은 스타일그래퍼(Stylegrapher)의 고객 서비스 담당자입니다.
            스타일링 컨설팅, AI 분석, 원데이 스타일링, 프로필 촬영 서비스를 제공하는 
            전문 회사의 대표로서 고객에게 응답합니다.
            항상 친절하고 전문적이며, 고객의 요구에 맞는 정확한 정보를 제공합니다.
            제공된 RAG 컨텍스트를 활용하여 정확한 서비스 정보를 포함합니다.''',
            llm=self.llm,
            verbose=True
        )
        
        self.agents = {
            'validator': self.content_validator,
            'language': self.language_detector,
            'sentiment': self.sentiment_analyzer,
            'response': self.response_generator
        }
    
    def _check_spam_keywords(self, message: str) -> Tuple[bool, str]:
        """스팸 키워드 체크 (빠른 사전 검사)"""
        message_lower = message.lower()
        
        for keyword in self.SPAM_KEYWORDS:
            if keyword.lower() in message_lower:
                return True, f"스팸 키워드 감지: {keyword}"
        
        return False, ""
    
    def _detect_language_simple(self, text: str) -> str:
        """간단한 언어 감지 (langdetect 사용)"""
        if not LANGDETECT_AVAILABLE:
            return 'ko'  # 기본값
        
        try:
            detected = detect(text)
            # 중국어 통합
            if detected in ['zh-cn', 'zh-tw']:
                return 'zh'
            return detected
        except:
            return 'ko'
    
    def _analyze_sentiment_simple(self, message: str) -> Tuple[str, str]:
        """간단한 감성 분석 (키워드 기반)"""
        message_lower = message.lower()
        
        # 긍정 키워드
        positive_keywords = ['감사', '좋아', '훌륭', '만족', '기대', 'thank', 'great', 'excellent', 'happy', 'love']
        # 부정 키워드
        negative_keywords = ['불만', '실망', '화가', '불편', '문제', 'angry', 'disappointed', 'problem', 'issue', 'bad']
        # 급함 키워드
        urgent_keywords = ['급해', '빨리', '긴급', 'urgent', 'asap', 'immediately', 'soon']
        
        positive_count = sum(1 for k in positive_keywords if k in message_lower)
        negative_count = sum(1 for k in negative_keywords if k in message_lower)
        is_urgent = any(k in message_lower for k in urgent_keywords)
        
        # 감성 판단
        if negative_count > positive_count:
            sentiment = 'negative'
        elif positive_count > negative_count:
            sentiment = 'positive'
        else:
            sentiment = 'neutral'
        
        # 상세 톤
        detail = 'urgent' if is_urgent else 'formal'
        
        return sentiment, detail
    
    def process_email(
        self,
        name: str,
        email: str,
        phone: str,
        message: str,
        service_name: str = "",
        service_id: Optional[int] = None
    ) -> EmailAnalysisResult:
        """
        이메일 전체 처리 파이프라인
        
        Args:
            name: 문의자 이름
            email: 문의자 이메일
            phone: 문의자 전화번호
            message: 문의 내용
            service_name: 문의 서비스 이름
            service_id: 서비스 ID
        
        Returns:
            EmailAnalysisResult: 분석 결과
        """
        result = EmailAnalysisResult()
        
        try:
            # 1단계: 빠른 스팸 키워드 체크
            is_spam, spam_reason = self._check_spam_keywords(message)
            if is_spam:
                result.is_spam = True
                result.spam_reason = spam_reason
                print(f"🚫 스팸 감지 (키워드): {spam_reason}")
                return result
            
            # 2단계: 언어 감지
            result.detected_language = self._detect_language_simple(message)
            print(f"🌐 감지된 언어: {result.detected_language}")
            
            # 3단계: 간단한 감성 분석
            result.sentiment, result.sentiment_detail = self._analyze_sentiment_simple(message)
            print(f"💭 감성: {result.sentiment} ({result.sentiment_detail})")
            
            # CrewAI 사용 가능 시 고급 분석 및 응답 생성
            if CREWAI_AVAILABLE and self.llm:
                result = self._process_with_crewai(
                    result, name, email, phone, message, 
                    service_name, service_id
                )
            else:
                # Fallback: 직접 OpenAI API 사용
                result = self._process_with_openai_direct(
                    result, name, email, phone, message,
                    service_name, service_id
                )
            
            result.success = True
            
        except Exception as e:
            print(f"❌ 이메일 처리 오류: {str(e)}")
            result.success = False
            result.error_message = str(e)
        
        return result
    
    def _process_with_crewai(
        self,
        result: EmailAnalysisResult,
        name: str,
        email: str,
        phone: str,
        message: str,
        service_name: str,
        service_id: Optional[int]
    ) -> EmailAnalysisResult:
        """CrewAI를 사용한 고급 처리"""
        from utils.rag_context import get_service_specific_context, get_response_guidelines
        
        # RAG 컨텍스트 수집
        rag_context = get_service_specific_context(service_id)
        guidelines = get_response_guidelines()
        
        # Task 1: 스팸 검증 (더 정밀한 분석)
        validation_task = Task(
            description=f'''다음 이메일 내용이 정상적인 스타일링 서비스 문의인지 분석하세요.

이메일 내용:
{message}

문의 서비스: {service_name}

다음 기준으로 판단하세요:
1. 스팸/광고/마케팅 내용인가?
2. 비속어나 부적절한 표현이 포함되어 있는가?
3. 스타일링 서비스와 관련 없는 내용인가?

JSON 형식으로 응답하세요:
{{"is_spam": true/false, "reason": "판단 이유"}}''',
            agent=self.content_validator,
            expected_output='JSON 형식의 스팸 판단 결과'
        )
        
        # Task 2: 응답 생성
        response_task = Task(
            description=f'''다음 고객 문의에 대해 응답을 작성하세요.

고객 정보:
- 이름: {name}
- 이메일: {email}
- 전화번호: {phone}

문의 내용:
{message}

문의 서비스: {service_name}

감지된 언어: {result.detected_language}
감성: {result.sentiment} ({result.sentiment_detail})

=== 참고할 서비스 정보 (RAG Context) ===
{rag_context}

{guidelines}

응답 작성 시 주의사항:
1. 감지된 언어({result.detected_language})로 응답 작성
2. 감성({result.sentiment})에 맞는 톤 사용
3. RAG Context의 정확한 서비스 정보 활용
4. "스타일그래퍼 팀" 또는 해당 언어의 서명으로 마무리''',
            agent=self.response_generator,
            expected_output='고객 문의에 대한 응답 이메일'
        )
        
        # Crew 실행
        crew = Crew(
            agents=[self.content_validator, self.response_generator],
            tasks=[validation_task, response_task],
            process=Process.sequential,
            verbose=True
        )
        
        crew_result = crew.kickoff()
        
        # 결과 파싱
        try:
            # 응답 텍스트에서 결과 추출
            result_text = str(crew_result)
            
            # 스팸 판단 결과 파싱 시도
            if '"is_spam": true' in result_text.lower():
                result.is_spam = True
                result.spam_reason = "AI 분석에 의한 스팸 판단"
            
            # AI 응답 추출 (마지막 태스크 결과)
            result.ai_response = result_text
            
        except Exception as parse_error:
            print(f"⚠️ CrewAI 결과 파싱 오류: {parse_error}")
            result.ai_response = str(crew_result)
        
        return result
    
    def _process_with_openai_direct(
        self,
        result: EmailAnalysisResult,
        name: str,
        email: str,
        phone: str,
        message: str,
        service_name: str,
        service_id: Optional[int]
    ) -> EmailAnalysisResult:
        """OpenAI API 직접 사용 (CrewAI 대체)"""
        import openai
        from utils.rag_context import get_service_specific_context, get_response_guidelines
        
        if not self.openai_api_key:
            result.ai_response = self._generate_fallback_response(
                name, result.detected_language, service_name
            )
            return result
        
        client = openai.OpenAI(api_key=self.openai_api_key)
        
        # RAG 컨텍스트 수집
        rag_context = get_service_specific_context(service_id)
        guidelines = get_response_guidelines()
        
        # 1. 스팸 검증
        spam_check_prompt = f'''다음 이메일이 스팸인지 판단하세요.

이메일 내용:
{message}

문의 서비스: {service_name}

스타일링 서비스 회사에 대한 정상적인 문의가 아닌 경우 스팸으로 판단합니다.
(광고, 마케팅, 비속어, 무관한 내용 등)

JSON으로만 응답: {{"is_spam": true/false, "reason": "판단 이유"}}'''

        spam_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": spam_check_prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        try:
            spam_result = json.loads(spam_response.choices[0].message.content)
            result.is_spam = spam_result.get('is_spam', False)
            result.spam_reason = spam_result.get('reason', '')
        except:
            pass
        
        if result.is_spam:
            return result
        
        # 2. 언어별 응답 생성
        language_instruction = {
            'ko': '한국어로 응답하세요.',
            'en': 'Respond in English.',
            'ja': '日本語で返信してください。',
            'zh': '请用中文回复。'
        }.get(result.detected_language, '한국어로 응답하세요.')
        
        response_prompt = f'''당신은 스타일그래퍼(Stylegrapher)의 고객 서비스 담당자입니다.

고객 정보:
- 이름: {name}
- 이메일: {email}

문의 내용:
{message}

문의 서비스: {service_name}

고객 감성: {result.sentiment} ({result.sentiment_detail})

{language_instruction}

=== 참고할 서비스 정보 ===
{rag_context}

{guidelines}

친절하고 전문적인 응답을 작성하세요.'''

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": response_prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        
        result.ai_response = response.choices[0].message.content
        
        # 3. 한국어가 아닌 경우 번역본 생성
        if result.detected_language != 'ko':
            translate_prompt = f'''다음 텍스트를 한국어로 번역하세요. 원문의 의미를 정확히 전달하세요.

원문:
{message}

번역:'''
            
            translate_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": translate_prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            result.translated_message = translate_response.choices[0].message.content
        else:
            result.translated_message = message
        
        return result
    
    def _generate_fallback_response(
        self,
        name: str,
        language: str,
        service_name: str
    ) -> str:
        """AI 사용 불가 시 기본 응답 생성"""
        responses = {
            'ko': f'''안녕하세요, {name}님.

스타일그래퍼에 문의해 주셔서 감사합니다.

{service_name}에 관한 문의를 접수하였습니다.
담당자가 확인 후 빠른 시간 내에 연락 드리겠습니다.

감사합니다.
스타일그래퍼 팀 드림''',
            
            'en': f'''Dear {name},

Thank you for contacting Stylegrapher.

We have received your inquiry about {service_name}.
Our team will review and get back to you shortly.

Best regards,
Stylegrapher Team''',
            
            'ja': f'''{name}様

スタイルグラファーにお問い合わせいただきありがとうございます。

{service_name}に関するお問い合わせを受け付けました。
担当者が確認後、早急にご連絡いたします。

どうぞよろしくお願いいたします。
スタイルグラファーチーム''',
            
            'zh': f'''{name}您好，

感谢您联系Stylegrapher。

我们已收到您关于{service_name}的咨询。
我们的团队将尽快审核并与您联系。

此致敬礼，
Stylegrapher团队'''
        }
        
        return responses.get(language, responses['ko'])


# 싱글톤 인스턴스
_email_agent_system = None


def get_email_agent_system() -> EmailAgentSystem:
    """이메일 에이전트 시스템 싱글톤 인스턴스 반환"""
    global _email_agent_system
    if _email_agent_system is None:
        _email_agent_system = EmailAgentSystem()
    return _email_agent_system


def process_inquiry_email(
    name: str,
    email: str,
    phone: str,
    message: str,
    service_name: str = "",
    service_id: Optional[int] = None
) -> EmailAnalysisResult:
    """
    문의 이메일 처리 (편의 함수)
    
    Returns:
        EmailAnalysisResult: 분석 결과
    """
    system = get_email_agent_system()
    return system.process_email(
        name=name,
        email=email,
        phone=phone,
        message=message,
        service_name=service_name,
        service_id=service_id
    )



