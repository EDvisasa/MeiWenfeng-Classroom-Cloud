import React, { useState, useEffect, useRef } from 'react';
import FileTree from './components/FileTree';
import ChatPanel from './components/ChatPanel';
import StatusPanel from './components/StatusPanel';
import CropModal from './components/CropModal';
import DatabaseViewer from './components/DatabaseViewer';

const COMMANDS = [
  { cmd: '/上课', desc: '开始新的课时，进入授课模式' },
  { cmd: '/交作业', desc: '进行课题考核，AI会对你进行提问' },
  { cmd: '/奖励', desc: '获取好感奖励，触发狐妖娘溺爱互动' },
  { cmd: '/总结', desc: '压缩并保存当前记忆，释放上下文' },
  { cmd: '/备课', desc: '将当前选定的讲义文件上传同步至RAGFlow知识库' },
  { cmd: '/计划', desc: '根据当前进度，重新调整课程大纲' }
];

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [messages, setMessages] = useState([]);

  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showDbViewer, setShowDbViewer] = useState(false);
  const [showMobileStatus, setShowMobileStatus] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem('mei_theme') || 'light');
  const [showSessionList, setShowSessionList] = useState(false);
  
  // 检测是否在 VS Code 插件环境中运行
  const isVsCode = new URLSearchParams(window.location.search).get('env') === 'vscode';

  const syncSessionToBackend = async (session) => {
    try {
      await fetch('http://localhost:8000/api/chat/sessions/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: session.id,
          title: session.title,
          messages: session.messages
        })
      });
    } catch (e) {
      console.error('Failed to sync session to backend:', e);
    }
  };

  // 同步当前会话的消息列表到 sessions 以及后端数据库
  useEffect(() => {
    if (!activeSessionId || sessions.length === 0) return;

    const currentSession = sessions.find(s => s.id === activeSessionId);
    if (!currentSession) return;

    if (JSON.stringify(currentSession.messages) === JSON.stringify(messages)) {
      return;
    }

    let updatedTitle = currentSession.title;
    if (updatedTitle === '默认会话' || updatedTitle === '新对话') {
      const firstUserMsg = messages.find(m => m.role === 'user');
      if (firstUserMsg) {
        updatedTitle = firstUserMsg.content.slice(0, 15) + (firstUserMsg.content.length > 15 ? '...' : '');
      }
    }

    const updatedSession = { ...currentSession, messages, title: updatedTitle };

    setSessions(prevSessions => prevSessions.map(s => s.id === activeSessionId ? updatedSession : s));
    syncSessionToBackend(updatedSession);
  }, [messages, activeSessionId]);

  const handleSwitchSession = (sessionId) => {
    if (isStreaming) return;
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      setActiveSessionId(sessionId);
      localStorage.setItem('mei_wenfeng_classroom_active_session_id', sessionId);
      setMessages(session.messages);
    }
  };

  const handleNewSession = async () => {
    if (isStreaming) return;
    const newId = Date.now().toString();
    const newSession = {
      id: newId,
      title: '新对话',
      messages: [
        {
          role: 'assistant',
          content: '*端坐在精致的红木矮椅上，红金色汉服衬出诱人的身段，红黑色的狐瞳含笑望着你，玉手托着香腮，柔声道：*“夫君，你可算来了。今天，咱们该从哪一课开始呢？是要奴家教你灵气感知，还是说...想先跟奴家聊聊天？”'
        }
      ]
    };
    
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
    localStorage.setItem('mei_wenfeng_classroom_active_session_id', newId);
    setMessages(newSession.messages);
    await syncSessionToBackend(newSession);
  };

  const handleDeleteSession = async (sessionId, e) => {
    if (e) e.stopPropagation();
    if (isStreaming) return;
    
    const filtered = sessions.filter(s => s.id !== sessionId);
    let nextSessions = filtered;
    
    try {
      await fetch(`http://localhost:8000/api/chat/sessions/${sessionId}`, {
        method: 'DELETE'
      });
    } catch (err) {
      console.error('Failed to delete session on backend:', err);
    }

    if (filtered.length === 0) {
      const defaultId = Date.now().toString();
      const defaultSess = {
        id: defaultId,
        title: '默认会话',
        messages: [
          {
            role: 'assistant',
            content: '*端坐在精致的红木矮椅上，红金色汉服衬出诱人的身段，红黑色的狐瞳含笑望着你，玉手托着香腮，柔声道：*“夫君，你可算来了。今天，咱们该从哪一课开始呢？是要奴家教你灵气感知，还是说...想先跟奴家聊聊天？”'
          }
        ]
      };
      nextSessions = [defaultSess];
      await syncSessionToBackend(defaultSess);
    }
    
    setSessions(nextSessions);

    if (activeSessionId === sessionId) {
      const nextActiveId = nextSessions[0].id;
      setActiveSessionId(nextActiveId);
      localStorage.setItem('mei_wenfeng_classroom_active_session_id', nextActiveId);
      setMessages(nextSessions[0].messages);
    }
  };

  const handleEditAndResend = async (index, newContent) => {
    if (isStreaming) return;
    
    // 截断到 index
    const truncated = messages.slice(0, index);
    const editedMessage = { role: 'user', content: newContent };
    const nextMessages = [...truncated, editedMessage];
    
    setMessages(nextMessages);
    await triggerAIResponse(nextMessages);
  };

  // 内心独白
  const [currentThought, setCurrentThought] = useState('暂时没有想法...');

  // 头像裁剪相关
  const [userAvatar, setUserAvatar] = useState(localStorage.getItem('user_avatar') || '🎓');
  const [assistantAvatar, setAssistantAvatar] = useState(localStorage.getItem('assistant_avatar') || '🦊');
  const [cropTarget, setCropTarget] = useState('user');
  const [showCropModal, setShowCropModal] = useState(false);
  const [imageSrc, setImageSrc] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const reader = new FileReader();
      reader.addEventListener('load', () => {
        setImageSrc(reader.result);
        setShowCropModal(true);
      });
      reader.readAsDataURL(e.target.files[0]);
      e.target.value = null; // reset
    }
  };

  const handleSaveCrop = (croppedImage) => {
    if (cropTarget === 'user') {
      setUserAvatar(croppedImage);
      localStorage.setItem('user_avatar', croppedImage);
    } else {
      setAssistantAvatar(croppedImage);
      localStorage.setItem('assistant_avatar', croppedImage);
    }
    setShowCropModal(false);
    setImageSrc(null);
  };
  
  // 字体大小设置
  const [fontSize, setFontSize] = useState(parseInt(localStorage.getItem('chat_font_size')) || 16);
  const handleFontSizeChange = (e) => {
    const newSize = parseInt(e.target.value);
    setFontSize(newSize);
    localStorage.setItem('chat_font_size', newSize.toString());
  };

  // 头像大小设置
  const [avatarSize, setAvatarSize] = useState(parseInt(localStorage.getItem('avatar_size')) || 36);

  // 名字大小设置
  const [nameFontSize, setNameFontSize] = useState(parseInt(localStorage.getItem('name_font_size')) || 12);
  const handleNameFontSizeChange = (e) => {
    const newSize = parseInt(e.target.value);
    setNameFontSize(newSize);
    localStorage.setItem('name_font_size', newSize.toString());
  };
  
  // 状态与配置
  const [activeModel, setActiveModel] = useState('DeepSeek (在线)');
  const [activeSubModel, setActiveSubModel] = useState('');
  const [models, setModels] = useState([]);
  const [courseProgress, setCourseProgress] = useState([]);
  const [affection, setAffection] = useState(100);
  const [personaType, setPersonaType] = useState(localStorage.getItem('persona_type') || 'simplified');

  // 酒馆式 API 设置和字体弹窗状态
  const [showFontMenu, setShowFontMenu] = useState(false);
  const [showApiMenu, setShowApiMenu] = useState(false);
  const [selectedConfigId, setSelectedConfigId] = useState(1);
  const [tempBaseUrl, setTempBaseUrl] = useState('');
  const [tempApiKey, setTempApiKey] = useState('');
  const [tempSelectedSubModel, setTempSelectedSubModel] = useState('');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // RAG 知识库后端配置
  const [ragConfig, setRagConfig] = useState({
    backend_type: 'chromadb',
    ragflow_url: '',
    ragflow_key: '',
    external_url: '',
    external_key: ''
  });
  const [savingRag, setSavingRag] = useState(false);

  const handlePersonaTypeChange = (type) => {
    setPersonaType(type);
    localStorage.setItem('persona_type', type);
    setMessages(prev => [
      ...prev,
      { role: 'system_info', content: `[人设切换] 已切换导师人设为：${type === 'simplified' ? '精简人设' : '原版人设'}` }
    ]);
  };
  
  // 角色本地图片包列表 (兼容状态)
  const [avatarList, setAvatarList] = useState([]);
  
  // 真实本地文件系统挂载路径和选定状态
  const [rootPath, setRootPath] = useState('D:/MeiWenfeng-Classroom');
  const [selectedFilePath, setSelectedFilePath] = useState('');
  const [selectedFileContent, setSelectedFileContent] = useState('');
  
  // 斜杠命令自动补全
  const [showCommandList, setShowCommandList] = useState(false);
  const [filteredCommands, setFilteredCommands] = useState([]);
  const [activeCommandIndex, setActiveCommandIndex] = useState(0);

  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // 滚动至最新消息
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 初始化拉取状态与历史会话
  useEffect(() => {
    const loadSessions = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/chat/sessions');
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setSessions(data);
            const savedActive = localStorage.getItem('mei_wenfeng_classroom_active_session_id');
            const activeId = (savedActive && data.some(s => s.id === savedActive)) ? savedActive : data[0].id;
            setActiveSessionId(activeId);
            const activeSess = data.find(s => s.id === activeId) || data[0];
            setMessages(activeSess.messages || []);
          } else {
            const defaultId = Date.now().toString();
            const defaultSess = {
              id: defaultId,
              title: '默认会话',
              messages: [
                {
                  role: 'assistant',
                  content: '*端坐在精致的红木矮椅上，红金色汉服衬出诱人的身段，红黑色的狐瞳含笑望着你，玉手托着香腮，柔声道：*“夫君，你可算来了。今天，咱们该从哪一课开始呢？是要奴家教你灵气感知，还是说...想先跟奴家聊聊天？”'
                }
              ]
            };
            setSessions([defaultSess]);
            setActiveSessionId(defaultId);
            setMessages(defaultSess.messages);
            await syncSessionToBackend(defaultSess);
          }
        }
      } catch (e) {
        console.error('Failed to load sessions from backend:', e);
      }
    };
    loadSessions();

    fetchStatus();
    fetchModels();
    fetchAvatars();
    fetchRagConfig();
  }, []);

  // 监听来自 VS Code 插件的消息
  useEffect(() => {
    const handleMessage = (event) => {
      const message = event.data;
      if (message.type === 'activeFileChanged') {
        setSelectedFilePath(message.filePath);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // 当 models 加载完成，将当前激活的 API 参数回显至设置中
  useEffect(() => {
    const active = models.find(m => m.is_active === 1);
    if (active) {
      setSelectedConfigId(active.id);
      setTempBaseUrl(active.base_url);
      setTempApiKey(active.api_key || '');
      setTempSelectedSubModel(active.selected_model_id || '');
    }
  }, [models]);

  // 当 API 设置菜单打开、切换配置源或代理地址变化时，自动拉取可用模型
  useEffect(() => {
    if (showApiMenu && tempBaseUrl) {
      const fetchModelsAuto = async () => {
        setLoadingModels(true);
        try {
          const selected = models.find(m => m.id === selectedConfigId);
          const protocol = selected ? selected.protocol : 'openai';
          const url = `http://localhost:8000/api/chat/models/available?base_url=${encodeURIComponent(tempBaseUrl)}&api_key=${encodeURIComponent(tempApiKey)}&protocol=${protocol}`;
          const res = await fetch(url);
          if (res.ok) {
            const data = await res.json();
            if (data.status === 'success') {
              setAvailableModels(data.models || []);
            }
          }
        } catch (e) {
          console.error("Auto fetch available models failed:", e);
        } finally {
          setLoadingModels(false);
        }
      };
      
      fetchModelsAuto();
    }
  }, [showApiMenu, selectedConfigId, tempBaseUrl]);


  const fetchStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/status');
      if (res.ok) {
        const data = await res.json();
        setAffection(data.affection);
        setActiveModel(data.active_model);
        setActiveSubModel(data.active_sub_model || '');
        setCourseProgress(data.course_progress || []);
      }
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  };

  const fetchModels = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/models');
      if (res.ok) {
        const data = await res.json();
        setModels(data);
      }
    } catch (e) {
      console.error('Failed to fetch models:', e);
    }
  };

  const fetchAvatars = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/images');
      if (res.ok) {
        const data = await res.json();
        setAvatarList(data);
      }
    } catch (e) {
      console.error('Failed to fetch avatars:', e);
    }
  };

  const fetchRagConfig = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/rag/config');
      if (res.ok) {
        const data = await res.json();
        setRagConfig(data);
      }
    } catch (e) {
      console.error('Failed to fetch rag config:', e);
    }
  };

  const saveRagConfig = async () => {
    setSavingRag(true);
    try {
      const res = await fetch('http://localhost:8000/api/chat/rag/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ragConfig)
      });
      if (res.ok) {
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[知识库配置] 已切换知识库后端为：${ragConfig.backend_type === 'chromadb' ? '🚀 本地 ChromaDB' : ragConfig.backend_type === 'ragflow' ? '☁️ RAGFlow' : '🔗 外部 API'}` }
        ]);
      } else {
        alert('保存知识库配置失败，请检查后端状态。');
      }
    } catch (e) {
      console.error(e);
      alert('保存失败，请检查网络或后端状态。');
    } finally {
      setSavingRag(false);
    }
  };

  // 切换设置面板里选择的模型配置时回显
  const handleConfigSelection = (e) => {
    const configId = parseInt(e.target.value);
    setSelectedConfigId(configId);
    
    const selected = models.find(m => m.id === configId);
    if (selected) {
      setTempBaseUrl(selected.base_url);
      setTempApiKey(selected.api_key || '');
      setTempSelectedSubModel(selected.selected_model_id || '');
      setAvailableModels([]);
    }
  };

  // 保存当前的 API 地址及密钥配置
  const saveApiConfiguration = async () => {
    const selected = models.find(m => m.id === selectedConfigId);
    if (!selected) return;

    try {
      const res = await fetch('http://localhost:8000/api/chat/models/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: selectedConfigId,
          base_url: tempBaseUrl,
          api_key: tempApiKey,
          protocol: selected.protocol,
          selected_model_id: tempSelectedSubModel
        })
      });
      if (res.ok) {
        fetchModels();
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统设置] 成功保存 API 配置：《${selected.name}》的新参数。` }
        ]);
      }
    } catch (e) {
      console.error(e);
      alert('保存失败，请检查网络或后端状态。');
    }
  };

  // 应用当前选中的具体子模型 (并切为活动配置)
  const saveSelectedModel = async () => {
    const selected = models.find(m => m.id === selectedConfigId);
    if (!selected) return;

    try {
      // 1. 先同步保存修改
      await fetch('http://localhost:8000/api/chat/models/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: selectedConfigId,
          base_url: tempBaseUrl,
          api_key: tempApiKey,
          protocol: selected.protocol,
          selected_model_id: tempSelectedSubModel
        })
      });
      
      // 2. 切换当前模型为激活状态
      const res = await fetch('http://localhost:8000/api/chat/switch_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedConfigId })
      });
      
      if (res.ok) {
        const data = await res.json();
        setActiveModel(data.active_model);
        fetchModels();
        fetchStatus();
        setShowApiMenu(false); // 关闭弹窗
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统设置] 已成功应用模型并激活：${data.active_model} (${tempSelectedSubModel || '默认'})` }
        ]);
      }
    } catch (e) {
      console.error(e);
      alert('应用失败，请检查后端状态。');
    }
  };

  // 刷新可用子模型列表
  const refreshAvailableModels = async () => {
    setLoadingModels(true);
    try {
      const selected = models.find(m => m.id === selectedConfigId);
      const protocol = selected ? selected.protocol : 'openai';
      const url = `http://localhost:8000/api/chat/models/available?base_url=${encodeURIComponent(tempBaseUrl)}&api_key=${encodeURIComponent(tempApiKey)}&protocol=${protocol}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
          setAvailableModels(data.models || []);
          if (data.models && data.models.length > 0 && !tempSelectedSubModel) {
            setTempSelectedSubModel(data.models[0]);
          }
        } else {
          setAvailableModels([]);
          console.error("API error:", data.message);
          alert("获取可用模型列表失败: " + data.message + "\n\n提示：某些第三方代理站点(如公益站)可能不支持直接获取模型列表接口，此时请在下方输入框手动输入模型名称(如 gpt-4o 等)。");
        }
      }
    } catch (e) {
      console.error(e);
      alert('无法连接到该 API 获取可用模型列表，请确认地址无误且服务正常启动。');
    } finally {
      setLoadingModels(false);
    }
  };

  // 处理右侧面板的基础模型切换
  const handleModelChange = async (modelId) => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/switch_model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: modelId })
      });
      if (res.ok) {
        const data = await res.json();
        setActiveModel(data.active_model);
        fetchModels();
        fetchStatus();
        
        const switchedObj = models.find(m => m.id === parseInt(modelId));
        if (switchedObj) {
          setSelectedConfigId(switchedObj.id);
          setTempBaseUrl(switchedObj.base_url);
          setTempApiKey(switchedObj.api_key || '');
          setTempSelectedSubModel(switchedObj.selected_model_id || '');
        }

        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `已成功切换配置源至: ${data.active_model}` }
        ]);
      }
    } catch (e) {
      console.error('Failed to switch model:', e);
    }
  };

  // 斜杠命令输入处理
  const handleInputChange = (e) => {
    const value = e.target.value;
    setInputText(value);

    if (value.startsWith('/')) {
      const query = value.slice(1).toLowerCase();
      const matched = COMMANDS.filter(c => c.cmd.toLowerCase().includes(query) || c.desc.includes(query));
      setFilteredCommands(matched);
      setShowCommandList(matched.length > 0);
      setActiveCommandIndex(0);
    } else {
      setShowCommandList(false);
    }
  };

  // 处理键盘操作
  const handleKeyDown = (e) => {
    if (showCommandList) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveCommandIndex(prev => (prev + 1) % filteredCommands.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveCommandIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        selectCommand(filteredCommands[activeCommandIndex]);
      } else if (e.key === 'Escape') {
        setShowCommandList(false);
      }
    } else {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    }
  };

  const selectCommand = (command) => {
    setInputText(command.cmd + ' ');
    setShowCommandList(false);
    inputRef.current?.focus();
  };

  // 快速执行斜杠指令（供快捷按钮调用）
  const executeSlashCommand = async (cmdText) => {
    if (isStreaming) return;
    const nextMessages = [...messages, { role: 'user', content: cmdText }];
    setMessages(nextMessages);
    await triggerAIResponse(nextMessages);
  };

  // 发送对话消息
  const sendMessage = async () => {
    if (!inputText.trim() || isStreaming) return;

    const userText = inputText.trim();
    setInputText('');
    setShowCommandList(false);

    const nextMessages = [...messages, { role: 'user', content: userText }];
    setMessages(nextMessages);
    await triggerAIResponse(nextMessages);
  };

  // 请求 API 获取流式回复
  const triggerAIResponse = async (history) => {
    setIsStreaming(true);
    const apiPayload = history.filter(m => m.role === 'user' || m.role === 'assistant');

    try {
      const response = await fetch('http://localhost:8000/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          messages: apiPayload,
          persona_type: personaType,
          current_file_path: selectedFilePath
        })
      });

      if (!response.ok) {
        throw new Error('Server returned an error');
      }

      if (!response.body) {
        throw new Error('No response stream body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;

      setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }]);

      let accumulatedContent = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6).trim();
                const parsed = JSON.parse(jsonStr);
                
                if (parsed && parsed.type === 'system_hint') {
                  setMessages(prev => {
                    const updated = [...prev];
                    const last = updated.pop();
                    updated.push({ role: 'system_info', content: parsed.text });
                    updated.push(last);
                    return updated;
                  });
                  continue;
                }

                if (parsed && parsed.type === 'open_explainer') {
                  // 通过 postMessage 发送给父级(VS Code Extension) 以打开文件
                  window.parent.postMessage({ type: 'openExplainer', filePath: parsed.filePath }, '*');
                  continue;
                }

                if (parsed && parsed.text) {
                  accumulatedContent += parsed.text;
                  
                  let displayContent = accumulatedContent;
                  const thoughtMatch = accumulatedContent.match(/【此刻内心】[：:]([\s\S]*)$/);
                  if (thoughtMatch) {
                    displayContent = accumulatedContent.replace(/【此刻内心】[：:][\s\S]*$/, '').trim();
                    setCurrentThought(thoughtMatch[1].trim());
                  }

                  setMessages(prev => {
                    const updated = [...prev];
                    updated[updated.length - 1] = {
                      role: 'assistant',
                      content: displayContent,
                      streaming: true
                    };
                    return updated;
                  });
                }
              } catch (e) {
                // Ignore parse error
              }
            }
          }
        }
      }

      setMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0) {
          updated[updated.length - 1].streaming = false;
        }
        return updated;
      });

      fetchStatus();

    } catch (e) {
      console.error(e);
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `*脸色微变，捂着额头，有些懊恼地蹙眉道：*“哎呀夫君...奴家好像开小差了（无法连接到后端，请确保 FastAPI 处于运行中）。要不咱们稍后再试？”` }
      ]);
    } finally {
      setIsStreaming(false);
    }
  };

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('mei_theme', nextTheme);
  };

  return (
    <div 
      className={`app-container ${isVsCode ? 'vscode-env' : 'web-env'} theme-${theme}`} 
      style={{ 
        '--chat-font-size': `${fontSize}px`,
        '--avatar-size': `${avatarSize}px`,
        '--name-font-size': `${nameFontSize}px`
      }}
    >
      {/* 顶部工具栏 */}
      <header className="header-bar">
        {/* 左上角：数据库图标 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
          <button
            className="cc-icon-btn"
            onClick={() => setShowDbViewer(true)}
            title="查看数据库"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M14 3c0 1.1-2.7 2-6 2S2 4.1 2 3s2.7-2 6-2 6 .9 6 2zm0 4c0 1.1-2.7 2-6 2S2 8.1 2 7V5c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm0 4c0 1.1-2.7 2-6 2S2 12.1 2 11V9c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm-6 4c-3.3 0-6-.9-6-2v-2c.8.6 2.3 1 4 1s3.2-.4 4-1v2c0 1.1-2.7 2-6 2z"/>
            </svg>
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
          
          {/* 主题切换按钮 */}
          <button 
            className="header-btn" 
            onClick={toggleTheme}
            title="切换明暗主题"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            {theme === 'light' ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8.5 2.5a6 6 0 1 0 5 9.8c-.5-.4-1.2-.2-1.4.4a4.5 4.5 0 1 1-5.1-6c.6-.2.8-.9.4-1.4a5.9 5.9 0 0 0 1.1-2.8z"/></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9zm0-2a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1c0-.4.3-.75.75-.75zm0 11a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1c0-.4.3-.75.75-.75zm5.66-8.24a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 1 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zm-8.48 8.48a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 1 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zM14.5 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1c.4 0 .75.3.75.75zM3.5 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1c.4 0 .75.3.75.75zm10.16 4.34a.75.75 0 0 1-1.06 0l-.7-.7a.75.75 0 1 1 1.06-1.06l.7.7a.75.75 0 0 1 0 1.06zm-8.48-8.48a.75.75 0 0 1-1.06 0l-.7-.7a.75.75 0 1 1 1.06-1.06l.7.7a.75.75 0 0 1 0 1.06z"/></svg>
            )}
          </button>

          {/* 大纲与状态面板切换按钮（移动端/窄边栏专属） */}
          <button 
            className="header-btn mobile-only-btn" 
            onClick={() => setShowMobileStatus(!showMobileStatus)}
            title="大纲与状态"
            style={{ background: showMobileStatus ? 'var(--accent-pink)' : '', color: showMobileStatus ? 'white' : '', display: 'flex', alignItems: 'center' }}
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '2px' }}><path d="M2 3h12v1H2V3zm0 4h12v1H2V7zm0 4h12v1H2v-1z"/></svg>
            <span>大纲/属性</span>
          </button>

          {/* 字体大小设置下拉菜单 */}
          <div className="settings-dropdown-container">
            <button 
              className="header-btn" 
              onClick={() => {
                setShowFontMenu(!showFontMenu);
                setShowApiMenu(false);
              }}
              title="UI 设置"
              style={{ display: 'flex', alignItems: 'center' }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '2px' }}><path d="M9.1 1.1L8.8 2.5C8.3 2.7 7.8 3 7.3 3.3L6.0 2.5L4.4 4.1L5.3 5.4C5.0 5.9 4.7 6.4 4.5 6.9L3.1 7.2V9.4L4.5 9.7C4.7 10.2 5.0 10.7 5.3 11.2L4.4 12.5L6.0 14.1L7.3 13.3C7.8 13.6 8.3 13.9 8.8 14.1L9.1 15.5H11.3L11.6 14.1C12.1 13.9 12.6 13.6 13.1 13.3L14.4 14.1L16.0 12.5L15.1 11.2C15.4 10.7 15.7 10.2 15.9 9.7L17.3 9.4V7.2L15.9 6.9C15.7 6.4 15.4 5.9 15.1 5.4L16.0 4.1L14.4 2.5L13.1 3.3C12.6 3.0 12.1 2.7 11.6 2.5L11.3 1.1H9.1zm1.1 4.5C11.9 5.6 13.0 6.7 13.0 8.0s-1.1 2.4-2.4 2.4S8.2 9.3 8.2 8.0s1.1-2.4 2.4-2.4z" transform="scale(0.85) translate(1, 1)"/></svg>
              <span>UI设置</span>
            </button>
            {showFontMenu && (
              <div 
                className="settings-popover" 
                style={{
                  position: 'absolute',
                  top: '36px',
                  right: 0,
                  width: '320px',
                  background: 'var(--bg-panel)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '16px',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 1000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <h4 style={{ margin: 0, fontSize: '13px', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>
                  ⚙️ UI 设置
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  
                  {/* 头像大小设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>头像大小: {avatarSize}px</label>
                    <input 
                      type="range" 
                      min="24" 
                      max="64" 
                      value={avatarSize} 
                      onChange={(e) => {
                        const size = parseInt(e.target.value);
                        setAvatarSize(size);
                        localStorage.setItem('avatar_size', size.toString());
                      }} 
                      style={{ width: '100%', accentColor: 'var(--accent-pink)' }} 
                    />
                  </div>

                  {/* 字体设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>字体大小: {fontSize}px</label>
                    <input 
                      type="range" 
                      min="12" 
                      max="24" 
                      value={fontSize} 
                      onChange={handleFontSizeChange} 
                      style={{ width: '100%', accentColor: 'var(--accent-pink)' }} 
                    />

                  </div>

                  {/* 名字大小设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>名字大小: {nameFontSize}px</label>
                    <input 
                      type="range" 
                      min="10" 
                      max="24" 
                      value={nameFontSize} 
                      onChange={handleNameFontSizeChange} 
                      style={{ width: '100%', accentColor: 'var(--accent-pink)' }} 
                    />
                  </div>

                  {/* 人设切换 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>导师人设类型</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => handlePersonaTypeChange('simplified')}
                        style={{
                          flex: 1, padding: '6px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)',
                          background: personaType === 'simplified' ? 'var(--accent-pink)' : 'var(--bg-secondary)',
                          color: personaType === 'simplified' ? 'white' : 'var(--text-primary)',
                          cursor: personaType === 'simplified' ? 'default' : 'pointer'
                        }}
                      >精简</button>
                      <button
                        onClick={() => handlePersonaTypeChange('original')}
                        style={{
                          flex: 1, padding: '6px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)',
                          background: personaType === 'original' ? 'var(--accent-pink)' : 'var(--bg-secondary)',
                          color: personaType === 'original' ? 'white' : 'var(--text-primary)',
                          cursor: personaType === 'original' ? 'default' : 'pointer'
                        }}
                      >原版</button>
                    </div>
                  </div>

                  {/* 头像设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>全局头像设置</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        onClick={() => { setCropTarget('user'); fileInputRef.current.click(); }}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}
                      >
                        修改我的头像
                      </button>
                      <button 
                        onClick={() => { setCropTarget('assistant'); fileInputRef.current.click(); }}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}
                      >
                        修改导师头像
                      </button>
                    </div>
                  </div>

                </div>
              </div>
            )}
          </div>

          {/* API 设置面板 */}
          <div className="api-dropdown-container">
            <button 
              className="header-btn" 
              onClick={() => {
                setShowApiMenu(!showApiMenu);
                setShowFontMenu(false);
              }}
              title="API 配置"
              style={{ display: 'flex', alignItems: 'center' }}
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '2px' }}><path d="M10.5 1L3 8.5h4.5L6 15l7.5-7.5H9L10.5 1z"/></svg>
              <span>API 配置</span>
            </button>
            {showApiMenu && (
              <div 
                className="settings-popover" 
                style={{
                  position: 'absolute',
                  top: '36px',
                  right: 0,
                  width: '320px',
                  background: 'var(--bg-panel)',
                  backdropFilter: 'blur(10px)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  padding: '16px',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 1000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <h4 style={{ margin: 0, fontSize: '13px', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>
                  🔑 API 设置
                </h4>

                {/* 模型选择配置 (原右侧面板) */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 'bold' }}>⚡ 切换大语言模型</label>
                  <select 
                    style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--accent-pink)', outline: 'none', background: 'rgba(244, 114, 182, 0.05)', color: 'var(--accent-pink)', fontWeight: 'bold' }}
                    value={models.find(m => m.name === activeModel)?.id || ''}
                    onChange={(e) => handleModelChange(e.target.value)}
                  >
                    {models.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.protocol.toUpperCase()})
                      </option>
                    ))}
                  </select>
                  {activeSubModel && (
                    <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>
                      活动子模型: <span style={{ color: 'var(--accent-pink)', fontWeight: 'bold' }}>{activeSubModel}</span>
                    </div>
                  )}
                </div>

                <hr style={{ margin: '4px 0', border: 'none', borderTop: '1px dashed var(--border-color)' }} />
                
                {/* API 源 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>API 配置源</label>
                  <select 
                    style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                    value={selectedConfigId}
                    onChange={handleConfigSelection}
                  >
                    {models.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                </div>

                {/* Base URL */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>API 代理地址 (Base URL)</label>
                  <input 
                    type="text" 
                    value={tempBaseUrl}
                    onChange={(e) => setTempBaseUrl(e.target.value)}
                    style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                  />
                </div>

                {/* API Key */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>API 密钥 (API Key)</label>
                  <input 
                    type="password" 
                    value={tempApiKey}
                    onChange={(e) => setTempApiKey(e.target.value)}
                    style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                  />
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button 
                    onClick={saveApiConfiguration}
                    style={{
                      flex: 1,
                      padding: '6px 12px',
                      fontSize: '12px',
                      background: 'var(--accent-pink)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 'bold'
                    }}
                  >
                    保存 API 地址
                  </button>
                </div>

                {/* 子模型选择 */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px', borderTop: '1px solid var(--border-color)', paddingTop: '8px' }}>
                  <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>🤖 可用子模型</span>
                    <button 
                      onClick={refreshAvailableModels} 
                      disabled={loadingModels}
                      style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '11px', color: 'var(--accent-pink)' }}
                    >
                      {loadingModels ? '加载中...' : '🔄 刷新列表'}
                    </button>
                  </label>
                  <input 
                    list="available-models"
                    placeholder="请选择或手动输入模型名 (如 gpt-4o)"
                    value={tempSelectedSubModel}
                    onChange={(e) => setTempSelectedSubModel(e.target.value)}
                    style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                  />
                  <datalist id="available-models">
                    {availableModels.map(m => (
                      <option key={m} value={m} />
                    ))}
                  </datalist>

                </div>

                <button 
                  onClick={saveSelectedModel}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    background: 'var(--success)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    width: '100%'
                  }}
                >
                  应用当前模型
                </button>

                {/* 知识库后端配置 */}
                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <h4 style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 'bold' }}>📚 知识库后端</h4>
                  
                  {/* 三档单选 */}
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {[
                      { val: 'chromadb', label: '🚀 ChromaDB', tip: '本地向量库，轻量推荐' },
                      { val: 'ragflow',  label: '☁️ RAGFlow',  tip: '需要Docker运行' },
                      { val: 'external', label: '🔗 外部API',  tip: 'Dify/FastGPT等' }
                    ].map(opt => (
                      <button
                        key={opt.val}
                        title={opt.tip}
                        onClick={() => setRagConfig(prev => ({ ...prev, backend_type: opt.val }))}
                        style={{
                          flex: 1,
                          padding: '4px 2px',
                          fontSize: '10px',
                          border: `1px solid ${ragConfig.backend_type === opt.val ? 'var(--accent-pink)' : 'var(--border-color)'}`,
                          borderRadius: '4px',
                          background: ragConfig.backend_type === opt.val ? 'var(--accent-pink)' : 'transparent',
                          color: ragConfig.backend_type === opt.val ? 'white' : 'var(--text-secondary)',
                          cursor: 'pointer',
                          fontWeight: ragConfig.backend_type === opt.val ? 'bold' : 'normal',
                          transition: 'all 0.2s'
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>

                  {/* RAGFlow 配置项 */}
                  {ragConfig.backend_type === 'ragflow' && (
                    <>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>RAGFlow API 地址</label>
                        <input type="text" value={ragConfig.ragflow_url}
                          onChange={e => setRagConfig(prev => ({ ...prev, ragflow_url: e.target.value }))}
                          placeholder="http://localhost/api/v1"
                          style={{ padding: '5px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                        />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>RAGFlow API Key</label>
                        <input type="password" value={ragConfig.ragflow_key}
                          onChange={e => setRagConfig(prev => ({ ...prev, ragflow_key: e.target.value }))}
                          placeholder="ragflow-xxxx"
                          style={{ padding: '5px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                        />
                      </div>
                    </>
                  )}

                  {/* 外部 API 配置项 */}
                  {ragConfig.backend_type === 'external' && (
                    <>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>外部 RAG 接口地址</label>
                        <input type="text" value={ragConfig.external_url}
                          onChange={e => setRagConfig(prev => ({ ...prev, external_url: e.target.value }))}
                          placeholder="http://your-rag-service/api"
                          style={{ padding: '5px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                        />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                        <label style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>外部 API Key（可选）</label>
                        <input type="password" value={ragConfig.external_key}
                          onChange={e => setRagConfig(prev => ({ ...prev, external_key: e.target.value }))}
                          placeholder="Bearer token 或留空"
                          style={{ padding: '5px', fontSize: '11px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                        />
                      </div>
                    </>
                  )}

                  {ragConfig.backend_type === 'chromadb' && (
                    <p style={{ margin: 0, fontSize: '10px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      ✅ ChromaDB 已内置于后端，无需外部服务。记忆和知识库文件均以语义向量形式本地存储于 <code>backend/rag_index/</code>。
                    </p>
                  )}

                  <button
                    onClick={saveRagConfig}
                    disabled={savingRag}
                    style={{
                      padding: '5px 12px',
                      fontSize: '11px',
                      background: savingRag ? 'var(--text-secondary)' : 'var(--accent-pink)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: savingRag ? 'not-allowed' : 'pointer',
                      fontWeight: 'bold',
                      width: '100%'
                    }}
                  >
                    {savingRag ? '保存中...' : '💾 保存知识库配置'}
                  </button>
                </div>
              </div>

            )}
          </div>

          <div className="connection-status">
            <div className={`status-indicator ${isStreaming ? 'pulse' : ''}`} />
            <span>{isStreaming ? '媚吻锋思考中...' : '课堂连通正常'}</span>
          </div>
        </div>
      </header>

      {/* 主工作区 */}
      <main className="main-layout">
        {/* 左侧面板：原本是文件树，现已被抛弃，将直接潜入 VS Code 原生生态 */}
        {/* 中间面板：核心对话区 */}
        <ChatPanel
          isVsCode={isVsCode}
          messages={messages}
          activeModel={activeModel}
          userAvatar={userAvatar}
          assistantAvatar={assistantAvatar}
          setCropTarget={setCropTarget}
          fileInputRef={fileInputRef}
          showCommandList={showCommandList}
          filteredCommands={filteredCommands}
          activeCommandIndex={activeCommandIndex}
          selectCommand={selectCommand}
          inputRef={inputRef}
          inputText={inputText}
          handleInputChange={handleInputChange}
          handleKeyDown={handleKeyDown}
          sendMessage={sendMessage}
          isStreaming={isStreaming}
          executeSlashCommand={executeSlashCommand}
          chatEndRef={chatEndRef}
          onEditAndResend={handleEditAndResend}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onNewSession={handleNewSession}
          onSwitchSession={handleSwitchSession}
          onDeleteSession={handleDeleteSession}
          showSessionList={showSessionList}
          setShowSessionList={setShowSessionList}
        />

        {/* 右侧面板：导师人设与课程大纲 */}
        <div className={`right-panel-container ${showMobileStatus ? 'show-mobile' : ''}`}>
          <StatusPanel
            currentThought={currentThought}
            affection={affection}
            personaType={personaType}
            handlePersonaTypeChange={handlePersonaTypeChange}
            models={models}
            activeModel={activeModel}
            handleModelChange={handleModelChange}
            activeSubModel={activeSubModel}
            courseProgress={courseProgress}
          />
          {showMobileStatus && (
            <button className="mobile-close-btn" onClick={() => setShowMobileStatus(false)}>
              ✖ 返回聊天
            </button>
          )}
        </div>
      </main>

      {/* 隐藏的文件输入框 */}
      <input 
        type="file" 
        accept="image/*" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        onChange={handleFileChange} 
      />

      {/* 头像裁剪弹窗 */}
      {showCropModal && (
        <CropModal 
          imageSrc={imageSrc} 
          onClose={() => { setShowCropModal(false); setImageSrc(null); }} 
          onSave={handleSaveCrop} 
        />
      )}

      {/* 内置数据库查看器 */}
      {showDbViewer && (
        <DatabaseViewer onClose={() => setShowDbViewer(false)} />
      )}
    </div>
  );
}
