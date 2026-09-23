import os
import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (제목 및 아이콘)
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖")

st.title("🤖 친절한 정보 선생님")
st.caption("궁금한 점이 있다면 무엇이든 물어보세요!")

# 1. API 키 확인 및 OpenAI 클라이언트 초기화
# streamlit secrets에서 GEMINI_API_KEY를 가져옵니다.
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.info("API 키 설정이 필요합니다. `.streamlit/secrets.toml` 파일에 GEMINI_API_KEY를 입력해 주세요.")
    st.stop()

# OpenAI 라이브러리를 사용하여 Gemini API에 연결합니다.
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 2. 시스템 프롬프트(AI 성격 지정) 설정
# 화면에는 보이지 않으며 AI가 답할 때의 기본 지침이 됩니다.
SYSTEM_PROMPT = {
    "role": "system",
    "content": "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. 어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
}

# 3. 대화 내역(세션 상태) 저장소 초기화
# 화면이 다시 그려져도 대화 기록이 유지되도록 세션 상태를 사용합니다.
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 이전 대화 내역 화면에 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 처리
if user_input := st.chat_input("질문을 입력하세요..."):
    # 사용자가 입력한 메시지를 화면에 말풍선으로 표시
    with st.chat_message("user"):
        st.markdown(user_input)

    # 대화 기록에 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 6. AI 답변 생성 및 실시간 스트리밍 출력
    with st.chat_message("assistant"):
        try:
            # 시스템 프롬프트를 포함하여 지금까지의 모든 대화 내역을 API에 전달
            full_conversation = [SYSTEM_PROMPT] + st.session_state.messages

            # API 호출 (글자가 실시간으로 나오는 stream=True 설정)
            response_stream = client.chat.completions.create(
                model="gemini-3.5-flash-lite",
                messages=full_conversation,
                stream=True
            )

            # 실시간으로 생성되는 답변을 화면에 말풍선으로 출력
            full_response = st.write_stream(response_stream)

            # 완결된 답변을 대화 기록에 추가하여 기억 유지
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception:
            # API 요청 실패 시 예외 처리 (오류 창 대신 안내 문구 출력)
            st.warning("응답을 가져오는 중에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")
