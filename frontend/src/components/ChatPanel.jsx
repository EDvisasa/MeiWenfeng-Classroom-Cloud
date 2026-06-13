import React from 'react';

export default function ChatPanel({
  messages,
  activeModel,
  userAvatar,
  assistantAvatar,
  setCropTarget,
  fileInputRef,
  showCommandList,
  filteredCommands,
  activeCommandIndex,
  selectCommand,
  inputRef,
  inputText,
  handleInputChange,
  handleKeyDown,
  sendMessage,
  isStreaming,
  executeSlashCommand,
  chatEndRef,
  onEditAndResend
}) {
  const [editingIndex, setEditingIndex] = React.useState(null);
  const [editContent, setEditContent] = React.useState('');
  
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

  return (
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
              <div 
                key={index} 
                style={{ 
                  alignSelf: 'center', 
                  backgroundColor: 'var(--bg-tertiary)', 
                  border: '1px solid var(--border-color)', 
                  borderRadius: '6px', 
                  padding: '6px 12px', 
                  fontSize: '12px', 
                  color: 'var(--text-secondary)' 
                }}
              >
                {msg.content}
              </div>
            );
          }

          const isUser = msg.role === 'user';
          const isEditing = editingIndex === index;

          return (
            <div key={index} className={`message-row ${isUser ? 'user' : 'assistant'}`} style={{ position: 'relative' }}>
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
              <div className="message-bubble" style={{ position: 'relative' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <span className="sender-name">
                    {isUser ? '✦⋆ 学生 玄一峰 ⋆✦' : 'ღ♡ 导师 媚吻锋 ♡ღ'}
                  </span>
                  
                  {isUser && !isEditing && !isStreaming && (
                    <button 
                      onClick={() => {
                        setEditingIndex(index);
                        setEditContent(msg.content);
                      }}
                      title="编辑并重新发送"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                        marginLeft: '8px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        transition: 'all 0.2s',
                        opacity: 0.6
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.opacity = 1;
                        e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)';
                        e.currentTarget.style.color = 'var(--accent-pink)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.opacity = 0.6;
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = 'var(--text-secondary)';
                      }}
                    >
                      ✏️ 编辑
                    </button>
                  )}
                </div>
                
                {isEditing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px', minWidth: '220px' }}>
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      style={{
                        width: '100%',
                        minHeight: '60px',
                        padding: '8px',
                        borderRadius: '6px',
                        border: '1px solid var(--accent-pink)',
                        fontSize: '14px',
                        background: 'var(--bg-primary)',
                        color: 'var(--text-primary)',
                        resize: 'vertical',
                        outline: 'none',
                        lineHeight: '1.5'
                      }}
                    />
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => {
                          setEditingIndex(null);
                          setEditContent('');
                        }}
                        style={{
                          padding: '4px 10px',
                          fontSize: '12px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-color)',
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          cursor: 'pointer'
                        }}
                      >
                        取消
                      </button>
                      <button
                        onClick={() => {
                          if (editContent.trim()) {
                            onEditAndResend(index, editContent.trim());
                            setEditingIndex(null);
                            setEditContent('');
                          }
                        }}
                        disabled={!editContent.trim()}
                        style={{
                          padding: '4px 10px',
                          fontSize: '12px',
                          borderRadius: '4px',
                          border: 'none',
                          background: 'var(--accent-pink)',
                          color: 'white',
                          cursor: 'pointer',
                          fontWeight: 'bold'
                        }}
                      >
                        保存并发送
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    {renderMessageContent(msg.content)}
                    {msg.streaming && <span className="typing-cursor" />}
                  </div>
                )}
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
          <div 
            style={{ 
              position: 'absolute', 
              bottom: '90px', 
              left: '24px', 
              right: '24px', 
              backgroundColor: 'var(--bg-secondary)', 
              border: '1px solid var(--border-color)', 
              borderRadius: '8px', 
              zIndex: 100, 
              overflow: 'hidden', 
              boxShadow: 'var(--shadow-lg)' 
            }}
          >
            <div 
              style={{ 
                padding: '8px 12px', 
                fontSize: '11px', 
                color: 'var(--text-secondary)', 
                borderBottom: '1px solid var(--border-color)', 
                fontWeight: 'bold' 
              }}
            >
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
          <span className="hint-badge" onClick={() => executeSlashCommand('更新人设')}>🔄 更新人设</span>
        </div>
      </div>
    </section>
  );
}
