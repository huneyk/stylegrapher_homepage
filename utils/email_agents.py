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
    is_irrelevant: bool = False  # RAG 파일과 관련 없는 내용인지
    irrelevant_reason: str = ""  # 관련 없는 내용 판단 이유
    irrelevant_response: str = ""  # 관련 없는 내용에 대한 간략한 회신
    detected_language: str = "ko"
    sentiment: str = "neutral"
    sentiment_detail: str = ""
    ai_response: str = ""
    translated_message: str = ""
    translated_ai_response: str = ""  # AI 응답의 한국어 번역
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
        # 1. 콘텐츠 검증 Agent - RAG 파일 기반 관련성 검증
        self.content_validator = Agent(
            role='Content Validator',
            goal='이메일 내용을 RAG 컨텍스트(회사 서비스 정보)와 비교하여 관련성을 판단하고, 스팸/광고 여부를 검증합니다',
            backstory='''당신은 이메일 콘텐츠 분석 전문가입니다.
            스타일그래퍼의 RAG 파일(서비스 정보, 회사 정보, 정책 등)을 기준으로
            접수된 이메일이 실제 서비스와 관련된 문의인지 판단합니다.
            
            분석 기준:
            1. RAG 컨텍스트에 포함된 서비스(AI 분석, 스타일링 컨설팅, 원데이 스타일링, 프로필 촬영)와의 관련성
            2. 스팸/광고/악성 콘텐츠 여부 (비속어, 욕설, 무관한 마케팅)
            3. 회사의 업무 범위(개인 스타일링, 이미지 컨설팅, 프로필 사진 촬영)와의 연관성
            
            RAG 파일에 없는 내용이나 서비스 범위를 벗어난 문의는 "irrelevant"로 분류합니다.''',
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
        import openai
        from utils.rag_context import get_service_specific_context, get_response_guidelines
        
        # RAG 컨텍스트 수집
        rag_context = get_service_specific_context(service_id)
        guidelines = get_response_guidelines()
        
        # Task 1: RAG 파일 기반 스팸 및 관련성 검증
        validation_task = Task(
            description=f'''다음 이메일 내용을 아래 RAG 컨텍스트(회사 서비스 정보)와 비교하여 관련성을 분석하세요.

=== 접수된 이메일 내용 ===
{message}

문의 서비스: {service_name}

=== RAG 컨텍스트 (스타일그래퍼 서비스/회사 정보) ===
{rag_context}

=== 분류 기준 ===
이메일 내용이 위 RAG 컨텍스트에 포함된 서비스/업무와 관련이 있는지 비교 분석하세요.

1. "spam": 광고, 마케팅, 비속어, 욕설, 사기성 내용 등 명백한 스팸
2. "irrelevant": 스팸은 아니지만 RAG 컨텍스트의 서비스 범위에 해당하지 않는 문의
   - RAG 파일에 없는 서비스 문의
   - 스타일링/이미지 컨설팅/프로필 촬영과 무관한 내용
   - 회사 업무 범위를 벗어난 요청
3. "valid": RAG 컨텍스트의 서비스와 관련된 정상적인 문의
   - 서비스 안내, 가격, 예약 관련 문의
   - RAG 파일에 포함된 서비스에 대한 질문

JSON 형식으로 응답하세요:
{{"classification": "spam/irrelevant/valid", "reason": "RAG 컨텍스트와 비교한 판단 근거"}}''',
            agent=self.content_validator,
            expected_output='JSON 형식의 콘텐츠 분류 결과 (RAG 파일 기반 관련성 판단 포함)'
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
4. 응답 마지막 부분(서명 직전)에 다음 안내 문구를 반드시 포함:
   - 한국어: "필요한 경우 더 정확하고 자세한 안내를 위해 담당자가 추가로 연락 드리겠습니다."
   - 영어: "If needed, our staff will contact you for more accurate and detailed assistance."
   - 일본어: "必要に応じて、より正確で詳しいご案内のため、担当者から追加でご連絡させていただきます。"
   - 중국어: "如有需要，我们的工作人员将与您联系，为您提供更准确、更详细的帮助。"
5. "스타일그래퍼 팀" 또는 해당 언어의 서명으로 마무리''',
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
            import openai
            # 응답 텍스트에서 결과 추출
            result_text = str(crew_result)
            
            # 분류 결과 파싱 시도 - JSON에서 reason 추출
            import re
            reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', result_text)
            parsed_reason = reason_match.group(1) if reason_match else ""
            
            if '"classification": "spam"' in result_text.lower() or '"classification":"spam"' in result_text.lower():
                result.is_spam = True
                result.spam_reason = parsed_reason or "AI 분석에 의한 스팸 판단"
                print(f"🚫 스팸 감지 (CrewAI): {result.spam_reason}")
                return result
            elif '"classification": "irrelevant"' in result_text.lower() or '"classification":"irrelevant"' in result_text.lower():
                result.is_irrelevant = True
                result.irrelevant_reason = parsed_reason or "RAG 컨텍스트와 비교 결과 관련 없는 내용으로 판단"
                print(f"⚠️ 관련 없는 내용 감지 (RAG 비교): {result.irrelevant_reason}")
                # 관련 없는 내용에 대한 간략한 회신 생성
                result.irrelevant_response = self._generate_irrelevant_response(
                    name, result.detected_language
                )
                result.ai_response = result.irrelevant_response
                
                # 번역 처리
                if result.detected_language != 'ko' and self.openai_api_key:
                    client = openai.OpenAI(api_key=self.openai_api_key)
                    result.translated_message = self._translate_to_korean(client, message)
                    result.translated_ai_response = self._translate_to_korean(client, result.irrelevant_response)
                else:
                    result.translated_message = message
                    result.translated_ai_response = result.irrelevant_response
                return result
            
            # AI 응답 추출 (마지막 태스크 결과)
            result.ai_response = result_text
            
        except Exception as parse_error:
            print(f"⚠️ CrewAI 결과 파싱 오류: {parse_error}")
            result.ai_response = str(crew_result)
        
        # 한국어가 아닌 경우 번역본 생성 (OpenAI API 직접 사용)
        if result.detected_language != 'ko' and self.openai_api_key:
            try:
                client = openai.OpenAI(api_key=self.openai_api_key)
                
                # 고객 메시지 번역
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
                print(f"✅ 고객 메시지 번역 완료: {result.detected_language} → 한국어")
                
                # AI 응답 번역 (외국어로 작성된 경우)
                if result.ai_response:
                    translate_ai_prompt = f'''다음 AI 응답을 한국어로 번역하세요. 원문의 의미를 정확히 전달하세요.

원문:
{result.ai_response}

번역:'''
                    
                    translate_ai_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": translate_ai_prompt}],
                        temperature=0.3,
                        max_tokens=1000
                    )
                    
                    result.translated_ai_response = translate_ai_response.choices[0].message.content
                    print(f"✅ AI 응답 번역 완료: {result.detected_language} → 한국어")
                
            except Exception as translate_error:
                print(f"⚠️ 번역 오류: {translate_error}")
                result.translated_message = f"[번역 실패] 원문: {message}"
                result.translated_ai_response = f"[번역 실패] 원문: {result.ai_response}"
        else:
            result.translated_message = message
            result.translated_ai_response = result.ai_response
        
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
        
        # 1. RAG 파일 기반 스팸 및 관련성 검증
        content_check_prompt = f'''다음 이메일 내용을 RAG 컨텍스트(회사 서비스 정보)와 비교하여 관련성을 분석하세요.

=== 접수된 이메일 내용 ===
{message}

문의 서비스: {service_name}

=== RAG 컨텍스트 (스타일그래퍼 서비스/회사 정보) ===
{rag_context}

=== 분류 기준 ===
이메일 내용이 위 RAG 컨텍스트에 포함된 서비스/업무와 관련이 있는지 비교 분석하세요.

1. "spam": 광고, 마케팅, 비속어, 욕설, 사기성 내용 등 명백한 스팸
2. "irrelevant": 스팸은 아니지만 RAG 컨텍스트의 서비스 범위에 해당하지 않는 문의
   - RAG 파일에 없는 서비스 문의 (예: 웹개발, 배달, 금융 등)
   - 스타일링/이미지 컨설팅/프로필 촬영과 무관한 내용
   - 회사 업무 범위를 벗어난 요청
3. "valid": RAG 컨텍스트의 서비스와 관련된 정상적인 문의
   - 서비스 안내, 가격, 예약 관련 문의
   - RAG 파일에 포함된 서비스에 대한 질문

JSON으로만 응답: {{"classification": "spam/irrelevant/valid", "reason": "RAG 컨텍스트와 비교한 판단 근거"}}'''

        content_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content_check_prompt}],
            temperature=0.3,
            max_tokens=200
        )
        
        try:
            content_result = json.loads(content_response.choices[0].message.content)
            classification = content_result.get('classification', 'valid')
            reason = content_result.get('reason', '')
            
            if classification == 'spam':
                result.is_spam = True
                result.spam_reason = reason
                print(f"🚫 스팸 감지 (AI): {reason}")
                return result
            elif classification == 'irrelevant':
                result.is_irrelevant = True
                result.irrelevant_reason = reason
                print(f"⚠️ 관련 없는 내용 감지 (RAG 비교): {reason}")
                # 관련 없는 내용에 대한 간략한 회신 생성
                result.irrelevant_response = self._generate_irrelevant_response(
                    name, result.detected_language
                )
                result.ai_response = result.irrelevant_response
                result.translated_ai_response = result.irrelevant_response if result.detected_language == 'ko' else self._translate_to_korean(client, result.irrelevant_response)
                result.translated_message = message if result.detected_language == 'ko' else self._translate_to_korean(client, message)
                return result
        except Exception as parse_error:
            print(f"⚠️ 콘텐츠 분류 파싱 오류: {parse_error}")
            pass
        
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

응답 마지막 부분(서명 직전)에 다음 안내 문구를 반드시 포함하세요:
- 한국어: "필요한 경우 더 정확하고 자세한 안내를 위해 담당자가 추가로 연락 드리겠습니다."
- 영어: "If needed, our staff will contact you for more accurate and detailed assistance."
- 일본어: "必要に応じて、より正確で詳しいご案内のため、担当者から追加でご連絡させていただきます。"
- 중국어: "如有需要，我们的工作人员将与您联系，为您提供更准确、更详细的帮助。"

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
            # 고객 메시지 번역
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
            print(f"✅ 고객 메시지 번역 완료: {result.detected_language} → 한국어")
            
            # AI 응답 번역 (외국어로 작성된 경우)
            if result.ai_response:
                translate_ai_prompt = f'''다음 AI 응답을 한국어로 번역하세요. 원문의 의미를 정확히 전달하세요.

원문:
{result.ai_response}

번역:'''
                
                translate_ai_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": translate_ai_prompt}],
                    temperature=0.3,
                    max_tokens=1000
                )
                
                result.translated_ai_response = translate_ai_response.choices[0].message.content
                print(f"✅ AI 응답 번역 완료: {result.detected_language} → 한국어")
        else:
            result.translated_message = message
            result.translated_ai_response = result.ai_response
        
        return result
    
    def _generate_irrelevant_response(self, name: str, language: str) -> str:
        """관련 없는 내용에 대한 간략한 회신 생성"""
        responses = {
            'ko': f'''안녕하세요, {name}님.

스타일그래퍼에 연락해 주셔서 감사합니다.

죄송합니다만, 문의해 주신 내용은 저희 회사의 서비스 범위와 관련이 없어 특별히 안내드릴 사항이 없습니다.

저희는 스타일링 컨설팅, AI 스타일 분석, 원데이 스타일링, 프로필 촬영 서비스를 제공하고 있습니다.
관련 문의가 있으시면 언제든지 연락 주세요.

필요한 경우 더 정확하고 자세한 안내를 위해 담당자가 추가로 연락 드리겠습니다.

감사합니다.
스타일그래퍼 팀 드림''',
            
            'en': f'''Dear {name},

Thank you for contacting Stylegrapher.

We apologize, but the content of your inquiry is not related to our company's services, so we are unable to provide any specific assistance.

We offer styling consulting, AI style analysis, one-day styling, and profile photography services.
Please feel free to contact us if you have any related inquiries.

If needed, our staff will contact you for more accurate and detailed assistance.

Best regards,
Stylegrapher Team''',
            
            'ja': f'''{name}様

スタイルグラファーにお問い合わせいただきありがとうございます。

申し訳ございませんが、お問い合わせいただいた内容は弊社のサービス範囲と関連がないため、特にご案内できる事項がございません。

弊社はスタイリングコンサルティング、AIスタイル分析、ワンデースタイリング、プロフィール撮影サービスを提供しております。
関連するお問い合わせがございましたら、いつでもご連絡ください。

必要に応じて、より正確で詳しいご案内のため、担当者から追加でご連絡させていただきます。

どうぞよろしくお願いいたします。
スタイルグラファーチーム''',
            
            'zh': f'''{name}您好，

感谢您联系Stylegrapher。

非常抱歉，您咨询的内容与我们公司的服务范围无关，因此我们无法提供具体的帮助。

我们提供造型咨询、AI风格分析、一日造型、个人写真服务。
如有相关咨询，请随时联系我们。

如有需要，我们的工作人员将与您联系，为您提供更准确、更详细的帮助。

此致敬礼，
Stylegrapher团队'''
        }
        
        return responses.get(language, responses['ko'])
    
    def _translate_to_korean(self, client, text: str) -> str:
        """텍스트를 한국어로 번역"""
        try:
            translate_prompt = f'''다음 텍스트를 한국어로 번역하세요. 원문의 의미를 정확히 전달하세요.

원문:
{text}

번역:'''
            
            translate_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": translate_prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            return translate_response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ 번역 오류: {e}")
            return f"[번역 실패] 원문: {text}"
    
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

필요한 경우 더 정확하고 자세한 안내를 위해 담당자가 추가로 연락 드리겠습니다.

감사합니다.
스타일그래퍼 팀 드림''',
            
            'en': f'''Dear {name},

Thank you for contacting Stylegrapher.

We have received your inquiry about {service_name}.
Our team will review and get back to you shortly.

If needed, our staff will contact you for more accurate and detailed assistance.

Best regards,
Stylegrapher Team''',
            
            'ja': f'''{name}様

スタイルグラファーにお問い合わせいただきありがとうございます。

{service_name}に関するお問い合わせを受け付けました。
担当者が確認後、早急にご連絡いたします。

必要に応じて、より正確で詳しいご案内のため、担当者から追加でご連絡させていただきます。

どうぞよろしくお願いいたします。
スタイルグラファーチーム''',
            
            'zh': f'''{name}您好，

感谢您联系Stylegrapher。

我们已收到您关于{service_name}的咨询。
我们的团队将尽快审核并与您联系。

如有需要，我们的工作人员将与您联系，为您提供更准确、更详细的帮助。

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




