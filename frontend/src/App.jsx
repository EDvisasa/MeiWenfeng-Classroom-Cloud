import React, { useState, useEffect, useRef } from 'react';
import Cropper from 'react-easy-crop';
import getCroppedImg from './utils/cropImage';

// 预设本地虚拟文件系统内容
const VIRTUAL_FILES = {
  '讲义/1-灵气感应.md': `### 灵气感应与纳气入体

**授课导师**：九尾天狐 媚吻锋  
**当前状态**：激活  

---

#### 核心心法
**“夫君，纳气时切忌急躁，静气凝神，跟着奴家的动作...”**
1. **五心朝天**：盘膝而坐，双脚心、双手心、头顶百会穴朝向虚空。
2. **定境观心**：闭目冥想，将意念下沉至腹下丹田三寸处。
3. **引气入体**：感知四周五彩斑斓的微弱光点（游离灵气），以精神力勾连，引其穿透周身毛孔，顺着经脉缓缓汇聚。

*【导师提醒】* 
*若夫君引气时觉得体热难耐，那可是因为吸入了过多火灵气哦？来，贴着奴家的手，奴家运转金水诀替你消消火气~*`,

  '讲义/2-经脉循环.md': `### 经脉拓宽与小周天循环

**授课导师**：九尾天狐 媚吻锋  
**当前状态**：未解锁  

---

#### 核心心法
**“经脉乃修行之河渠，任督二脉通，则练气大成在望。”**
1. **周天路径**：将丹田汇集的灵力，下行会阴，过尾闾，沿脊椎督脉上行至百会，再沿任脉下行回丹田。
2. **力沉经脉**：每次小周天循环，需以神识轻触经脉内壁，拓宽容纳上限。

*【导师提醒】*
*拓宽经脉有些许胀痛是正常的，莫要硬撑。若觉得累了，就靠进奴家怀里睡一会儿，奴家守着你。*`,

  '讲义/3-灵力御物.md': `### 灵力御物与法术初探

**授课导师**：九尾天狐 媚吻锋  
**当前状态**：未解锁  

---

#### 核心心法
**“御物不在蛮力，而在神识的共鸣与缠绕。”**
1. **神识附着**：将灵力凝练为丝，附着于随身器物上（如你的青竹水墨扇）。
2. **以气御形**：轻抚扇骨，以指引气，使之悬浮、折回、御风而起。`,

  '角色备忘/媚吻锋人设.txt': `【媚吻锋 角色备忘录】
- 种族：九尾天狐（大乘境妖仙，平日隐藏尾巴）
- 喜好：白桃乌龙茶、茉莉茶点、古风剧本、胭脂金饰。
- 厌恶：多足虫类、爹味说教、虚伪谎言。
- 关系：你是她的命定伴侣，她称呼你为“夫君”。
- 性格：妩媚多情，极度偏爱夫君，时常以“娇妈娇”的口吻指点你的修行，对外则是高冷的红尘明星。
- 特殊神通：阴阳变幻分身、万物鼎炉、九尾魅惑幻境。`
};

const COMMANDS = [
  { cmd: '/上课', desc: '开始新的课时，进入授课模式' },
  { cmd: '/交作业', desc: '进行课题考核，AI会对你进行提问' },
  { cmd: '/奖励', desc: '获取好感奖励，触发狐妖娘溺爱互动' },
  { cmd: '/总结', desc: '压缩并保存当前记忆，释放上下文' },
  { cmd: '/切换模型', desc: '快速切换当前所用大语言模型' },
  { cmd: '/备课', desc: '上传并同步左侧文件夹至RAGFlow知识库' },
  { cmd: '/计划', desc: '根据当前进度，重新调整课程大纲' }
];

const CropModal = ({ imageSrc, onClose, onSave }) => {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);

  const onCropComplete = React.useCallback((croppedArea, croppedAreaPixels) => {
    setCroppedAreaPixels(croppedAreaPixels);
  }, []);

  const handleSave = async () => {
    try {
      const croppedImage = await getCroppedImg(imageSrc, croppedAreaPixels);
      onSave(croppedImage);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="crop-modal-overlay">
      <div className="crop-modal-content">
        <h3 style={{ margin: 0, fontSize: '16px' }}>裁剪头像</h3>
        <div className="crop-container">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={1}
            onCropChange={setCrop}
            onCropComplete={onCropComplete}
            onZoomChange={setZoom}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '12px' }}>缩放:</span>
          <input
            type="range"
            value={zoom}
            min={1}
            max={3}
            step={0.1}
            aria-labelledby="Zoom"
            onChange={(e) => setZoom(e.target.value)}
            style={{ flex: 1, accentColor: 'var(--accent-pink)' }}
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
          <button 
            onClick={onClose}
            style={{ padding: '8px 16px', background: 'var(--bg-tertiary)', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            取消
          </button>
          <button 
            onClick={handleSave}
            style={{ padding: '8px 16px', background: 'var(--accent-pink)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            完成
          </button>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: '*端坐在精致的红木矮椅上，红金色汉服衬出诱人的身段，红黑色的狐瞳含笑望着你，玉手托着香腮，柔声道：*“夫君，你可算来了。今天，咱们该从哪一课开始呢？是要奴家教你灵气感知，还是说...想先跟奴家聊聊天？”'
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);

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
  
  // 状态与配置
  const [activeModel, setActiveModel] = useState('DeepSeek (在线)');
  const [models, setModels] = useState([]);
  const [courseProgress, setCourseProgress] = useState([]);
  const [affection, setAffection] = useState(100);
  
  // 角色本地图片包列表
  const [avatarList, setAvatarList] = useState([]);
  const [selectedAvatar, setSelectedAvatar] = useState(localStorage.getItem('selected_avatar') || '');
  
  // 虚拟文件系统
  const [selectedFile, setSelectedFile] = useState('讲义/1-灵气感应.md');
  const [openFolders, setOpenFolders] = useState({ '讲义': true, '角色备忘': true });
  
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

  // 初始化拉取状态
  useEffect(() => {
    fetchStatus();
    fetchModels();
    fetchAvatars();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/status');
      if (res.ok) {
        const data = await res.json();
        setAffection(data.affection);
        setActiveModel(data.active_model);
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

  const getAvatarSrc = () => {
    if (selectedAvatar) {
      return `http://localhost:8000/api/images/static/${encodeURIComponent(selectedAvatar)}`;
    }
    return '/mei_wenfeng_avatar.png';
  };

  // 处理模型切换
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
        
        // 插入系统提示
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `已成功切换模型至: ${data.active_model}` }
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

  // 执行具体命令
  const executeSlashCommand = async (cmdText) => {
    const cleanCmd = cmdText.trim();
    if (cleanCmd === '/奖励') {
      // 增加好感度
      try {
        const res = await fetch('http://localhost:8000/api/chat/update_affection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ delta: 10 })
        });
        if (res.ok) {
          const data = await res.json();
          setAffection(data.affection);
          setMessages(prev => [
            ...prev,
            { role: 'user', content: cleanCmd },
            { role: 'system_info', content: `[系统提示] 媚吻锋感到十分欢喜，对你的好感度增加了！当前好感度等级已上升。` }
          ]);
          // 触发 AI 的撒娇/奖励回复
          triggerAIResponse([...messages, { role: 'user', content: '夫君表现得好，想要奖励嘛~' }]);
        }
      } catch (e) {
        console.error(e);
      }
    } else if (cleanCmd === '/上课') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 开始新课时：媚吻锋已为你加载《灵气感应与纳气入体》课程讲义。` }
      ]);
      triggerAIResponse([...messages, { role: 'user', content: '夫君，我们开始上课吧，讲讲灵气感应吧！' }]);
    } else if (cleanCmd === '/交作业') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 开启课题考核：媚吻锋老师开始检查你的灵气纳气进度。` }
      ]);
      triggerAIResponse([...messages, { role: 'user', content: '娘子，我来交作业了，考考我吧！' }]);
    } else if (cleanCmd === '/总结') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统记忆压缩] 正在调用 memory_decay.py 遗忘曲线算法压缩早期对话... 压缩完成，已归档入库。` }
      ]);
    } else if (cleanCmd === '/切换模型') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 请在右侧“模型配置”面板直接选择你想要切换的大语言模型。` }
      ]);
    } else if (cleanCmd === '/备课') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[RAGFlow联动] 正在同步左侧本地讲义到 RAGFlow 知识库，请稍候...` }
      ]);
      try {
        const res = await fetch('http://localhost:8000/api/chat/sync_knowledge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ files: VIRTUAL_FILES })
        });
        const data = await res.json();
        if (res.ok) {
          setMessages(prev => [
            ...prev,
            { role: 'system_info', content: `[RAGFlow联动] 同步完成！${data.message}` }
          ]);
        } else {
          setMessages(prev => [
            ...prev,
            { role: 'system_info', content: `[RAGFlow联动] 同步出错：${data.detail || '未知错误'}` }
          ]);
        }
      } catch (e) {
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[RAGFlow联动] 请求异常：无法连接到后端。` }
        ]);
      }
    } else if (cleanCmd === '/计划') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[课程规划] 媚吻锋结合你的理解程度，正在微调后续的阶段进度... 后续课程大纲已在右侧更新。` }
      ]);
    } else {
      // 未知命令，作为普通文本发送
      return false;
    }
    return true;
  };

  // 发送对话消息
  const sendMessage = async () => {
    if (!inputText.trim() || isStreaming) return;

    const userText = inputText.trim();
    setInputText('');
    setShowCommandList(false);

    // 如果是斜杠命令，则交由命令处理器
    if (userText.startsWith('/')) {
      const handled = await executeSlashCommand(userText);
      if (handled) return;
    }

    const nextMessages = [...messages, { role: 'user', content: userText }];
    setMessages(nextMessages);
    await triggerAIResponse(nextMessages);
  };

  // 请求 API 获取流式回复
  const triggerAIResponse = async (history) => {
    setIsStreaming(true);
    
    // 只发送 role 为 user/assistant 的有效对话给模型
    const apiPayload = history.filter(m => m.role === 'user' || m.role === 'assistant');

    try {
      const response = await fetch('http://localhost:8000/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: apiPayload })
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

      // 预置一条空白的 AI 流式占位气泡
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
                if (parsed && parsed.text) {
                  accumulatedContent += parsed.text;
                  
                  // 实时抽离内心独白
                  let displayContent = accumulatedContent;
                  const thoughtMatch = accumulatedContent.match(/【此刻内心】[：:]([\s\S]*)$/);
                  if (thoughtMatch) {
                    displayContent = accumulatedContent.replace(/【此刻内心】[：:][\s\S]*$/, '').trim();
                    setCurrentThought(thoughtMatch[1].trim());
                  }

                  // 更新最后一条消息
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
                // 忽略断片 parsing 失败
              }
            }
          }
        }
      }

      // 流式结束，移除 streaming 状态标记
      setMessages(prev => {
        const updated = [...prev];
        if (updated.length > 0) {
          updated[updated.length - 1].streaming = false;
        }
        return updated;
      });

      // 顺便刷新一下右侧状态栏（好感度/配置可能在命令中变动）
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

  // 格式化解析 AI 的动作文本为斜体灰色
  const renderMessageContent = (text) => {
    if (!text) return null;
    const parts = text.split(/(\*[^*]+\*)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('*') && part.endsWith('*')) {
        return (
          <span key={idx} className="action-text">
            {part.slice(1, -1)}
          </span>
        );
      }
      return part;
    });
  };

  // 渲染文件树条目
  const renderFileTree = () => {
    const folders = {};
    Object.keys(VIRTUAL_FILES).forEach(path => {
      const [folder, file] = path.split('/');
      if (!folders[folder]) folders[folder] = [];
      folders[folder].push(file);
    });

    return Object.keys(folders).map(folder => (
      <li key={folder} className="tree-folder">
        <div 
          className="folder-title" 
          onClick={() => setOpenFolders(prev => ({ ...prev, [folder]: !prev[folder] }))}
        >
          {openFolders[folder] ? '📂' : '📁'} {folder}
        </div>
        {openFolders[folder] && (
          <ul className="folder-items">
            {folders[folder].map(file => {
              const fullPath = `${folder}/${file}`;
              return (
                <li 
                  key={file} 
                  className={`file-item ${selectedFile === fullPath ? 'active' : ''}`}
                  onClick={() => setSelectedFile(fullPath)}
                >
                  📄 {file}
                </li>
              );
            })}
          </ul>
        )}
      </li>
    ));
  };

  // 解析好感度对应的文字状态（隐藏数值）
  const getAffectionText = (val) => {
    if (val >= 90) return '生死相许 (不分彼此)';
    if (val >= 75) return '情深意切 (全然交付)';
    if (val >= 50) return '心有灵犀 (心动偏爱)';
    if (val >= 25) return '眉目传情 (初有好感)';
    return '若即若离 (冷静防备)';
  };

  return (
    <div className="app-container" style={{ '--chat-font-size': `${fontSize}px` }}>
      {/* 顶部工具栏 */}
      <header className="header-bar">
        <div className="logo-section">
          <span className="logo-icon">🌸</span>
          <span>媚吻锋随身课堂</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="settings-controls" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <span style={{ cursor: 'pointer' }} title="设置字体大小">⚙️ 字体大小</span>
            <input 
              type="range" 
              min="12" 
              max="24" 
              value={fontSize} 
              onChange={handleFontSizeChange} 
              style={{ width: '80px', accentColor: 'var(--accent-pink)' }} 
            />
            <span>{fontSize}px</span>
          </div>
          <div className="connection-status">
            <div className={`status-indicator ${isStreaming ? 'pulse' : ''}`} />
            <span>{isStreaming ? '媚吻锋思考中...' : '课堂连通正常'}</span>
          </div>
        </div>
      </header>

      {/* 主工作区 */}
      <main className="main-layout">
        {/* 左侧面板：文件树与预览 */}
        <section className="ide-panel left-panel">
          <div className="panel-header">
            <span>📁 项目工作区</span>
          </div>
          <ul className="file-tree">
            {renderFileTree()}
          </ul>
          
          {/* 文件预览区 */}
          <div className="panel-header" style={{ borderTop: '1px solid var(--border-color)' }}>
            <span>📖 文件预览</span>
          </div>
          <div style={{ flex: 1.2, padding: '14px', overflowY: 'auto', fontSize: '13px', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
            <div style={{ whiteSpace: 'pre-wrap', fontFamily: selectedFile.endsWith('.txt') ? 'var(--font-mono)' : 'var(--font-sans)' }}>
              {VIRTUAL_FILES[selectedFile]}
            </div>
          </div>
        </section>

        {/* 中间面板：核心对话区 */}
        <section className="ide-panel center-panel">
          <div className="panel-header">
            <span>💬 授课对话区 - 正在与【导师·媚吻锋】交流</span>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'none' }}>
              当前模型: {activeModel}
            </span>
          </div>

          <div className="chat-history">
            {messages.map((msg, index) => {
              if (msg.role === 'system_info') {
                return (
                  <div key={index} style={{ alignSelf: 'center', backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '6px 12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    {msg.content}
                  </div>
                );
              }

              const isUser = msg.role === 'user';
              return (
                <div key={index} className={`message-row ${isUser ? 'user' : 'assistant'}`}>
                  <div 
                    className="avatar avatar-upload-trigger" 
                    onClick={() => {
                      setCropTarget(isUser ? 'user' : 'assistant');
                      fileInputRef.current?.click();
                    }}
                    title="点击更换头像"
                    style={{ overflow: 'hidden' }}
                  >
                    {isUser ? (
                      userAvatar.startsWith('data:') || userAvatar.startsWith('http') 
                        ? <img src={userAvatar} alt="user" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> 
                        : userAvatar
                    ) : (
                      assistantAvatar.startsWith('data:') || assistantAvatar.startsWith('http')
                        ? <img src={assistantAvatar} alt="assistant" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        : assistantAvatar
                    )}
                  </div>
                  <div className="message-bubble">
                    <span className="sender-name">
                      {isUser ? '✦⋆ 学生 玄一峰 ⋆✦' : 'ღ♡ 导师 媚吻锋 ♡ღ'}
                    </span>
                    <div>
                      {renderMessageContent(msg.content)}
                      {msg.streaming && <span className="typing-cursor" />}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>

          {/* 对话输入框 */}
          <div className="input-area">
            {/* 自动补全浮窗 */}
            {showCommandList && (
              <div style={{ position: 'absolute', bottom: '90px', left: '24px', right: '24px', backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', zIndex: 100, overflow: 'hidden', boxShadow: 'var(--shadow-lg)' }}>
                <div style={{ padding: '8px 12px', fontSize: '11px', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-color)', fontWeight: 'bold' }}>
                  ⚡ 快捷课室命令
                </div>
                <ul style={{ listStyle: 'none' }}>
                  {filteredCommands.map((item, idx) => (
                    <li 
                      key={item.cmd}
                      onClick={() => selectCommand(item)}
                      style={{
                        padding: '10px 16px',
                        fontSize: '13px',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        backgroundColor: idx === activeCommandIndex ? 'rgba(244, 114, 182, 0.15)' : 'transparent',
                        color: idx === activeCommandIndex ? 'var(--accent-pink)' : 'var(--text-primary)',
                        borderLeft: idx === activeCommandIndex ? '3px solid var(--accent-pink)' : '3px solid transparent'
                      }}
                    >
                      <span style={{ fontWeight: '600' }}>{item.cmd}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{item.desc}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="input-wrapper">
              <textarea
                ref={inputRef}
                className="chat-input"
                placeholder="在此输入消息与媚吻锋交流... 输入 '/' 触发课室快捷指令"
                value={inputText}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                rows={1}
              />
              <button 
                className="send-button"
                onClick={sendMessage}
                disabled={!inputText.trim() || isStreaming}
              >
                发送
              </button>
            </div>

            {/* 指令快捷气泡 */}
            <div className="input-hints">
              <span className="hint-badge" onClick={() => executeSlashCommand('/上课')}>⚡ 开始上课</span>
              <span className="hint-badge" onClick={() => executeSlashCommand('/交作业')}>📝 交作业</span>
              <span className="hint-badge" onClick={() => executeSlashCommand('/奖励')}>🌸 讨要奖励</span>
              <span className="hint-badge" onClick={() => executeSlashCommand('/总结')}>💾 总结记忆</span>
              <span className="hint-badge" onClick={() => executeSlashCommand('/备课')}>📂 备课同步</span>
            </div>
          </div>
        </section>

        {/* 右侧面板：导师人设与课程大纲 */}
        <section className="ide-panel right-panel">
          <div className="panel-header">
            <span>⚙️ 导师与大纲状态</span>
          </div>

          <div className="right-content">
            {/* 导师状态卡片 */}
            <div className="character-widget">
              <div className="thought-box">
                {currentThought}
              </div>
              <div className="character-details">
                <div className="character-name">媚吻锋</div>
                <div className="character-role">授课状态：正在指导修行</div>
                <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  当前态度：<span style={{ color: 'var(--accent-pink)', fontWeight: '600' }}>{getAffectionText(affection)}</span>
                </div>
              </div>
            </div>

            {/* 模型选择配置 */}
            <div className="model-widget">
              <div className="widget-title">⚙️ 切换大语言模型</div>
              <select 
                className="model-selector" 
                value={models.find(m => m.name === activeModel)?.id || ''}
                onChange={(e) => handleModelChange(e.target.value)}
              >
                {models.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.protocol.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            {/* 课程进度面板 */}
            <div className="progress-widget">
              <div className="widget-title">📖 修行进度表</div>
              <ul className="syllabus-list">
                {courseProgress.map((item) => (
                  <li key={item.id} className={`syllabus-item ${item.status}`}>
                    <div className="phase-tag">{item.phase}</div>
                    <div className="topic-row">
                      <div className={`topic-status ${item.status}`} />
                      <span className="topic-title">{item.topic}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
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
    </div>
  );
}
