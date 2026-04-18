import os
import requests
from dotenv import load_dotenv
import sys

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 더 강력한 지시문
SYSTEM_PROMPT = """CRITICAL TASK: Create COMPLETE 04_full_script.txt with ZERO truncation.

You MUST process the ENTIRE script - no shortcuts, no "continued...", no omissions.

FORMAT (MANDATORY):

[Paragraph 1]
EN: (complete paragraph 1 text)
KR: (Korean translation)

[Paragraph 2]  
EN: (complete paragraph 2 text)
KR: (Korean translation)

Continue for EVERY SINGLE PARAGRAPH until the END.

ANTI-TRUNCATION RULES (CRITICAL):
- Process ALL 43,900 characters
- Never write "...continued" or similar
- Never stop early due to length
- This is for educational use - completeness is MANDATORY
- Include EVERY sentence from original

If you start truncating, you FAIL the task."""

def call_openai_api(script_content):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }
    
    data = {
        'model': 'gpt-3.5-turbo',  # 3.5 사용 (성공 확률 높음)
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"Process this COMPLETE script:\n\n{script_content}"}
        ],
        'max_tokens': 4000,
        'temperature': 0.05  # 더 정확한 처리
    }
    
    try:
        print("🤖 GPT-3.5-turbo로 강력한 04 파일 생성 중...")
        response = requests.post('https://api.openai.com/v1/chat/completions', 
                               headers=headers, json=data, timeout=300)
        
        if response.status_code == 429:
            print("⚠️  Rate limit. 5분 후 재시도하세요.")
            return None
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"❌ 에러: {e}")
        return None

def main():
    print("💪 04_full_script.txt 강력 생성기 (GPT-3.5)")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print('사용법: python scripts/generate_04_strong.py "KFC Success Story - Level 2.txt"')
        return
    
    filename = sys.argv[1]
    
    # 파일 찾기
    file_path = None
    for root, dirs, files in os.walk('.'):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path:
        print(f"❌ 파일 없음: {filename}")
        return
    
    folder_path = os.path.dirname(file_path)
    
    # 스크립트 읽기
    with open(file_path, 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    print(f"📄 처리할 크기: {len(script_content):,} 글자")
    
    # API 호출
    result = call_openai_api(script_content)
    if not result:
        return
    
    # 저장
    output_path = os.path.join(folder_path, "04_full_script.txt")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result['choices'][0]['message']['content'])
    
    print(f"✅ 완료! {len(result['choices'][0]['message']['content']):,} 글자 생성")
    
    # 비용
    if 'usage' in result:
        usage = result['usage']
        cost = (usage['prompt_tokens'] * 0.001 + usage['completion_tokens'] * 0.002) / 1000
        print(f"💰 비용: ${cost:.4f}")

if __name__ == "__main__":
    main()
