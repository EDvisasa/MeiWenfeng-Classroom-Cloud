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
  const isUpdatePersona = ['/update_persona', 'update_persona', '/更新人设', '更新人设'].includes(cmd);
  if (isUpdatePersona) {
    const userMsg = { role: 'user', content: commandText.trim(), timestamp: getNowStr() };
    const sysMsg = {
      role: 'system_info',
      type: 'persona_update_progress',
      state: 'loading',
      content: '导师正在提炼并更新角色设定卡，请稍候...',
      text: '导师正在提炼并更新角色设定卡，请稍候...'
    };
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
                    let parsedData = dataStr;
                    try {
                        // The backend yields escaped JSON like "data: {\"text\": \"[系统更新] ...\"}"
                        parsedData = JSON.parse(dataStr);
                    } catch (e) {}

                    let textVal = '';
                    if (typeof parsedData === 'string') {
                        textVal = parsedData;
                    } else if (parsedData && typeof parsedData === 'object') {
                        textVal = parsedData.text || parsedData.content || parsedData.message || '';
                    } else {
                        textVal = String(parsedData || '');
                    }

                    if (!textVal) continue;

                    // Check if chunk represents a failure/error reported by backend
                    const isError = textVal.includes('错误：') || textVal.includes('失败:');
                    if (isError) {
                        let errorText = textVal.replace(/^\[系统更新\]\s*/, '');
                        errorText = errorText.replace(/^错误[：:]\s*/, '').replace(/^生成精简人设失败[：:]\s*/, '提炼失败: ');

                        setMessages(prev => {
                            const updated = [...prev];
                            const last = updated[updated.length - 1] ? { ...updated[updated.length - 1] } : null;
                            if (last && (last.type === 'persona_update_progress' || last.type === 'system_action')) {
                                last.state = 'error';
                                last.error = errorText;
                                last.text = errorText;
                                last.content = errorText;
                                updated[updated.length - 1] = last;
                            }
                            return updated;
                        });
                    }
                }
            }
        }
        
        // When stream completes, set status to done (pure system card, no assistant dialogue pollution)
        setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1] ? { ...updated[updated.length - 1] } : null;
            if (last && (last.type === 'persona_update_progress' || last.type === 'system_action') && last.state === 'loading') {
                last.state = 'done';
                last.content = '角色设定卡提炼完毕，人设已同步。';
                last.text = last.content;
                updated[updated.length - 1] = last;
            }
            return updated;
        });

    } catch (e) {
        setMessages(prev => {
            const updated = [...prev];
            const last = updated[updated.length - 1] ? { ...updated[updated.length - 1] } : null;
            if (last && (last.type === 'persona_update_progress' || last.type === 'system_action')) {
                last.state = 'error';
                last.error = `提炼失败: ${e.message}`;
                last.content = last.error;
                last.text = last.content;
                updated[updated.length - 1] = last;
            }
            return updated;
        });
    }
    return true;
  }

  // Add more system commands here...

  return false;
};
