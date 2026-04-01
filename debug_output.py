from google import genai
from PIL import Image
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
img = Image.open('receipts/receipt_02.jpg')
prompt = """이 영수증 이미지를 분석하여 다음 정보를 추출해줘. 항목을 찾을 수 없는 경우 값에 '없음'이라고 적어줘. 결과를 반드시 아래 예시와 동일한 형식으로 출력해:
1. 결제 일자 (날짜): YYYY-MM-DD
2. 상호명: 상호명
3. 총 결제 금액: 금액(숫자만)
4. 부가세: 금액(숫자만, 없으면 0)"""

response = client.models.generate_content(model='gemini-2.5-flash-lite', contents=[prompt, img])
print("--- RAW AI RESPONSE ---")
print(response.text)
print("--- END ---")
