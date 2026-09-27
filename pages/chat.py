import streamlit as st
from openai import OpenAI

# 웹 페이지의 기본 설정
st.set_page_config(
    page_title="고등학교 물리 선생님",
    page_icon="⚛️"
)

st.title("⚛️ 친절한 물리 선생님")
st.caption("물리 개념에 대해 궁금한 점이 있다면 무엇이든 물어보세요!")

# 1. Claude API 키 불러오기
api_key = st.secrets.get("CLAUDE_API_KEY")

if not api_key:
    st.info(
        "API 키 설정이 필요합니다. "
        "`.streamlit/secrets.toml` 파일에 CLAUDE_API_KEY를 추가해 주세요."
    )
    st.stop()

# Claude의 OpenAI 호환 API 연결
client = OpenAI(
    api_key=api_key,
    base_url="https://api.anthropic.com/v1/"
)

# 2. AI 페르소나 설정
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "너는 고등학생에게 물리를 가르쳐주는 친절한 물리 선생님이야. "
        "물리 개념을 꼼꼼하고 이해하기 쉽게 설명해 줘. "
        "필요하면 공식과 예시를 사용하고, 어려운 내용은 단계별로 설명해 줘."
    )
}

# 3. 대화 내역 저장소 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 이전 대화 기록 화면에 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 처리
if user_input := st.chat_input("물리 개념이나 문제를 입력해 보세요..."):

    # 사용자 질문 화면에 표시
    with st.chat_message("user"):
        st.markdown(user_input)

    # 대화 기록에 저장
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # 6. Claude 답변 생성
    with st.chat_message("assistant"):
        try:
            full_conversation = (
                [SYSTEM_PROMPT]
                + st.session_state.messages
            )

            response_stream = client.chat.completions.create(
                model="claude-sonnet-4-5",
                messages=full_conversation,
                stream=True
            )

            # 실시간 출력
            full_response = st.write_stream(response_stream)

            # 답변 저장
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response
            })

        except Exception as e:
            st.warning(
                "응답을 가져오는 중에 문제가 발생했습니다. "
                "잠시 후 다시 시도해 주세요."
            )
