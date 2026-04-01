import os
import re
import io
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai

def setup_directories():
    dirs = ['receipts', os.path.join('receipts', 'error'), 'outputs']
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def parse_response(text):
    data = {"날짜": "없음", "상호명": "없음", "공급가액": "없음", "부가세": "없음", "카테고리": "없음"}
    
    clean_text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    lines = clean_text.split('\n')
    
    for line in lines:
        if ':' in line or '：' in line:
            separator = ':' if ':' in line else '：'
            parts = line.split(separator, 1)
            k = parts[0].strip()
            v = parts[1].strip()
            
            for key in data.keys():
                if key in k:
                    data[key] = v

    data["공급가액"] = re.sub(r'[^\d]', '', data["공급가액"])
    data["부가세"] = re.sub(r'[^\d]', '', data["부가세"])
    
    if not data["공급가액"]: data["공급가액"] = "없음"
    if not data["부가세"]: data["부가세"] = "없음"

    return data

def main():
    st.set_page_config(page_title="영수증 자동 처리기", page_icon="🧾", layout="centered")
    setup_directories()

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        st.error(".env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
        return

    client = genai.Client(api_key=api_key)

    st.title("🧾 영수증 자동 처리기")
    st.write("영수증 사진을 업로드하면 날짜, 상호명, 금액을 자동으로 추출합니다.")

    uploaded_file = st.file_uploader("영수증 이미지 업로드", type=["jpg", "jpeg", "png", "bmp", "gif"])
    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        st.image(img, caption="업로드된 영수증", use_column_width=True)

        if st.button("영수증 분석하기", type="primary"):
            with st.spinner("Gemini AI가 영수증을 분석 중입니다..."):
                try:
                    model_id = 'gemini-2.5-flash'
                    prompt = """영수증 이미지에서 다음 5가지 항목을 찾아줘: 날짜, 상호명, 공급가액, 부가세, 카테고리.
조건:
1. 없는 경우 '없음'이라고 할 것
2. 금액은 기호(원, ₩, 쉼표 등)를 제외하고 순수한 숫자만 출력할 것
3. 카테고리는 상호명과 구매 내역을 바탕으로 다음 중 하나로만 분류할 것: 식비, 교통비, 사무용품, 숙박비, 기타
4. 마크다운 포맷(``` 등) 없이 '항목: 값' 형태로 5줄만 출력할 것"""
                    
                    response = client.models.generate_content(
                        model=model_id,
                        contents=[prompt, img]
                    )
                    
                    parsed_data = parse_response(response.text)
                    
                    # 합계금액 계산 (공급가액 + 부가세)
                    try:
                        supply = int(parsed_data.get("공급가액", "0") if parsed_data.get("공급가액") != "없음" else 0)
                    except ValueError:
                        supply = 0
                        
                    try:
                        vat = int(parsed_data.get("부가세", "0") if parsed_data.get("부가세") != "없음" else 0)
                    except ValueError:
                        vat = 0
                        
                    parsed_data["합계금액"] = str(supply + vat)
                    
                    # 부가세포함 여부 확인
                    if vat > 0:
                        parsed_data["부가세포함"] = "포함"
                    else:
                        parsed_data["부가세포함"] = "미포함"
                    
                    st.success("분석 완료!")
                    
                    # 결과를 보기 좋은 표로 출력
                    # 순서를 명시적으로 지정
                    columns_order = ["날짜", "상호명", "카테고리", "공급가액", "부가세", "합계금액", "부가세포함"]
                    ordered_data = {k: parsed_data[k] for k in columns_order if k in parsed_data}
                    df = pd.DataFrame([ordered_data])
                    
                    # '없음'인 경우 빨간색으로 표시
                    def highlight_missing(val):
                        return 'color: red' if val == '없음' else ''
                    
                    # pandas 버전에 따른 호환성 처리 (map vs applymap)
                    try:
                        styled_df = df.style.map(highlight_missing)
                    except AttributeError:
                        styled_df = df.style.applymap(highlight_missing)
                        
                    st.table(styled_df)
                    
                    # 요약 표시
                    fail_count = list(parsed_data.values()).count('없음')
                    success_count = len(parsed_data) - fail_count
                    
                    st.markdown(f"**✅ 성공 {success_count}건 | ❌ 실패 {fail_count}건**")
                    
                    # 엑셀 다운로드 버튼
                    excel_df = df.copy()
                    
                    # 맨 아래에 합계 행 추가
                    sum_row = {col: "" for col in excel_df.columns}
                    sum_row["날짜"] = "총합계"
                    sum_row["합계금액"] = parsed_data["합계금액"]
                    
                    excel_df = pd.concat([excel_df, pd.DataFrame([sum_row])], ignore_index=True)
                    
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        excel_df.to_excel(writer, index=False, sheet_name="분석결과")
                        
                    st.download_button(
                        label="📥 엑셀로 다운로드",
                        data=excel_buffer.getvalue(),
                        file_name="receipt_result.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main()
