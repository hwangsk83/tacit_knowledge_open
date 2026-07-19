import streamlit as st
import matplotlib.pyplot as plt
import os
import tempfile
import json
import pandas as pd

from services.geometry_service import DXFGeometryService
from services.xdata_service import DXFXDataService
from services.gemini_service import GeminiAPIService
from infrastructure.file_repo import FileRepository
from utils.logger import get_logger

st.set_page_config(page_title="TacitBridge-DXF", layout="wide")

# 1. 의존성 객체 초기화 (세션 캐시 활용)
@st.cache_resource
def init_services():
    logger = get_logger()
    repo = FileRepository()
    geom_service = DXFGeometryService()
    xdata_service = DXFXDataService()
    return logger, repo, geom_service, xdata_service

logger, repo, geom_service, xdata_service = init_services()

logger.info("웹 UI 로드됨.")

# 2. 사이드바 - API Key 및 환경 설정
st.sidebar.title("⚙️ 설정 및 API 키")
api_key_input = st.sidebar.text_input("Gemini API Key", type="password", help="구글 Gemini API 키를 입력하세요. 미입력 시 시스템 환경변수(GEMINI_API_KEY)를 사용합니다.")

# 3. 메인 레이아웃 구성
st.title("🛠️ TacitBridge-DXF")
st.caption("대한민국 제조 기술유산 보존 프로젝트 - 암묵지 내장형 DXF 도면 편집기")

uploaded_file = st.file_uploader("2D DXF 도면 파일을 업로드하세요", type=["dxf"])

if uploaded_file:
    # 세션 상태(Session State)를 활용한 파일 파싱 결과 캐싱
    if "last_uploaded_name" not in st.session_state or st.session_state.last_uploaded_name != uploaded_file.name:
        st.session_state.last_uploaded_name = uploaded_file.name
        logger.info(f"새 파일 업로드 감지 및 파싱: {uploaded_file.name}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
            
        try:
            doc = geom_service.load_dxf(tmp_path)
            circles = geom_service.get_all_circles(doc)
            
            st.session_state.doc = doc
            st.session_state.circles = circles
            st.session_state.tmp_path = tmp_path
            st.session_state.compiled_rule = None # 파일 변경 시 기존 컴파일된 룰 리셋
            logger.info("DXF 파싱 성공 및 메모리 캐싱 완료.")
        except Exception as e:
            st.error(f"도면 로드 에러: {e}")
            logger.error(f"도면 로드 에러: {e}")
            st.stop()

    # 캐시된 도면 데이터 로드
    doc = st.session_state.doc
    circles = st.session_state.circles
            
    if not circles:
        st.warning("도면 내에 분석 가능한 원(CIRCLE) 개체가 존재하지 않습니다.")
        logger.warning("원 개체 없음 경고.")
    else:
        # 4. 화면 분할 (좌측 도면 플롯 / 우측 암묵지 입력)
        col_plot, col_control = st.columns([0.5, 0.5])
        
        with st.sidebar:
            st.subheader("📍 개체 선택")
            selection_mode = st.radio("선택 방식", ["목록에서 선택 (Dropdown)", "좌표로 탐색 (X, Y)"])
            
            if selection_mode == "목록에서 선택 (Dropdown)":
                circle_options = [f"Handle: {c['handle']} | 위치: ({c['center_x']:.1f}, {c['center_y']:.1f}) | 반경: {c['radius']:.1f}" for c in circles]
                selected_index = st.selectbox("어노테이션을 작성할 개체를 선택하세요", range(len(circle_options)), format_func=lambda x: circle_options[x])
                selected_circle = circles[selected_index]
            else:
                st.write("도면에서 탐색할 클릭 좌표(가상)를 입력하세요:")
                col_x, col_y = st.columns(2)
                click_x = col_x.number_input("X 좌표", value=0.0)
                click_y = col_y.number_input("Y 좌표", value=0.0)
                
                nearest_ent, nearest_info, dist = geom_service.find_nearest_entity(click_x, click_y, doc)
                if nearest_info:
                    st.success(f"최근접 개체 발견 (거리: {dist:.2f})")
                    selected_circle = {
                        "handle": nearest_info["handle"],
                        "center_x": nearest_info["center"]["x"],
                        "center_y": nearest_info["center"]["y"],
                        "radius": nearest_info["radius"]
                    }
                else:
                    st.warning("임계값 내에 근접 개체가 없습니다. 목록의 첫 번째 개체를 임의 선택합니다.")
                    selected_circle = circles[0]
            
        # 좌측: 도면 시각화 및 선택 개체 하이라이트
        with col_plot:
            st.subheader("📐 도면 형상 및 선택 영역")
            fig, ax = plt.subplots(figsize=(6, 6))
            
            # 모든 LINE 그리기 (시각화 목적이므로 ezdxf 직접 접근 허용)
            for line in doc.modelspace().query('LINE'):
                ax.plot([line.dxf.start.x, line.dxf.end.x], [line.dxf.start.y, line.dxf.end.y], color="grey", alpha=0.5, linewidth=1)
            
            # 모든 CIRCLE 그리기 (선택된 것은 빨강색, 나머지는 파랑색)
            for c in circles:
                color = "red" if c['handle'] == selected_circle['handle'] else "blue"
                linewidth = 2.5 if c['handle'] == selected_circle['handle'] else 1.0
                circle_patch = plt.Circle((c['center_x'], c['center_y']), c['radius'], color=color, fill=False, linewidth=linewidth)
                ax.add_patch(circle_patch)
            
            ax.set_aspect('equal', adjustable='datalim')
            ax.grid(True, linestyle="--", alpha=0.5)
            st.pyplot(fig)
            
        # 우측: 암묵지 어노테이션 작성 영역
        with col_control:
            st.subheader("💡 암묵지 지식 주입 및 변환")
            st.info(f"선택된 개체 속성: Handle=`{selected_circle['handle']}`, 반경=`{selected_circle['radius']:.2f}`")
            
            # 기존 데이터 주입 정보가 있는지 조회 (Service 계층 활용)
            existing_xdata = None
            try:
                existing_xdata = xdata_service.get_xdata_by_handle(doc, selected_circle['handle'])
            except Exception as e:
                st.error(f"XData 조회 에러: {e}")
            
            if existing_xdata:
                st.success("이 개체에는 이미 암묵지 코드가 내장되어 있습니다.")
                st.json(existing_xdata)
            
            master_comment = st.text_area("숙련 기술인의 노하우를 입력해 주세요 (구어체 가능)", placeholder="예: 여기에 스크류 들어갈거니까 크랙 안나게 외경 살두께의 1.5배로 키우고 단차 확보 필요.")
            
            if st.button("Gemini AI 제약조건 분석 및 컴파일"):
                if not master_comment.strip():
                    st.error("암묵지 의견을 입력해 주세요.")
                else:
                    with st.spinner("Gemini API를 호출하여 도면 변수와 매핑 규칙을 코드로 생성하고 있습니다..."):
                        try:
                            api_key = api_key_input if api_key_input.strip() else None
                            api_service = GeminiAPIService(api_key=api_key)
                            
                            # AI 분석 호출
                            rule_json = api_service.compile_constraint(master_comment, selected_circle)
                            st.session_state["compiled_rule"] = rule_json
                            st.success("제약조건 코드(JSON) 컴파일 성공!")
                            st.json(rule_json)
                            logger.info(f"Gemini API 룰 컴파일 성공: Handle={selected_circle['handle']}")
                        except Exception as e:
                            st.error(f"분석 실패: {e}")
                            logger.error(f"분석 실패 에러: {e}")
                            
            # 5. XData 주입 및 새로운 DXF 파일 다운로드
            if st.session_state.get("compiled_rule"):
                st.write("---")
                st.subheader("💾 DXF 파일 내보내기")
                if st.button("도면에 메타데이터 영구 주입"):
                    try:
                        # XData 주입
                        success = xdata_service.inject_xdata_by_handle(doc, selected_circle['handle'], st.session_state["compiled_rule"])
                        if success:
                            # 새로운 DXF 저장
                            output_path = repo.save_output_dxf(doc, uploaded_file.name)
                            with open(output_path, "rb") as file_bytes:
                                st.download_button(
                                    label="암묵지 내장형 DXF 다운로드",
                                    data=file_bytes,
                                    file_name=os.path.basename(output_path),
                                    mime="application/dxf"
                                )
                            st.success("DXF 파일 내 주입 및 내보내기 성공! 위 다운로드 버튼을 클릭하세요.")
                            logger.info(f"XData 주입 완료 및 내보내기 파일 생성: {os.path.basename(output_path)}")
                    except Exception as e:
                        st.error(f"주입 실패: {e}")
                        logger.error(f"주입 실패 에러: {e}")

# 6. 하단: 실시간 트레이스 로그 뷰어
st.write("---")
st.subheader("📝 실시간 로깅 모니터 (Logger Trace)")
if os.path.exists("./log/app.log"):
    try:
        with open("./log/app.log", "r", encoding="utf-8") as lf:
            log_lines = lf.readlines()
        st.code("".join(log_lines[-20:]))  # 마지막 20줄 출력
    except Exception:
        st.info("로그 파일을 읽을 수 없습니다.")
else:
    st.info("로그가 비어 있습니다.")
