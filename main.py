# -*- coding: utf-8 -*-
"""
어제의 일별 박스오피스를 보여주는 스트림릿 앱
- KOBIS(영화진흥위원회) 공식 Open API 사용
- 인증키는 코드에 직접 쓰지 않고, 스트림릿 비밀 금고(secrets)에서 불러옵니다.
  (Streamlit Cloud > Settings > Secrets 에 KOBIS_KEY = "발급받은키" 형태로 등록)
"""

import random  # '가볍게 아무거나' 기분일 때 랜덤 추천용 (파이썬 내장 모듈)
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # 파이썬 내장 시간대 모듈 (한국 시간 계산용)

# -----------------------------
# 0. 기본 설정
# -----------------------------
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")

API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 배우 정보·출연작 추천에 사용할 TMDb(The Movie Database) API 주소
# - TMDb 인증키도 코드에 쓰지 않고 st.secrets["TMDB_KEY"]에서 불러옵니다.
TMDB_API_URL = "https://api.themoviedb.org/3"


# -----------------------------
# 1. '어제' 날짜를 한국 시간(KST) 기준으로 계산
#    - 배포 서버의 시계가 한국 시간이 아닐 수 있으므로,
#      항상 Asia/Seoul 시간대를 명시해서 계산합니다.
# -----------------------------
def get_yesterday_kst_str() -> str:
    """한국 시간 기준 '어제' 날짜를 yyyymmdd 문자열로 반환"""
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday_kst = now_kst - timedelta(days=1)
    return yesterday_kst.strftime("%Y%m%d")


# -----------------------------
# 2. 숫자 문자열을 보기 좋게 콤마가 찍힌 문자열로 바꾸는 도우미 함수
#    - API 응답의 숫자 값은 전부 문자열("12345")로 오기 때문에
#      int로 바꾼 뒤 다시 콤마 포맷을 적용합니다.
# -----------------------------
def to_int_safe(value) -> int:
    """문자열을 정수로 안전하게 변환. 실패하면 0을 반환"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# -----------------------------
# 3. KOBIS API를 호출해서 박스오피스 목록을 가져오는 함수
#    - 네트워크 오류, 인증키 오류(faultInfo), 빈 목록 등
#      모든 실패 상황을 하나씩 확인하고, 실패 시 (None, 안내메시지)를 반환합니다.
# -----------------------------
def fetch_box_office(target_dt: str):
    # 3-1. 비밀 금고에서 인증키 불러오기
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except (KeyError, FileNotFoundError):
        return None, (
            "인증키(KOBIS_KEY)를 찾을 수 없습니다. "
            "스트림릿 클라우드의 앱 설정(Settings) > Secrets 메뉴에서 "
            'KOBIS_KEY = "발급받은키" 형태로 등록했는지 확인해 주세요.'
        )

    params = {"key": api_key, "targetDt": target_dt}

    # 3-2. 실제 요청 보내기 (네트워크 오류 대비)
    try:
        response = requests.get(API_URL, params=params, timeout=10)
    except requests.exceptions.Timeout:
        return None, "요청 시간이 초과되었습니다. 인터넷 연결 상태를 확인하고 다시 시도해 주세요."
    except requests.exceptions.RequestException:
        return None, "박스오피스 서버에 연결할 수 없습니다. 인터넷 연결 상태나 KOBIS 서버 상태를 확인해 주세요."

    # 3-3. 상태 코드 확인
    #      (문서에 따르면 인증키가 틀려도 상태코드는 200일 수 있으니, 이건 1차 점검용)
    if response.status_code != 200:
        return None, f"박스오피스 서버가 오류를 반환했습니다. (상태 코드: {response.status_code}) 잠시 후 다시 시도해 주세요."

    # 3-4. JSON 형식인지 확인
    try:
        data = response.json()
    except ValueError:
        return None, "서버 응답을 해석할 수 없습니다(JSON 형식이 아닙니다). KOBIS 서버 상태를 확인해 주세요."

    # 3-5. faultInfo 상자가 왔는지 확인 (주로 인증키 오류일 때 옴)
    if "faultInfo" in data:
        fault_msg = data["faultInfo"].get("message", "알 수 없는 오류")
        return None, (
            f"인증키 오류로 보입니다: {fault_msg} "
            "Secrets에 등록한 KOBIS_KEY 값이 정확한지, 발급받은 키가 맞는지 확인해 주세요."
        )

    # 3-6. 정상 구조(boxOfficeResult > dailyBoxOfficeList)인지 확인
    box_office_result = data.get("boxOfficeResult")
    if not box_office_result:
        return None, "응답에 boxOfficeResult가 없습니다. targetDt(조회 날짜) 값이나 API 주소가 올바른지 확인해 주세요."

    movie_list = box_office_result.get("dailyBoxOfficeList")
    if not movie_list:
        return None, (
            "해당 날짜의 박스오피스 목록이 비어 있습니다. "
            "아직 집계 전이거나(너무 이른 날짜), 조회 날짜(targetDt) 계산이 잘못되었을 수 있습니다."
        )

    return movie_list, None


# -----------------------------
# 3-2. TMDb API 도우미 함수들 (배우 출연작 추천 기능용)
#      - 모든 함수는 실패하면 None 또는 빈 리스트를 반환해서,
#        호출하는 쪽에서 앱이 멈추지 않고 안내 메시지를 보여줄 수 있게 합니다.
# -----------------------------
def tmdb_search_movie(title: str, api_key: str):
    """영화 한글 제목으로 TMDb에서 영화를 검색해서, 가장 가까운 결과 1건을 반환"""
    try:
        resp = requests.get(
            f"{TMDB_API_URL}/search/movie",
            params={"api_key": api_key, "query": title, "language": "ko-KR"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        return results[0] if results else None
    except requests.exceptions.RequestException:
        return None


def tmdb_get_movie_cast(movie_id: int, api_key: str, limit: int = 6):
    """TMDb 영화 id로 출연 배우 목록(상위 limit명)을 반환"""
    try:
        resp = requests.get(
            f"{TMDB_API_URL}/movie/{movie_id}/credits",
            params={"api_key": api_key, "language": "ko-KR"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("cast", [])[:limit]
    except requests.exceptions.RequestException:
        return []


def tmdb_get_person_movie_credits(person_id: int, api_key: str, limit: int = 6):
    """TMDb 배우 id로 그 배우의 다른 출연작을 인기도 순으로 반환"""
    try:
        resp = requests.get(
            f"{TMDB_API_URL}/person/{person_id}/movie_credits",
            params={"api_key": api_key, "language": "ko-KR"},
            timeout=10,
        )
        resp.raise_for_status()
        cast = resp.json().get("cast", [])
        cast_sorted = sorted(cast, key=lambda m: m.get("popularity", 0), reverse=True)
        return cast_sorted[:limit]
    except requests.exceptions.RequestException:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def build_actor_pool(movie_titles: tuple, api_key: str) -> dict:
    """현재 상영작 목록(영화 제목들)을 TMDb에서 검색해서,
    등장하는 배우 이름 -> TMDb 배우 id 매핑을 만들어 반환.
    같은 결과를 1시간 동안 캐시해서, 매번 새로고침해도 API를 너무 많이 부르지 않도록 함."""
    actor_map = {}
    for title in movie_titles:
        movie = tmdb_search_movie(title, api_key)
        if not movie:
            continue  # TMDb에서 못 찾은 영화는 건너뜀
        cast = tmdb_get_movie_cast(movie["id"], api_key)
        for actor in cast:
            name = actor.get("name")
            actor_id = actor.get("id")
            if name and actor_id and name not in actor_map:
                actor_map[name] = actor_id
    return actor_map


# -----------------------------
# 4. 화면 그리기 시작
# -----------------------------
st.title("🎬 어제의 일별 박스오피스")

target_dt = get_yesterday_kst_str()
target_dt_display = f"{target_dt[0:4]}-{target_dt[4:6]}-{target_dt[6:8]}"
st.caption(f"조회 날짜(한국 시간 기준 어제): {target_dt_display}")

movie_list, error_message = fetch_box_office(target_dt)

# 4-1. 실패했을 때: 빈 화면 대신 안내 문구를 보여줍니다.
if error_message:
    st.error(error_message)
    st.info(
        "확인해 보세요:\n"
        "1) Streamlit Cloud의 Secrets에 KOBIS_KEY가 올바르게 등록되어 있는지\n"
        "2) KOBIS에서 발급받은 인증키가 유효한지(만료/오타 여부)\n"
        "3) 인터넷 연결 및 KOBIS 서버 상태\n"
        "4) 새벽 시간대에는 전날 집계가 아직 올라오지 않았을 수 있습니다."
    )
    st.stop()  # 아래 코드는 실행하지 않고 여기서 멈춤

# -----------------------------
# 5. 데이터프레임으로 정리
# -----------------------------
rows = []
for movie in movie_list:
    rows.append(
        {
            "순위": to_int_safe(movie.get("rank")),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int_safe(movie.get("audiCnt")),
            "누적관객": to_int_safe(movie.get("audiAcc")),
            "스크린수": to_int_safe(movie.get("scrnCnt")),
        }
    )

df = pd.DataFrame(rows).sort_values("순위").reset_index(drop=True)

# -----------------------------
# 6. 1위 영화 지표 카드 3장
# -----------------------------
top1 = df.iloc[0]
st.subheader(f"🥇 1위: {top1['영화명']}")

col1, col2, col3 = st.columns(3)
col1.metric("어제 관객수", f"{top1['관객수']:,}명")
col2.metric("누적 관객수", f"{top1['누적관객']:,}명")
col3.metric("스크린수", f"{top1['스크린수']:,}개")

# -----------------------------
# 7. 전체 표 (콤마 포맷 적용)
# -----------------------------
st.subheader("📋 전체 순위")

df_display = df.copy()
df_display["관객수"] = df_display["관객수"].map(lambda x: f"{x:,}")
df_display["누적관객"] = df_display["누적관객"].map(lambda x: f"{x:,}")
df_display["스크린수"] = df_display["스크린수"].map(lambda x: f"{x:,}")

st.dataframe(df_display, use_container_width=True, hide_index=True)

# -----------------------------
# 8. 관객수 상위 5편 막대그래프
# -----------------------------
st.subheader("📊 관객수 상위 5편")

top5 = df.sort_values("관객수", ascending=False).head(5).set_index("영화명")
st.bar_chart(top5["관객수"])

# -----------------------------
# 9. 오늘의 기분에 따라 '지금 상영 중인 영화'(=어제 박스오피스에 오른 영화) 추천
#
#    ※ KOBIS 일별 박스오피스 API에는 장르 정보가 없어서(문서에 없는 필드는
#      임의로 만들어 쓰지 않았습니다), 장르 대신 실제로 제공되는 지표
#      (순위, 관객수, 스크린수, 누적관객수)의 '패턴'을 기분과 연결했습니다.
#      예: 스크린수는 적은데 관객수 비율이 높다 → 입소문으로 사랑받는 영화
# -----------------------------
st.divider()
st.subheader("🎭 오늘 기분에 맞는 영화 추천")
st.caption("아래 목록은 어제 박스오피스에 오른, 즉 지금 상영 중인 영화들입니다.")

mood = st.selectbox(
    "오늘 기분이 어떠세요?",
    [
        "신나고 활기찬 기분이에요",
        "잔잔하게 힐링하고 싶어요",
        "다 같이 볼 대중적인 영화가 필요해요",
        "이미 검증된 명작이 좋아요",
        "그냥 가볍게 아무거나 보고 싶어요",
    ],
)

if st.button("추천 받기"):
    # 스크린수가 0이면 나누기 오류가 나므로, 0인 경우는 계산에서 제외
    df_calc = df[df["스크린수"] > 0].copy()

    if mood == "신나고 활기찬 기분이에요":
        # 어제 관객수가 가장 많은, 지금 가장 화제인 영화
        pick = df_calc.sort_values("관객수", ascending=False).iloc[0]
        reason = "어제 관객수가 가장 많아서 지금 가장 화제가 되고 있는 영화예요."

    elif mood == "잔잔하게 힐링하고 싶어요":
        # 스크린수 대비 관객수 비율(회전율)이 높은 영화 = 큰 규모는 아니지만 입소문으로 사랑받는 영화
        df_calc["좌석회전율"] = df_calc["관객수"] / df_calc["스크린수"]
        pick = df_calc.sort_values("좌석회전율", ascending=False).iloc[0]
        reason = "상영관 수 대비 관객 비율이 높아서, 입소문으로 잔잔하게 사랑받고 있는 영화예요."

    elif mood == "다 같이 볼 대중적인 영화가 필요해요":
        # 스크린수가 가장 많은 영화 = 가장 대중적으로 넓게 상영 중인 영화
        pick = df_calc.sort_values("스크린수", ascending=False).iloc[0]
        reason = "상영 스크린수가 가장 많아서, 어디서든 쉽게 함께 볼 수 있는 영화예요."

    elif mood == "이미 검증된 명작이 좋아요":
        # 누적관객수가 가장 많은 영화 = 오랫동안 많은 사람이 본 영화
        pick = df_calc.sort_values("누적관객", ascending=False).iloc[0]
        reason = "누적 관객수가 가장 많아서, 이미 많은 사람들에게 검증된 영화예요."

    else:  # 그냥 가볍게 아무거나 보고 싶어요
        # 매번 누를 때마다 무작위로 한 편 선택
        pick = df_calc.sample(n=1).iloc[0]
        reason = "오늘의 기분을 위해 무작위로 골라본 영화예요."

    st.success(f"오늘의 추천 영화: **{pick['영화명']}**")
    st.write(reason)

    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("순위", f"{int(pick['순위'])}위")
    r_col2.metric("어제 관객수", f"{int(pick['관객수']):,}명")
    r_col3.metric("누적 관객수", f"{int(pick['누적관객']):,}명")
    r_col4.metric("스크린수", f"{int(pick['스크린수']):,}개")

# -----------------------------
# 10. 현재 상영작에 나온 배우 선택 → 그 배우의 다른 출연작 추천
#     - KOBIS API에는 배우 정보가 없어서, 배우 검색·출연작 조회는
#       TMDb(The Movie Database) API를 추가로 사용합니다.
#     - TMDb 인증키도 코드에 쓰지 않고 st.secrets["TMDB_KEY"]에서 불러옵니다.
#       (Streamlit Cloud Secrets에 TMDB_KEY = "TMDb에서 발급받은 키" 로 등록)
# -----------------------------
st.divider()
st.subheader("🧑‍🎤 배우로 다른 영화 찾기")
st.caption("현재 상영작에 나온 배우를 고르면, TMDb 데이터로 그 배우의 다른 출연작을 추천합니다.")

try:
    tmdb_api_key = st.secrets["TMDB_KEY"]
except (KeyError, FileNotFoundError):
    tmdb_api_key = None
    st.warning(
        "TMDb 인증키(TMDB_KEY)가 등록되어 있지 않아 이 기능을 사용할 수 없습니다. "
        "Streamlit Cloud의 Settings > Secrets에 TMDB_KEY를 추가해 주세요."
    )

if tmdb_api_key:
    # 현재 상영작(어제 박스오피스) 제목들로 배우 목록을 만듭니다.
    movie_titles = tuple(df["영화명"].tolist())

    with st.spinner("현재 상영작의 배우 정보를 불러오는 중..."):
        actor_map = build_actor_pool(movie_titles, tmdb_api_key)

    if not actor_map:
        st.info(
            "TMDb에서 현재 상영작의 배우 정보를 찾지 못했습니다. "
            "TMDb 인증키가 올바른지, 또는 영화 제목이 TMDb 검색 결과와 다른 건 아닌지 확인해 주세요."
        )
    else:
        selected_actor = st.selectbox("배우를 선택하세요", sorted(actor_map.keys()))

        if selected_actor:
            person_id = actor_map[selected_actor]
            with st.spinner(f"{selected_actor}의 출연작을 찾는 중..."):
                credits_list = tmdb_get_person_movie_credits(person_id, tmdb_api_key)

            if not credits_list:
                st.info(f"TMDb에서 {selected_actor}의 다른 출연작을 찾지 못했습니다.")
            else:
                st.write(f"**{selected_actor}**의 다른 출연작 추천")
                credit_cols = st.columns(len(credits_list))
                for col, movie in zip(credit_cols, credits_list):
                    poster_path = movie.get("poster_path")
                    movie_title = movie.get("title") or movie.get("original_title") or "제목 미상"
                    release_date = movie.get("release_date", "")
                    release_year = release_date[:4] if release_date else "?"
                    with col:
                        if poster_path:
                            st.image(f"https://image.tmdb.org/t/p/w200{poster_path}")
                        else:
                            st.write("🎬 포스터 없음")
                        st.caption(f"{movie_title} ({release_year})")
