import os
from dotenv import load_dotenv
load_dotenv('.env')
from openai import OpenAI

api_key = os.getenv('AIRP_MODEL_API_KEY') or os.getenv('DEEPSEEK_API_KEY')
base_url = os.getenv('AIRP_MODEL_BASE_URL') or os.getenv('DEEPSEEK_BASE_URL')

client = OpenAI(api_key=api_key or 'test', base_url=base_url)
try:
    response = client.chat.completions.create(
        model='gemini-3.1-pro-preview',
        messages=[
            {'role': 'system', 'content': '请将这段简短的修仙教学对话，浓缩成不超过 150 字的【今日总结】。\n【重要指令】：请直接输出纯文本总结，绝对不要包含任何 Markdown 格式或多余的换行，并且整段文字必须严格以完整的中文句号“。”结尾。'},
            {'role': 'user', 'content': '【对话记录】\n用户：娘子，这御剑飞行的法诀好难啊！\n媚吻锋：夫君莫慌，且看奴家示范，将灵力集中于足底涌泉穴~'}
        ],
        stream=False
    )
    print('RESPONSE:', repr(response.choices[0].message.content))
except Exception as e:
    print('ERROR:', e)
