import streamlit as st
from openai import OpenAI

# 웹 페이지의 기본 설정 (타이틀 및 아이콘)
st.set_page_config(page_title="고등학교 물리 선생님", page_icon="⚛️")

st.title("⚛️ 친절한 물리 선생님")
st.caption("물리 개념에 대해 궁금한 점이 있다면 무엇이든 물어보세요!")

# 1. API 키 불러오기 및 클라이언트 초기화
# Streamlit 비밀 금고(secrets)에서 GEMINI_API_KEY를 안전하게 가져옵니다.
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.info("API 키 설정이 필요합니다. `.streamlit/secrets.toml` 파일에 GEMINI_API_KEY를 추가해 주세요.")
    st.stop()

# OpenAI 라이브러리를 사용해 Gemini OpenAI 호환 API 주소로 연결합니다.
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 2. AI 페르소나(성격) 설정
# 시스템 프롬프트를 통해 AI 역할을 부여합니다. (화면에는 출력되지 않습니다)
SYSTEM_PROMPT = {
    "role": "system",
    "content": "너는 고등학생에게 물리를 가르쳐주는 물리 선생님이야. 개념을 꼼꼼하게 설명해 줘."
}

# 3. 대화 내역(세션 상태) 저장소 초기화
# 페이지가 다시 로드되어도 이전 질문과 답변을 기억하도록 저장소를 만듭니다.
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 이전 대화 기록 화면에 출력
# 대화 기록에 저장된 메시지들을 하나씩 말풍선 형태로 보여줍니다.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 채팅 입력 처리
if user_input := st.chat_input("물리 개념이나 문제를 입력해 보세요..."):
    # 사용자가 입력한 메시지를 즉시 화면 말풍선으로 표시
    with st.chat_message("user"):
        st.markdown(user_input)

    # 대화 기록에 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 6. AI 답변 생성 및 실시간 스트리밍 출력
    with st.chat_message("assistant"):
        try:
            # 시스템 역할(성격) 설정과 지금까지의 이전 대화 기록 전체를 함께 전달합니다.
            full_conversation = [SYSTEM_PROMPT] + st.session_state.messages

            # API 호출 (stream=True를 설정하여 글자가 실시간으로 출력되게 함)
            response_stream = client.chat.completions.create(
                model="gemini-3.5-flash-lite",
                messages=full_conversation,
                stream=True
            )

            # Streamlit의 write_stream을 사용하여 글자가 차례대로 흘러나오게 표출
            full_response = st.write_stream(response_stream)

            # 완성된 답변을 다음 대화 상맥을 위해 대화 기록에 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception:
            # API 요청 실패 시 빨간 오류 화면 대신 아래 한국어 문구 한 줄만 출력
            st.warning("응답을 가져오는 중에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")
