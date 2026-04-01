import os
import glob
from dotenv import load_dotenv
from google import genai
from PIL import Image
import unicodedata

def string_width(s):
    # 한글 등 CJK 문자는 폭을 2로, 그 외는 1로 계산
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)

def pad_string(s, width):
    return s + ' ' * max(0, width - string_width(s))

def setup_directories():
    dirs = ['receipts', os.path.join('receipts', 'error'), 'outputs']
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def main():
    setup_directories()

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("오류: .env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
        return

    client = genai.Client(api_key=api_key)
    model_id = 'gemini-2.5-flash'

    image_extensions = ('*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif')
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join("receipts", ext)))
        image_files.extend(glob.glob(os.path.join("receipts", ext.upper())))
    
    if not image_files:
        print("오류: receipts 폴더에 이미지 파일이 없습니다.")
        return

    first_image_path = image_files[0]
    print(f"분석할 이미지: {first_image_path}\n")

    try:
        img = Image.open(first_image_path)
        prompt = """영수증 이미지에서 다음 4가지 항목을 찾아줘: 날짜, 상호명, 총금액, 부가세.

조건:
1. 없는 항목은 '없음'이라고 적을 것
2. 금액은 기호(원, ₩, 쉼표 등)를 모두 뺀 "순수한 숫자만" 출력할 것
3. 추가 설명이나 마크다운 포맷(``` 등) 없이 '항목: 값' 형태로 4줄만 출력할 것
"""
        response = client.models.generate_content(
            model=model_id,
            contents=[prompt, img]
        )
        
        text = response.text.strip()
        lines = text.split('\n')
        
        data = {"날짜": "없음", "상호명": "없음", "총금액": "없음", "부가세": "없음"}
        for line in lines:
            if ":" in line or "：" in line:
                sep = ":" if ":" in line else "："
                k, v = line.split(sep, 1)
                k = k.strip()
                v = v.strip()
                for key in data.keys():
                    if key in k:
                        data[key] = v

        k_width = 12
        v_width = 30
        
        print(f"+-{'-'*k_width}-+-{'-'*v_width}-+")
        print(f"| {pad_string('항목', k_width)} | {pad_string('값', v_width)} |")
        print(f"+-{'-'*k_width}-+-{'-'*v_width}-+")
        for k, v in data.items():
            print(f"| {pad_string(k, k_width)} | {pad_string(v, v_width)} |")
        print(f"+-{'-'*k_width}-+-{'-'*v_width}-+")

    except Exception as e:
         print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()
