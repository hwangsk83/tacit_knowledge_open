from google import genai
from google.genai import types
import json

class GeminiAPIService:
    def __init__(self, api_key: str = None):
        """
        Gemini API 서비스를 초기화합니다.
        api_key가 제공되지 않으면 환경변수(GEMINI_API_KEY)에서 로드합니다.
        """
        if not api_key:
            import os
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY API 키가 제공되지 않았습니다.")
            
        # 최신 google-genai SDK 클라이언트 초기화
        self.client = genai.Client(api_key=api_key)

    def compile_constraint(self, comment: str, entity_info: dict) -> dict:
        """
        사용자의 코멘트와 기하 피처 속성을 분석하여
        기하학적 제약조건 JSON 구조화 규칙 데이터를 컴파일합니다.
        가장 최신의 gemini-2.5-flash를 시작으로 순차적으로 하위 호환 모델로 Fallback을 시도하여
        API 키 권한별 404 에러를 방지합니다.
        """
        prompt = f"""
        너는 20년 경력의 대한민국 기구설계, 사출 금형 및 가공 제조 전문가다.
        아래 입력된 도면 개체 기하 정보[Entity Info]와 엔지니어의 설계 노하우 코멘트[Design Comment]를 종합 분석해라.
        그리고 이 설계 노하우를 CAD 시스템이나 DFM 검증 엔진이 바로 파싱해 사용할 수 있도록 정형화된 JSON 규칙 코드로 변환해라.

        반드시 다른 답변 텍스트는 작성하지 말고, JSON 데이터 포맷 자체만 리턴해야 한다.
        의사결정 이유(rationale)는 한국어로 상세히 서술해라.

        [Entity Info]
        {json.dumps(entity_info, ensure_ascii=False)}

        [Design Comment]
        {comment}
        """

        # 지원 모델 리스트 순서대로 스캔 (404 발생 시 즉각 다음 모델로 Fallback)
        candidate_models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.5-pro', 'gemini-1.5-pro']
        last_exception = None

        for model_name in candidate_models:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Structured Output 설정을 통해 응답 형식을 JSON으로 강제
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )

                    response_text = response.text.strip()
                    return json.loads(response_text)

                except json.JSONDecodeError as e:
                    # AI 응답이 예외적으로 오염되었을 경우에 대한 방어적 파싱 처리
                    raise ValueError(f"Gemini API가 규격에 맞지 않는 데이터를 리턴했습니다: {e}. 응답원문: {response_text}")
                except Exception as e:
                    last_exception = e
                    err_msg = str(e)
                    
                    # 404 NOT_FOUND인 경우 해당 모델에 권한이 없는 것이므로 즉시 다음 모델로 진행 (재시도 생략)
                    if "NOT_FOUND" in err_msg or "404" in err_msg or "not found" in err_msg.lower():
                        break
                        
                    # 일시적 오류(429, 5xx)인 경우 지수 백오프 대기
                    if attempt == max_retries - 1:
                        break # 재시도 횟수 초과 시 다음 모델 탐색
                    import time
                    time.sleep(2 ** attempt) # Exponential backoff

        raise ValueError(f"모든 Gemini 모델 후보 호출에 실패했습니다. 최종 에러: {last_exception}")
