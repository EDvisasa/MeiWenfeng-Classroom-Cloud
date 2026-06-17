import json
import urllib.request
import sys

def test():
    url = "http://127.0.0.1:12701/api/chat/send"
    payload = {
        "messages": [
            {"role": "user", "content": "请使用 bash 工具执行命令 `echo TDD_TOOL_TEST_SUCCESS`，只输出工具执行结果即可。"}
        ],
        "persona_type": "simplified"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    print("Sending request to backend...")
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith("data: "):
                    try:
                        event_data = json.loads(line_str[6:])
                        if isinstance(event_data, dict):
                            t = event_data.get('type')
                            if t == 'tool_start':
                                print(f"\n[Tool Started] Command: {event_data.get('command')}")
                            elif t == 'tool_output':
                                print(f"[Tool Output]: {event_data.get('text')}")
                            elif t == 'text':
                                print(event_data.get('text', ''), end='', flush=True)
                            elif t == 'thinking':
                                pass
                        else:
                            pass
                    except json.JSONDecodeError:
                        pass
        print("\n\nTest completed.")
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        print("Please ensure the backend is running.")

if __name__ == "__main__":
    test()
