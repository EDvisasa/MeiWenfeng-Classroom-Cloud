import React, { useState, useEffect, useRef } from 'react';
import FileTree from './components/FileTree';
import ChatPanel from './components/ChatPanel';
import StatusPanel from './components/StatusPanel';
import CropModal from './components/CropModal';

const COMMANDS = [
  { cmd: '/上课', desc: '开始新的课时，进入授课模式' },
  { cmd: '/交作业', desc: '进行课题考核，AI会对你进行提问' },
  { cmd: '/奖励', desc: '获取好感奖励，触发狐妖娘溺爱互动' },
  { cmd: '/总结', desc: '压缩并保存当前记忆，释放上下文' },
  { cmd: '/切换模型', desc: '快速切换当前所用大语言模型' },
  { cmd: '/备课', desc: '将当前选定的讲义文件上传同步至RAGFlow知识库' },
  { cmd: '/计划', desc: '根据当前进度，重新调整课程大纲' }
];

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
  const [personaType, setPersonaType] = useState(localStorage.getItem('persona_type') || 'simplified');

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
          triggerAIResponse([...messages, { role: 'user', content: '夫君表现得好，想要奖励嘛~' }]);
        }
      } catch (e) {
        console.error(e);
      }
    } else if (cleanCmd === '/上课') {
      const fileName = selectedFilePath ? selectedFilePath.split('/').pop() : '默认修仙';
      const topicName = fileName.replace('.md', '');
      
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 开始新课时：媚吻锋已为你加载《${topicName}》讲义内容。` }
      ]);
      triggerAIResponse([...messages, { role: 'user', content: `娘子，我们开始上课吧，给我讲讲关于《${topicName}》的修行要点吧！` }]);
    } else if (cleanCmd === '/交作业') {
      const fileName = selectedFilePath ? selectedFilePath.split('/').pop() : '当前课题';
      const topicName = fileName.replace('.md', '');
      
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 开启课题考核：媚吻锋老师开始检查你对《${topicName}》的掌握进度。` }
      ]);
      triggerAIResponse([...messages, { role: 'user', content: `娘子，我来交《${topicName}》的作业了，快来考考我吧！` }]);
    } else if (cleanCmd === '/总结') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统记忆压缩] 正在调用艾宾浩斯遗忘曲线算法进行后台压缩，请稍候...` }
      ]);
      try {
        const res = await fetch('http://localhost:8000/api/chat/summarize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (res.ok) {
          setMessages(prev => [
            ...prev,
            { role: 'system_info', content: `[系统记忆压缩] 压缩完成！新记忆已归档入库。处理统计: ${JSON.stringify(data.stats)}` }
          ]);
        } else {
          setMessages(prev => [
            ...prev,
            { role: 'system_info', content: `[系统记忆压缩] 压缩失败: ${data.detail || '未知错误'}` }
          ]);
        }
      } catch (e) {
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[系统记忆压缩] 请求异常：无法连接到后端。` }
        ]);
      }
    } else if (cleanCmd === '/切换模型') {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[系统提示] 请在右侧“模型配置”面板直接选择你想要切换的大语言模型。` }
      ]);
    } else if (cleanCmd === '/备课') {
      if (!selectedFilePath) {
        setMessages(prev => [
          ...prev,
          { role: 'system_info', content: `[RAGFlow联动] 提示：请先在左侧选择要上传的 Markdown 讲义文件。` }
        ]);
        return true;
      }
      
      const fileName = selectedFilePath.split('/').pop();
      setMessages(prev => [
        ...prev,
        { role: 'user', content: cleanCmd },
        { role: 'system_info', content: `[RAGFlow联动] 正在同步本地文件《${fileName}》到 RAGFlow 知识库，请稍候...` }
      ]);
      try {
        const res = await fetch('http://localhost:8000/api/chat/files/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: selectedFilePath })
        });
        const data = await res.json();
        if (res.ok) {
          setMessages(prev => [
            ...prev,
            { role: 'system_info', content: `[RAGFlow联动] 上传成功！已开始触发解析进程。` }
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
    } else if (cleanCmd === '更新人设' || cleanCmd === '/更新人设') {
      const nextMessages = [
        ...messages,
        { role: 'user', content: '更新人设' }
      ];
      setMessages(nextMessages);
      triggerAIResponse(nextMessages);
    } else {
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
    const apiPayload = history.filter(m => m.role === 'user' || m.role === 'assistant');

    try {
      const response = await fetch('http://localhost:8000/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          messages: apiPayload,
          persona_type: personaType
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
        <FileTree
          selectedFilePath={selectedFilePath}
          selectedFileContent={selectedFileContent}
          onFileSelect={(path, content) => {
            setSelectedFilePath(path);
            setSelectedFileContent(content);
          }}
          rootPath={rootPath}
          setRootPath={setRootPath}
        />

        {/* 中间面板：核心对话区 */}
        <ChatPanel
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
        />

        {/* 右侧面板：导师人设与课程大纲 */}
        <StatusPanel
          currentThought={currentThought}
          affection={affection}
          personaType={personaType}
          handlePersonaTypeChange={handlePersonaTypeChange}
          models={models}
          activeModel={activeModel}
          handleModelChange={handleModelChange}
          courseProgress={courseProgress}
        />
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
