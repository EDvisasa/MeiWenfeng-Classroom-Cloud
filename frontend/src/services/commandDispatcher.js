export const dispatchSystemCommand = async (commandText, context) => {
  const { setMessages, API_BASE, getNowStr } = context;
  const cmd = commandText.trim().toLowerCase();

  // /summarize: Memory compression engine
  if (cmd === '/summarize') {
    const userMsg = { role: 'user', content: commandText.trim(), timestamp: getNowStr() };
    const sysMsg = { role: 'system_info', type: 'summarize_progress', state: 'loading' };
    setMessages(prev => [...prev, userMsg, sysMsg]);
    
    try {
        const res = await fetch(`${API_BASE}/api/chat/summarize`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.type === 'summarize_progress') {
                    last.state = 'done';
                    if (data.stats) last.stats = data.stats;
                }
                return updated;
            });
        } else {
            setMessages(prev => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.type === 'summarize_progress') {
                    last.state = 'error';
                    last.error = data.detail || data.message || 'Unknown error';
                }
                return updated;
            });
        }
    } catch (e) {
        setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.type === 'summarize_progress') {
                last.state = 'error';
                last.error = e.message;
            }
            return updated;
        });
    }
    return true;
  }


  // /update_persona: Sync and distil persona with SSE streaming
  if (cmd === '/update_persona') {
    const userMsg = { role: 'user', content: commandText.trim(), timestamp: getNowStr() };
    const sysMsg = { role: 'system_info', type: 'system_action', state: 'loading', text: '正在准备更新人设...' };
    setMessages(prev => [...prev, userMsg, sysMsg]);

    try {
        const res = await fetch(`${API_BASE}/api/chat/command/update_persona_stream`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6).trim();
                    if (!dataStr) continue;
                    let parsedText = dataStr;
                    try {
                        // The backend yields escaped JSON strings like "data: \"[系统更新] ...\""
                        parsedText = JSON.parse(dataStr);
                    } catch (e) {}

                    // Update the banner text dynamically
                    setMessages(prev => {
                        const updated = [...prev];
                        const last = updated[updated.length - 1];
                        if (last && last.type === 'system_action' && last.state === 'loading') {
                            last.text = parsedText;
                        }
                        return updated;
                    });
                }
            }
        }
        
        // When stream completes, set it to done
        setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.type === 'system_action' && last.state === 'loading') {
                last.state = 'done';
                // The text remains whatever the last stream event set it to (e.g. "[系统更新] 更新大业已成...")
            }
            return updated;
        });

    } catch (e) {
        setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.type === 'system_action') {
                last.state = 'error';
                last.text = `更新失败: ${e.message}`;
            }
            return updated;
        });
    }
    return true;
  }

  // Add more system commands here...

  return false;
};
