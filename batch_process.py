import os
import glob
import shutil
import re
import pandas as pd
from dotenv import load_dotenv
from google import genai
from PIL import Image

def setup_directories():
    dirs = ['receipts', os.path.join('receipts', 'error'), 'outputs']
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def parse_response(text):
    data = {"날짜": "없음", "상호명": "없음", "총금액": "없음", "부가세": "없음"}
    
    # 마크다운 백틱 및 json 태그 제거
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

    # 금액 정제 (숫자만 남기기)
    data["총금액"] = re.sub(r'[^\d]', '', data["총금액"])
    data["부가세"] = re.sub(r'[^\d]', '', data["부가세"])
    
    # 빈 문자열 처리
    if not data["총금액"]: data["총금액"] = "없음"
    if not data["부가세"]: data["부가세"] = "없음"

    return data

def main():
    setup_directories()

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("오류: .env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
        return

    client = genai.Client(api_key=api_key)
    
    receipt_dir = "receipts"
    error_dir = os.path.join(receipt_dir, "error")
    output_xlsx = os.path.join("outputs", "results.xlsx")

    image_extensions = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif')
    receipt_files = []
    for ext in image_extensions:
        receipt_files.extend(glob.glob(os.path.join(receipt_dir, ext)))
        receipt_files.extend(glob.glob(os.path.join(receipt_dir, ext.upper())))
    
    # 중복 제거 및 정렬
    receipt_files = sorted(list(set(receipt_files)))

    if not receipt_files:
        print("알림: 'receipts' 폴더에 처리할 이미지 파일이 없습니다.")
        return

    print(f"총 {len(receipt_files)}개의 영수증을 일괄 처리합니다...\n")

    results_list = []
    failures_list = []

    for file_path in receipt_files:
        file_name = os.path.basename(file_path)
        print(f"[{file_name}] 처리 중...", end=" ", flush=True)

        try:
            img = Image.open(file_path)
            prompt = """영수증 이미지에서 다음 4가지 항목을 찾아줘: 날짜, 상호명, 총금액, 부가세.
조건:
1. 없는 경우 '없음'이라고 할 것
2. 금액은 기호(원, ₩, 쉼표 등)를 제외하고 순수한 숫자만 출력할 것
3. 마크다운 포맷(``` 등) 없이 '항목: 값' 형태로 4줄만 출력할 것"""

            # 1차 시도: gemini-2.5-flash-lite
            try:
                model_id = 'gemini-2.5-flash-lite'
                response = client.models.generate_content(
                    model=model_id,
                    contents=[prompt, img]
                )
            except Exception as e:
                # 2차 시도 (Fallback): gemini-2.5-flash
                print("(Fallback: gemini-2.5-flash 사용)", end=" ")
                model_id = 'gemini-2.5-flash'
                response = client.models.generate_content(
                    model=model_id,
                    contents=[prompt, img]
                )

            # 데이터 파싱
            parsed_data = parse_response(response.text)
            
            # 둘 다 실패면 error (필수값이 거의 안나오면 에러로 간주 등의 로직도 가능하지만, 단순 예외 처리로 함)
            data_dict = {
                "파일명": file_name,
                "날짜": parsed_data["날짜"],
                "상호명": parsed_data["상호명"],
                "총금액": parsed_data["총금액"],
                "부가세": parsed_data["부가세"]
            }
            results_list.append(data_dict)
            print("완료")
            
        except Exception as e:
            print(f"\033[91m실패 (오류: {e})\033[0m")
            failures_list.append({"실패한 파일명": file_name, "실패 이유": str(e)})
            try:
                shutil.move(file_path, os.path.join(error_dir, file_name))
            except Exception as move_e:
                pass

    # 결과 엑셀 저장
    if results_list or failures_list:
        try:
            with pd.ExcelWriter(output_xlsx, engine='openpyxl') as writer:
                df_success = pd.DataFrame(results_list) if results_list else pd.DataFrame(columns=["파일명", "날짜", "상호명", "총금액", "부가세"])
                df_success.to_excel(writer, sheet_name="결과", index=False)
                
                df_fail = pd.DataFrame(failures_list) if failures_list else pd.DataFrame(columns=["실패한 파일명", "실패 이유"])
                df_fail.to_excel(writer, sheet_name="실패 목록", index=False)
            
            print(f"\n=> 엑셀 파일 저장 완료: {output_xlsx}")
        except Exception as e:
             print(f"\n=> 엑셀 파일 저장 실패: {e}")

    print("=" * 40)
    print(f"작업 요약 -> 성공: {len(results_list)}건 / 실패: {len(failures_list)}건")
    print("=" * 40)

if __name__ == "__main__":
    main()
