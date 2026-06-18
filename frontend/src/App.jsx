import { API_BASE } from './config';
import React, { useState, useEffect, useRef } from 'react';
import FileTree from './components/FileTree';
import ChatPanel from './components/ChatPanel';
import StatusPanel from './components/StatusPanel';
import CropModal from './components/CropModal';
import DatabaseViewer from './components/DatabaseViewer';

const COMMANDS = [
  { cmd: '/lesson', desc: '开始新的课时，进入授课模式' },
  { cmd: '/submit', desc: '进行课题考核，AI会对你进行提问' },
  { cmd: '/reward', desc: '获取好感奖励，触发狐妖娘溺爱互动' },
  { cmd: '/summarize', desc: '压缩并保存当前记忆，释放上下文' },
  { cmd: '/prepare', desc: '将当前选定的讲义文件上传同步至RAGFlow知识库' },
  { cmd: '/plan', desc: '根据当前进度，重新调整课程大纲' }
];


const TIPS_LIST = [
  "可以在对话框输入 / 开头的指令来触发特殊事件哦~",
  "媚吻锋不仅是你的修行导师，还是个爱吃醋的小狐狸。",
  "右侧边栏可以随时切换大纲状态、UI设置和API配置。",
  "如果不喜欢当前的回答风格，可以随时切换导师的人设（精简/原版）。",
  "知识库后端支持本地 ChromaDB 或外部的 RAGFlow。",
  "您可以上传自定义的背景图片，或者调整毛玻璃特效的开关。",
  "点击左上角的数据库图标，可以实时查看当前的记忆体状态。",
  "不同的代理站点可能不支持获取可用模型列表，可以尝试手动输入模型名称。",
  "开发这个插件是为了让你在学习编程的路上不再孤单~",
  "API 配置源可以随时切换，并记得填写你自己的 API Key！"
];

export default function App() {
  const [sessions, setSessions] = useState([]);

  // 后端加载与超时状态
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting'); // 'connecting', 'restarting', 'timeout', 'failed'
  const [pollingCount, setPollingCount] = useState(0);
  const [currentTip, setCurrentTip] = useState(TIPS_LIST[0]);

  const [activeSessionId, setActiveSessionId] = useState('');
  const [messages, setMessages] = useState([]);

  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef(null);
  const [showDbViewer, setShowDbViewer] = useState(false);
  const [showMobileStatus, setShowMobileStatus] = useState(false);
  const [theme, setTheme] = useState(localStorage.getItem('mei_theme') || 'light');
  const [showSessionList, setShowSessionList] = useState(false);

  // 检测是否在 VS Code 插件环境中运行
  const isVsCode = new URLSearchParams(window.location.search).get('env') === 'vscode';

  const syncSessionToBackend = async (session) => {
    try {
      await fetch(`${API_BASE}/api/chat/sessions/save`, {
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
      await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`, {
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

  // 当消息列表更新或切换会话时，自动解析最近一次的内心独白
  useEffect(() => {
    if (messages && messages.length > 0) {
      const lastAsst = [...messages].reverse().find(m => m.role === 'assistant');
      if (lastAsst) {
        let textToParse = '';
        if (lastAsst.blocks) {
          textToParse = lastAsst.blocks.filter(b => b.type === 'text').map(b => b.text).join('');
        } else if (lastAsst.content) {
          textToParse = lastAsst.content;
        }
        const thoughtMatch = textToParse.match(/【此刻内心】[：:]\s*[（(]([\s\S]*?)[)）]/g);
        if (thoughtMatch && thoughtMatch.length > 0) {
          const lastThought = thoughtMatch[thoughtMatch.length - 1];
          const innerMatch = lastThought.match(/[（(]([\s\S]*?)[)）]/);
          if (innerMatch) {
            setCurrentThought(innerMatch[1].trim());
          }
        }
      }
    }
  }, [messages, activeSessionId]);

  // 头像裁剪相关
  const storedUser = localStorage.getItem('user_avatar');
  const initialUser = (storedUser === '🎓' || !storedUser) ? 'default_student' : storedUser;
  const storedAssistant = localStorage.getItem('assistant_avatar');
  const initialAssistant = (storedAssistant === '🦊' || !storedAssistant) ? 'default_tutor' : storedAssistant;

  const [userAvatar, setUserAvatar] = useState(initialUser);
  const [assistantAvatar, setAssistantAvatar] = useState(initialAssistant);
  const [cropTarget, setCropTarget] = useState('user');
  const [showCropModal, setShowCropModal] = useState(false);
  const [imageSrc, setImageSrc] = useState(null);
  const fileInputRef = useRef(null);

  const [bgImage, setBgImage] = useState(localStorage.getItem('bg_image') || '');
  const [enableBlur, setEnableBlur] = useState(localStorage.getItem('enable_blur') !== 'false');
  const bgFileInputRef = useRef(null);

  const handleBgUpload = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (event) => {
        const dataUrl = event.target.result;
        try {
          localStorage.setItem('bg_image', dataUrl);
          setBgImage(dataUrl);
        } catch (err) {
          alert('图片过大，无法保存到本地存储，请选择较小的图片。');
        }
      };
      reader.readAsDataURL(file);
      e.target.value = null;
    }
  };

  const handleResetBg = () => {
    localStorage.removeItem('bg_image');
    setBgImage('');
  };

  const toggleBlur = () => {
    const newVal = !enableBlur;
    setEnableBlur(newVal);
    localStorage.setItem('enable_blur', newVal.toString());
  };

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

  const [maxTokens, setMaxTokens] = useState(parseInt(localStorage.getItem('max_tokens')) || 8192);
  const handleMaxTokensChange = (e) => {
    const val = parseInt(e.target.value) || 0;
    setMaxTokens(val);
    localStorage.setItem('max_tokens', val.toString());
  };

  // 状态与配置
  const [activeModel, setActiveModel] = useState('DeepSeek (在线)');
  const [activeSubModel, setActiveSubModel] = useState('');
  const [models, setModels] = useState([]);
  const [courseProgress, setCourseProgress] = useState([]);
  const [affection, setAffection] = useState(100);
  const [personaType, setPersonaType] = useState(localStorage.getItem('persona_type') || 'simplified');

  // 酒馆式 API 设置和字体弹窗状态
  const [activeRightTab, setActiveRightTab] = useState('status');
  const [selectedConfigId, setSelectedConfigId] = useState(1);
  const [tempBaseUrl, setTempBaseUrl] = useState('');
  const [tempApiKey, setTempApiKey] = useState('');
  const [tempMaxContextTokens, setTempMaxContextTokens] = useState('');
  const [tempSelectedSubModel, setTempSelectedSubModel] = useState('');
  const [availableModels, setAvailableModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // API 配置源管理相关状态
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [newConfigName, setNewConfigName] = useState('');
  const [newConfigProtocol, setNewConfigProtocol] = useState('openai');
  const [newConfigBaseUrl, setNewConfigBaseUrl] = useState('');
  const [newConfigApiKey, setNewConfigApiKey] = useState('');
  const [newConfigMaxContextTokens, setNewConfigMaxContextTokens] = useState('');
  const [renameConfigName, setRenameConfigName] = useState('');

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
    if (!isBackendReady) return;

    const loadSessions = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/sessions`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setSessions(data);
            const savedActive = localStorage.getItem('mei_wenfeng_classroom_active_session_id');
            const activeId = (savedActive && data.some(s => s.id === savedActive)) ? savedActive : data[0].id;
            setActiveSessionId(activeId);
            const activeSess = data.find(s => s.id === activeId) || data[0];
            setMessages(activeSess.messages || []);

            // Check for long-term decay
            try {
              const decayRes = await fetch(`${API_BASE}/api/chat/check_decay`);
              if (decayRes.ok) {
                const decayData = await decayRes.json();
                if (decayData.needed) {
                  setMessages(prev => [...prev, {
                    role: 'system_info',
                    type: 'decay_prompt',
                    content: '好久不见，导师需要重新整理先前的学习档案，是否立即执行？(建议切换至高性价比模型)'
                  }]);
                }
              }
            } catch(e) {
              console.error('Failed to check decay:', e);
            }
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
  }, [isBackendReady]);

  const [cursorLine, setCursorLine] = useState(1);


  // Tips 轮播
  useEffect(() => {
    if (isBackendReady) return;
    const interval = setInterval(() => {
      setCurrentTip(TIPS_LIST[Math.floor(Math.random() * TIPS_LIST.length)]);
    }, 8000);
    return () => clearInterval(interval);
  }, [isBackendReady]);

  // 后端状态探测轮询
  useEffect(() => {
    if (isBackendReady) return;

    const checkBackend = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/status`, {
          method: 'GET',
        });
        if (res.ok) {
          setIsBackendReady(true);
        } else {
          throw new Error("Not OK");
        }
      } catch (err) {
        setPollingCount(prev => prev + 1);
      }
    };

    const timer = setTimeout(checkBackend, 2000);
    return () => clearTimeout(timer);
  }, [isBackendReady, pollingCount, connectionStatus]);

  // 处理超时与重试状态流转
  useEffect(() => {
    if (isBackendReady) return;
    // 30秒大约是 15 次轮询
    if (pollingCount > 15) {
      if (connectionStatus === 'connecting') {
        setConnectionStatus('timeout');
      } else if (connectionStatus === 'restarting') {
        setConnectionStatus('failed');
      }
    }
  }, [pollingCount, isBackendReady, connectionStatus]);

  // 监听来自 VS Code 插件的消息
  useEffect(() => {
    const handleMessage = (event) => {
      const message = event.data;
      if (message.type === 'activeFileChanged' || message.type === 'cursorMoved') {
        if (message.filePath) setSelectedFilePath(message.filePath);
        if (message.cursorLine) setCursorLine(message.cursorLine);
      }
    };
    window.addEventListener('message', handleMessage);

    // 通知 VS Code 插件 Webview 已经准备好，可以发送当前活动的编辑器信息
    if (isVsCode) {
      window.parent.postMessage({ type: 'webviewReady' }, '*');
    }

    return () => window.removeEventListener('message', handleMessage);
  }, [isVsCode]);

  // 当 models 加载完成，将当前激活的 API 参数回显至设置中
  useEffect(() => {
    const active = models.find(m => m.is_active === 1);
    if (active) {
      setSelectedConfigId(active.id);
      setTempBaseUrl(active.base_url);
      setTempApiKey(active.api_key || '');
      setTempSelectedSubModel(active.selected_model_id || '');
      setTempMaxContextTokens(active.max_context_tokens || '');
    }
  }, [models]);

  // 当 API 设置菜单打开、切换配置源或代理地址变化时，自动拉取可用模型
  useEffect(() => {
    if (activeRightTab === 'api' && tempBaseUrl) {
      const fetchModelsAuto = async () => {
        setLoadingModels(true);
        try {
          const selected = models.find(m => m.id === selectedConfigId);
          const protocol = selected ? selected.protocol : 'openai';
          const url = `${API_BASE}/api/chat/models/available?base_url=${encodeURIComponent(tempBaseUrl)}&api_key=${encodeURIComponent(tempApiKey)}&protocol=${protocol}`;
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
  }, [activeRightTab, selectedConfigId, tempBaseUrl]);


  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/status`);
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
      const res = await fetch(`${API_BASE}/api/chat/models`);
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
      const res = await fetch(`${API_BASE}/api/chat/images`);
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
      const res = await fetch(`${API_BASE}/api/chat/rag/config`);
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
      const res = await fetch(`${API_BASE}/api/chat/rag/update`, {
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
      setTempMaxContextTokens(selected.max_context_tokens || '');
      setTempSelectedSubModel(selected.selected_model_id || '');
      setAvailableModels([]);
    }
  };

  // 保存当前的 API 地址及密钥配置
  const saveApiConfiguration = async () => {
    const selected = models.find(m => m.id === selectedConfigId);
    if (!selected) return;

    try {
      const res = await fetch(`${API_BASE}/api/chat/models/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: selectedConfigId,
          name: selected.name,
          base_url: tempBaseUrl,
          api_key: tempApiKey,
          max_context_tokens: tempMaxContextTokens ? parseInt(tempMaxContextTokens, 10) : null,
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
      await fetch(`${API_BASE}/api/chat/models/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: selectedConfigId,
          name: selected.name,
          base_url: tempBaseUrl,
          api_key: tempApiKey,
          max_context_tokens: tempMaxContextTokens ? parseInt(tempMaxContextTokens, 10) : null,
          protocol: selected.protocol,
          selected_model_id: tempSelectedSubModel
        })
      });

      // 2. 切换当前模型为激活状态
      const res = await fetch(`${API_BASE}/api/chat/switch_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedConfigId })
      });

      if (res.ok) {
        const data = await res.json();
        setActiveModel(data.active_model);
        fetchModels();
        fetchStatus();
        // 关闭弹窗行为取消，已变为右侧边栏常驻
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

  // 创建新的 API 配置
  const handleCreateModel = async () => {
    if (!newConfigName.trim()) {
      alert("请输入配置名称！");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/chat/models/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newConfigName.trim(),
          protocol: newConfigProtocol,
          base_url: newConfigBaseUrl.trim(),
          api_key: newConfigApiKey.trim(),
          max_context_tokens: newConfigMaxContextTokens ? parseInt(newConfigMaxContextTokens, 10) : null
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowCreateModal(false);
        setNewConfigName('');
        setNewConfigBaseUrl('');
        setNewConfigApiKey('');
        setNewConfigProtocol('openai');
        setNewConfigMaxContextTokens('');

        // 刷新列表并选中新创建的配置
        await fetchModels();
        setSelectedConfigId(data.id);
        setTempBaseUrl(newConfigBaseUrl.trim());
        setTempApiKey(newConfigApiKey.trim());
        setTempMaxContextTokens(newConfigMaxContextTokens ? parseInt(newConfigMaxContextTokens, 10) : '');
        setTempSelectedSubModel('');
        setAvailableModels([]);

        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统设置] 成功创建 API 配置源：《${newConfigName.trim()}》。` }
        ]);
      } else {
        alert(data.detail || '创建失败，请检查名称是否重复或后端状态。');
      }
    } catch (e) {
      console.error(e);
      alert('创建失败，请确认后端连接正常。');
    }
  };

  // 重命名 API 配置
  const handleRenameModel = async () => {
    if (!renameConfigName.trim()) {
      alert("请输入新名称！");
      return;
    }
    const selected = models.find(m => m.id === selectedConfigId);
    if (!selected) return;
    if (selected.is_active === 1) {
      alert("当前激活的配置不能重命名！");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/chat/models/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: selectedConfigId,
          name: renameConfigName.trim(),
          base_url: tempBaseUrl,
          api_key: tempApiKey,
          max_context_tokens: tempMaxContextTokens ? parseInt(tempMaxContextTokens, 10) : null,
          protocol: selected.protocol,
          selected_model_id: tempSelectedSubModel
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setShowRenameModal(false);
        setRenameConfigName('');
        await fetchModels();
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统设置] 成功将配置源重命名为：《${renameConfigName.trim()}》。` }
        ]);
      } else {
        alert(data.detail || '保存失败，可能名称已存在。');
      }
    } catch (e) {
      console.error(e);
      alert('保存失败，请检查网络或后端状态。');
    }
  };

  // 删除 API 配置
  const handleDeleteModel = async () => {
    const selected = models.find(m => m.id === selectedConfigId);
    if (!selected) return;
    if (selected.is_active === 1) {
      alert("当前激活的配置不能删除！");
      return;
    }
    if (models.length <= 1) {
      alert("不能删除最后一个配置！");
      return;
    }
    if (!window.confirm(`确认删除 API 配置源 《${selected.name}》 吗？`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/chat/models/${selectedConfigId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        // 找到另一个配置并选中
        const remaining = models.filter(m => m.id !== selectedConfigId);
        const nextSelected = remaining[0];

        await fetchModels();

        if (nextSelected) {
          setSelectedConfigId(nextSelected.id);
          setTempBaseUrl(nextSelected.base_url);
          setTempApiKey(nextSelected.api_key || '');
          setTempMaxContextTokens(nextSelected.max_context_tokens || '');
          setTempSelectedSubModel(nextSelected.selected_model_id || '');
          setAvailableModels([]);
        }

        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统设置] 已成功删除配置源：《${selected.name}》。` }
        ]);
      } else {
        alert(data.detail || '删除失败');
      }
    } catch (e) {
      console.error(e);
      alert('删除失败，请检查网络或后端状态。');
    }
  };

  // 刷新可用子模型列表
  const refreshAvailableModels = async () => {
    setLoadingModels(true);
    try {
      const selected = models.find(m => m.id === selectedConfigId);
      const protocol = selected ? selected.protocol : 'openai';
      const url = `${API_BASE}/api/chat/models/available?base_url=${encodeURIComponent(tempBaseUrl)}&api_key=${encodeURIComponent(tempApiKey)}&protocol=${protocol}`;
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
      const res = await fetch(`${API_BASE}/api/chat/switch_model`, {
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
          setTempMaxContextTokens(switchedObj.max_context_tokens || '');
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
    } else if (value.includes('@')) {
      // Very basic @ detection
      const parts = value.split('@');
      const query = parts[parts.length - 1].toLowerCase();
      const matched = [
        { cmd: '@current_file', desc: '引用当前激活的文件' },
        { cmd: '@workspace', desc: '扫描整个工作区' }
      ].filter(c => c.cmd.toLowerCase().includes(query) || c.desc.includes(query));
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
    if (command.cmd.startsWith('@')) {
      const parts = inputText.split('@');
      parts.pop();
      setInputText(parts.join('@') + command.cmd + ' ');
    } else {
      setInputText(command.cmd + ' ');
    }
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

  // 停止对话生成
  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  // 请求 API 获取流式回复
  const triggerAIResponse = async (history) => {
    setIsStreaming(true);
    abortControllerRef.current = new AbortController();
    const apiPayload = history.filter(m => m.role === 'user' || m.role === 'assistant');

    try {
      const response = await fetch(`${API_BASE}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortControllerRef.current.signal,
        body: JSON.stringify({
          messages: apiPayload,
          persona_type: personaType,
          current_file_path: selectedFilePath,
          cursor_line: cursorLine,
          custom_max_tokens: maxTokens
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

      setMessages(prev => [...prev, { role: 'assistant', blocks: [], streaming: true }]);

      let currentBlocks = [];

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
                if (jsonStr === '[DONE]' || !jsonStr) continue;
                const parsed = JSON.parse(jsonStr);

                if (parsed.type === 'system_hint') {
                  setMessages(prev => {
                    const updated = [...prev];
                    const last = updated.pop();
                    updated.push({ role: 'system_info', content: parsed.text, icon: parsed.icon });
                    updated.push(last);
                    return updated;
                  });
                  continue;
                }

                if (parsed.type === 'open_explainer') {
                  window.parent.postMessage({ type: 'openExplainer', filePath: parsed.filePath }, '*');
                  continue;
                }

                if (parsed.type === 'thinking') {
                  let lastBlock = currentBlocks[currentBlocks.length - 1];
                  if (!lastBlock || lastBlock.type !== 'thinking') {
                    currentBlocks.forEach(b => { if (b.type === 'thinking') b.status = 'done'; });
                    currentBlocks.push({ type: 'thinking', text: parsed.text || '', status: 'running' });
                  } else {
                    lastBlock.text += (parsed.text || '');
                  }
                } else if (parsed.type === 'tool_start') {
                  currentBlocks.forEach(b => { if (b.type === 'thinking') b.status = 'done'; });
                  currentBlocks.push({ type: 'tool', tool_name: parsed.tool_name, command: parsed.command, output: '', status: 'running' });
                } else if (parsed.type === 'tool_output') {
                  let lastBlock = currentBlocks[currentBlocks.length - 1];
                  if (lastBlock && lastBlock.type === 'tool') {
                    lastBlock.output += (parsed.text || '');
                  }
                } else if (parsed.type === 'tool_end') {
                  let lastBlock = currentBlocks[currentBlocks.length - 1];
                  if (lastBlock && lastBlock.type === 'tool') {
                    lastBlock.status = 'done';
                  }
                } else if (parsed.type === 'text' || parsed.text) {
                  currentBlocks.forEach(b => { if (b.type === 'thinking') b.status = 'done'; });
                  let lastBlock = currentBlocks[currentBlocks.length - 1];
                  if (!lastBlock || lastBlock.type !== 'text') {
                    currentBlocks.push({ type: 'text', text: parsed.text || '' });
                  } else {
                    lastBlock.text += (parsed.text || '');
                  }
                }

                setMessages(prev => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg.role === 'assistant') {
                    lastMsg.blocks = [...currentBlocks];
                    // Keep plain text content for compatibility with older rendering (like the prompt match logic below)
                    let displayContent = currentBlocks.filter(b => b.type === 'text').map(b => b.text).join('');
                    const thoughtMatchArray = displayContent.match(/【此刻内心】[：:]\s*[（(]([\s\S]*?)[)）]/g);
                    if (thoughtMatchArray && thoughtMatchArray.length > 0) {
                      const lastThought = thoughtMatchArray[thoughtMatchArray.length - 1];
                      const innerMatch = lastThought.match(/[（(]([\s\S]*?)[)）]/);
                      if (innerMatch) {
                        setCurrentThought(innerMatch[1].trim());
                      }
                      displayContent = displayContent.replace(/【此刻内心】[：:]\s*[（(][\s\S]*?[)）]/g, '').trim();
                    }
                    lastMsg.content = displayContent;
                  }
                  return updated;
                });
              } catch (e) {
                // Ignore parse error
              }
            }
          }
        }
      }

      setMessages(prev => {
        return prev.map(msg => {
          if (msg.streaming) {
            const newMsg = { ...msg, streaming: false };
            if (newMsg.blocks) {
              newMsg.blocks.forEach(b => b.status = 'done');

              // Bug2 修复：GG公益站/DeepSeek 等代理模型会把最终故事全部放进
              // reasoning_content（type=thinking），导致 delta.content 为空，没有 text block。
              // 检测：流结束后如果没有 text block 但有 thinking block，
              // 把最后一个 thinking block 的内容升级为 text block（正文区域显示）。
              const hasText = newMsg.blocks.some(b => b.type === 'text' && b.text && b.text.trim());
              if (!hasText) {
                // 找最后一个有内容的 thinking block
                const thinkingBlocks = newMsg.blocks.filter(b => b.type === 'thinking' && b.text && b.text.trim());
                if (thinkingBlocks.length > 0) {
                  const lastThinking = thinkingBlocks[thinkingBlocks.length - 1];
                  lastThinking.type = 'text';
                }
              }
            }
            return newMsg;
          }
          return msg;
        });
      });

      fetchStatus();

    } catch (e) {
      if (e.name === 'AbortError') {
        console.log('Generation aborted by user.');
      } else {
        console.error(e);
        const errorMsg = `*脸色微变，捂着额头，有些懊恼地蹙眉道：*“哎呀夫君...奴家好像开小差了（后端连接中断，可能是代理超时或 FastAPI 崩溃）。要不咱们重试一下？”\n\n**前端报错详情:** \`${e.message}\``;
        setMessages(prev => {
          const updated = prev.map(msg => {
            if (msg.streaming) {
              return { 
                ...msg, 
                streaming: false,
                content: (msg.content || '') + `\n\n[系统错误] ` + errorMsg 
              };
            }
            return msg;
          });
          
          // 如果没有任何消息在 streaming 状态，就在末尾追加报错
          if (!prev.some(msg => msg.streaming)) {
            updated.push({ role: 'assistant', content: `[系统错误] ` + errorMsg });
          }
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
      // Bug1 修复：无论正常/异常/中断，都确保 running 状态的 block 被标记为 done
      // 防止 Thinking 黄灯在任何情况下永久不灭
      setMessages(prev => prev.map(msg => {
        if (msg.streaming || (msg.blocks && msg.blocks.some(b => b.status === 'running'))) {
          const newMsg = { ...msg, streaming: false };
          if (newMsg.blocks) newMsg.blocks.forEach(b => { if (b.status === 'running') b.status = 'done'; });
          return newMsg;
        }
        return msg;
      }));
    }

  };

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('mei_theme', nextTheme);
  };

  const selectedConfig = models.find(m => m.id === selectedConfigId);
  const selectedConfigIsActive = selectedConfig ? selectedConfig.is_active === 1 : false;

  return (
    <>
      {/* 全屏加载遮罩层 */}
      {!isBackendReady && (
        <div className="startup-loading-overlay">
          <div className="loading-content-box">
            {connectionStatus === 'connecting' ? (
              <>
                <div className="bouncing-dots">
                  <div></div><div></div><div></div>
                </div>
                <h3 style={{ marginTop: '20px', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  {connectionStatus === 'restarting' ? '正在重启并重新连接中...' : (
                    <>
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                        <path d="M6 12v5c3 3 9 3 12 0v-5" />
                      </svg>
                      导师正在赶来的路上...
                    </>
                  )}
                </h3>
              </>
            ) : (
              <>
                <div className="crying-fox" style={{ marginBottom: '10px', color: 'var(--text-secondary)' }}>
                  <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" strokeWidth="2"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <circle cx="12" cy="17" r="1.5" fill="currentColor" stroke="none"></circle>
                  </svg>
                </div>
                <h3 style={{ color: 'var(--danger)', marginBottom: '16px' }}>
                  后端服务连接超时
                </h3>
                <div style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: '1.6', textAlign: 'left', background: 'var(--bg-hover)', padding: '15px', borderRadius: '8px' }}>
                  <p style={{ margin: '0 0 8px 0', fontWeight: 'bold' }}>请按照以下步骤恢复连接：</p>
                  <p style={{ margin: '4px 0' }}>1. 检查背后的黑色终端窗口是否有报错，或者是否已被关闭。</p>
                  <p style={{ margin: '4px 0' }}>2. 请手动关闭黑色终端，然后重新双击运行 <b>start.bat</b>。</p>
                  <p style={{ margin: '4px 0' }}>3. 等待终端内所有服务启动完毕后，按 <b>F5</b> 刷新本页面。</p>
                </div>
              </>
            )}
            <div className="loading-tip">
              <span className="tips-badge">TIPS</span>
              <span className="tips-text">{currentTip}</span>
            </div>
          </div>
        </div>
      )}
      <div
        className={`app-container ${isVsCode ? 'vscode-env' : 'web-env'} theme-${theme} ${!enableBlur ? 'disable-blur' : ''}`}
        style={{
          '--chat-font-size': `${fontSize}px`,
          '--avatar-size': `${avatarSize}px`,
          '--name-font-size': `${nameFontSize}px`,
          backgroundImage: bgImage ? `url(${bgImage})` : undefined
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
                <path d="M14 3c0 1.1-2.7 2-6 2S2 4.1 2 3s2.7-2 6-2 6 .9 6 2zm0 4c0 1.1-2.7 2-6 2S2 8.1 2 7V5c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm0 4c0 1.1-2.7 2-6 2S2 12.1 2 11V9c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm-6 4c-3.3 0-6-.9-6-2v-2c.8.6 2.3 1 4 1s3.2-.4 4-1v2c0 1.1-2.7 2-6 2z" />
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
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8.5 2.5a6 6 0 1 0 5 9.8c-.5-.4-1.2-.2-1.4.4a4.5 4.5 0 1 1-5.1-6c.6-.2.8-.9.4-1.4a5.9 5.9 0 0 0 1.1-2.8z" /></svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9zm0-2a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1c0-.4.3-.75.75-.75zm0 11a.75.75 0 0 1 .75.75v1a.75.75 0 0 1-1.5 0v-1c0-.4.3-.75.75-.75zm5.66-8.24a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 1 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zm-8.48 8.48a.75.75 0 0 1 0 1.06l-.7.7a.75.75 0 1 1-1.06-1.06l.7-.7a.75.75 0 0 1 1.06 0zM14.5 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1c.4 0 .75.3.75.75zM3.5 8a.75.75 0 0 1-.75.75h-1a.75.75 0 0 1 0-1.5h1c.4 0 .75.3.75.75zm10.16 4.34a.75.75 0 0 1-1.06 0l-.7-.7a.75.75 0 1 1 1.06-1.06l.7.7a.75.75 0 0 1 0 1.06zm-8.48-8.48a.75.75 0 0 1-1.06 0l-.7-.7a.75.75 0 1 1 1.06-1.06l.7.7a.75.75 0 0 1 0 1.06z" /></svg>
              )}
            </button>

            {/* 切换右侧边栏选项卡的按钮组 */}
            <button
              className="header-btn"
              onClick={() => { setActiveRightTab('status'); setShowMobileStatus(true); }}
              title="大纲与状态"
              style={{ background: activeRightTab === 'status' ? 'var(--accent-pink)' : '', color: activeRightTab === 'status' ? 'white' : '', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M2 3h12v1H2V3zm0 4h12v1H2V7zm0 4h12v1H2v-1z" /></svg>
            </button>

            <button
              className="header-btn"
              onClick={() => { setActiveRightTab('ui'); setShowMobileStatus(true); }}
              title="UI 设置"
              style={{ background: activeRightTab === 'ui' ? 'var(--accent-pink)' : '', color: activeRightTab === 'ui' ? 'white' : '', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor"><path d="M9.405 1.05c-.413-1.4-2.397-1.4-2.81 0l-.1.34a1.464 1.464 0 0 1-2.105.872l-.31-.17c-1.283-.698-2.686.705-1.987 1.987l.169.311c.446.82.023 1.841-.872 2.105l-.34.1c-1.4.413-1.4 2.397 0 2.81l.34.1a1.464 1.464 0 0 1 .872 2.105l-.17.31c-.698 1.283.705 2.686 1.987 1.987l.311-.169a1.464 1.464 0 0 1 2.105.872l.1.34c.413 1.4 2.397 1.4 2.81 0l.1-.34a1.464 1.464 0 0 1 2.105-.872l.31.17c1.283.698 2.686-.705 1.987-1.987l-.169-.311a1.464 1.464 0 0 1 .872-2.105l.34-.1c1.4-.413 1.4-2.397 0-2.81l-.34-.1a1.464 1.464 0 0 1-.872-2.105l.17-.31c.698-1.283-.705-2.686-1.987-1.987l-.311.169a1.464 1.464 0 0 1-2.105-.872l-.1-.34zM8 10.93a2.93 2.93 0 1 1 0-5.86 2.93 2.93 0 0 1 0 5.86z" /></svg>
            </button>

            <button
              className="header-btn"
              onClick={() => { setActiveRightTab('api'); setShowMobileStatus(true); }}
              title="API 配置"
              style={{ background: activeRightTab === 'api' ? 'var(--accent-pink)' : '', color: activeRightTab === 'api' ? 'white' : '', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2v4M10 2v4M3 6h10M4 6a4 4 0 0 0 8 0M8 10v4" /></svg>
            </button>



            <div className="connection-status">
              <div className={`status-indicator ${isStreaming ? 'pulse' : ''}`} />
              <span>{isStreaming ? '导师思考中...' : '课堂连通正常'}</span>
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
            models={models}
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
            stopGeneration={stopGeneration}
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
            selectedFilePath={selectedFilePath}
          />

          {/* 右侧面板：导师人设与课程大纲 */}
          <div className={`right-panel-container ${showMobileStatus ? 'show-mobile' : ''}`}>
            {activeRightTab === 'status' && (
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
            )}

            {activeRightTab === 'ui' && (
              <section className="ide-panel right-panel">
                <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '6px' }}>
                      <path d="M9.1 1.1L8.8 2.5C8.3 2.7 7.8 3 7.3 3.3L6.0 2.5L4.4 4.1L5.3 5.4C5.0 5.9 4.7 6.4 4.5 6.9L3.1 7.2V9.4L4.5 9.7C4.7 10.2 5.0 10.7 5.3 11.2L4.4 12.5L6.0 14.1L7.3 13.3C7.8 13.6 8.3 13.9 8.8 14.1L9.1 15.5H11.3L11.6 14.1C12.1 13.9 12.6 13.6 13.1 13.3L14.4 14.1L16.0 12.5L15.1 11.2C15.4 10.7 15.7 10.2 15.9 9.7L17.3 9.4V7.2L15.9 6.9C15.7 6.4 15.4 5.9 15.1 5.4L16.0 4.1L14.4 2.5L13.1 3.3C12.6 3.0 12.1 2.7 11.6 2.5L11.3 1.1H9.1zm1.1 4.5C11.9 5.6 13.0 6.7 13.0 8.0s-1.1 2.4-2.4 2.4S8.2 9.3 8.2 8.0s1.1-2.4 2.4-2.4z" transform="scale(0.85) translate(1, 1)" />
                    </svg>
                    <span>UI 设置</span>
                  </div>
                </div>
                <div className="right-content">


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

                  {/* 头像设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>全局头像设置</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => { setCropTarget('user'); fileInputRef.current.click(); }}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                      >
                        修改我的头像
                      </button>
                      <button
                        onClick={() => { setCropTarget('assistant'); fileInputRef.current.click(); }}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                      >
                        修改导师头像
                      </button>
                    </div>
                  </div>

                  {/* 全局背景设置 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: 'bold' }}>全局背景设置</label>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => bgFileInputRef.current.click()}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                      >
                        更换背景图片
                      </button>
                      <button
                        onClick={handleResetBg}
                        style={{ flex: 1, padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
                      >
                        恢复默认背景
                      </button>
                    </div>
                    <button
                      onClick={toggleBlur}
                      style={{
                        width: '100%', padding: '6px', fontSize: '11px', cursor: 'pointer', borderRadius: '4px', border: '1px solid var(--border-color)',
                        background: enableBlur ? 'var(--accent-pink)' : 'var(--bg-secondary)',
                        color: enableBlur ? 'white' : 'var(--text-primary)'
                      }}
                    >
                      毛玻璃背景特效：{enableBlur ? '已开启' : '已关闭'}
                    </button>
                  </div>
                </div>
              </section>
            )}

            {activeRightTab === 'api' && (
              <section className="ide-panel right-panel">
                <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                      <path d="M6 2v4M10 2v4M3 6h10M4 6a4 4 0 0 0 8 0M8 10v4" />
                    </svg>
                    <span>API 配置</span>
                  </div>
                </div>
                <div className="right-content">
                  {/* 模型选择配置 (原右侧面板) */}

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="1" y="1" width="14" height="14" rx="3" fill="none" />
                        <path d="M5 11V5M3 7l2-2 2 2M11 5v6M9 9l2 2 2-2" />
                      </svg>
                      切换大语言模型
                    </label>
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

                  <hr style={{ margin: '4px 0', border: 'none', borderTop: '1px solid var(--border-color)' }} />

                  {/* API 源 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>API 配置源</label>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button
                          onClick={() => setShowCreateModal(true)}
                          style={{
                            padding: '2px 6px',
                            fontSize: '11px',
                            background: 'var(--bg-tertiary)',
                            border: 'none',
                            borderRadius: '3px',
                            cursor: 'pointer',
                            color: 'var(--text-primary)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                          title="新增配置"
                        >
                          ➕
                        </button>
                        <button
                          onClick={() => {
                            if (selectedConfigIsActive) return;
                            setRenameConfigName(selectedConfig ? selectedConfig.name : '');
                            setShowRenameModal(true);
                          }}
                          style={{
                            padding: '2px 6px',
                            fontSize: '11px',
                            background: 'var(--bg-tertiary)',
                            border: 'none',
                            borderRadius: '3px',
                            cursor: selectedConfigIsActive ? 'not-allowed' : 'pointer',
                            color: 'var(--text-primary)',
                            opacity: selectedConfigIsActive ? 0.5 : 1,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                          title={selectedConfigIsActive ? "当前激活的配置不能重命名" : "重命名配置"}
                          disabled={selectedConfigIsActive}
                        >
                          ✏️
                        </button>
                        <button
                          onClick={handleDeleteModel}
                          style={{
                            padding: '2px 6px',
                            fontSize: '11px',
                            background: 'var(--bg-tertiary)',
                            border: 'none',
                            borderRadius: '3px',
                            cursor: (selectedConfigIsActive || models.length <= 1) ? 'not-allowed' : 'pointer',
                            color: 'var(--text-primary)',
                            opacity: (selectedConfigIsActive || models.length <= 1) ? 0.5 : 1,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '2px'
                          }}
                          title={
                            selectedConfigIsActive
                              ? "当前激活的配置不能删除"
                              : models.length <= 1
                                ? "不能删除最后一个配置"
                                : "删除配置"
                          }
                          disabled={selectedConfigIsActive || models.length <= 1}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                    <select
                      style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
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

                  {/* Max Context Tokens */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>最大上下文 Tokens (可选)</label>
                    <input
                      type="number"
                      placeholder="留空则自动试探。填入将永久锁定该限界 (如 131072)"
                      value={tempMaxContextTokens}
                      onChange={(e) => setTempMaxContextTokens(e.target.value)}
                      style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                    />
                  </div>

                  {/* Max Tokens (Output) */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>最大返回 Tokens (推荐8192, 0表示无限制)</label>
                    <input
                      type="number"
                      value={maxTokens}
                      onChange={handleMaxTokensChange}
                      style={{ padding: '6px', fontSize: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', outline: 'none' }}
                    />
                  </div>



                  {/* 子模型选择 */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>可用子模型</span>
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
                      padding: '8px 12px',
                      fontSize: '12px',
                      background: 'var(--accent-pink)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 'bold',
                      width: '100%',
                      marginTop: '8px'
                    }}
                  >
                    保存 API 地址并应用
                  </button>

                  {/* 知识库后端配置 */}
                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <h4 style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 'bold' }}>📚 知识库后端</h4>

                    {/* 三档单选 */}
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {[
                        { val: 'chromadb', label: '🚀 ChromaDB', tip: '本地向量库，轻量推荐' },
                        { val: 'ragflow', label: '☁️ RAGFlow', tip: '需要Docker运行' },
                        { val: 'external', label: '🔗 外部API', tip: 'Dify/FastGPT等' }
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
              </section>
            )}
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
        <input
          type="file"
          accept="image/*"
          ref={bgFileInputRef}
          style={{ display: 'none' }}
          onChange={handleBgUpload}
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

        {/* 新增 API 配置模态弹窗 */}
        {showCreateModal && (
          <div className="crop-modal-overlay" style={{ zIndex: 1010 }}>
            <div className="crop-modal-content" style={{ width: '450px', background: 'var(--bg-panel)', color: 'var(--text-primary)' }}>
              <h3 style={{ margin: 0, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>➕ 新增 API 配置源</h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>配置名称</label>
                  <input
                    type="text"
                    value={newConfigName}
                    onChange={(e) => setNewConfigName(e.target.value)}
                    placeholder="例如：My Custom API"
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>协议类型</label>
                  <select
                    value={newConfigProtocol}
                    onChange={(e) => setNewConfigProtocol(e.target.value)}
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  >
                    <option value="openai">OpenAI (推荐)</option>
                    <option value="gemini">Gemini</option>
                    <option value="claude">Claude</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>代理地址 (Base URL)</label>
                  <input
                    type="text"
                    value={newConfigBaseUrl}
                    onChange={(e) => setNewConfigBaseUrl(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>API 密钥 (API Key)</label>
                  <input
                    type="password"
                    value={newConfigApiKey}
                    onChange={(e) => setNewConfigApiKey(e.target.value)}
                    placeholder="sk-..."
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>最大上下文 Tokens (可选)</label>
                  <input
                    type="number"
                    value={newConfigMaxContextTokens}
                    onChange={(e) => setNewConfigMaxContextTokens(e.target.value)}
                    placeholder="留空自动探测。填入将永久锁定该限界 (如 131072)"
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewConfigName('');
                    setNewConfigBaseUrl('');
                    setNewConfigApiKey('');
                    setNewConfigProtocol('openai');
                    setNewConfigMaxContextTokens('');
                  }}
                  style={{ padding: '8px 16px', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  取消
                </button>
                <button
                  onClick={handleCreateModel}
                  style={{ padding: '8px 16px', background: 'var(--accent-pink)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                >
                  确认创建
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 重命名 API 配置模态弹窗 */}
        {showRenameModal && (
          <div className="crop-modal-overlay" style={{ zIndex: 1010 }}>
            <div className="crop-modal-content" style={{ width: '400px', background: 'var(--bg-panel)', color: 'var(--text-primary)' }}>
              <h3 style={{ margin: 0, fontSize: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>✏️ 重命名 API 配置源</h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>新名称</label>
                  <input
                    type="text"
                    value={renameConfigName}
                    onChange={(e) => setRenameConfigName(e.target.value)}
                    placeholder="输入新配置名称"
                    style={{ padding: '8px', fontSize: '13px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)', outline: 'none' }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '16px' }}>
                <button
                  onClick={() => {
                    setShowRenameModal(false);
                    setRenameConfigName('');
                  }}
                  style={{ padding: '8px 16px', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  取消
                </button>
                <button
                  onClick={handleRenameModel}
                  style={{ padding: '8px 16px', background: 'var(--accent-pink)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                >
                  保存修改
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
