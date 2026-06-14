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
  onEditAndResend,
  isVsCode,
  sessions,
  activeSessionId,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
  showSessionList,
  setShowSessionList,
  selectedFilePath
}) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [showShortcuts, setShowShortcuts] = React.useState(false);
  const [editingIndex, setEditingIndex] = React.useState(null);
  const [editContent, setEditContent] = React.useState('');

  // 监听输入文本内容，根据行数自适应高度，未满高度时不显示滚动条
  React.useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      const scrollHeight = inputRef.current.scrollHeight;
      inputRef.current.style.height = `${Math.min(150, scrollHeight)}px`;
      if (scrollHeight > 150) {
        inputRef.current.style.overflowY = 'auto';
      } else {
        inputRef.current.style.overflowY = 'hidden';
      }
    }
  }, [inputText, inputRef]);

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
        {/* 当前会话标题 */}
        <span style={{ fontWeight: 600, fontSize: '13px', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {(sessions?.find(s => s.id === activeSessionId)?.title || 'Mei Wenfeng').slice(0, 20)}
        </span>

        {/* 历史对话(时钟) + 新建对话(圆圈加号) 图标按钮 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px', marginLeft: '6px' }}>

          {/* 历史对话 - 时钟图标 */}
          <div style={{ position: 'relative' }}>
            <button
              className={`cc-icon-btn ${showSessionList ? 'active' : ''}`}
              onClick={() => setShowSessionList(v => !v)}
              title="历史对话"
              style={{ width: '24px', height: '24px' }}
            >
              <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM0 8a8 8 0 1 1 16 0A8 8 0 0 1 0 8zm8-3.5a.75.75 0 0 1 .75.75v3h1.5a.75.75 0 0 1 0 1.5H8a.75.75 0 0 1-.75-.75v-3.75A.75.75 0 0 1 8 4.5z" />
              </svg>
            </button>
            {showSessionList && (
              <div className="session-list-popover">
                <div className="session-list-header">历史对话</div>
                {sessions && sessions.map(s => (
                  <div
                    key={s.id}
                    className={`session-item ${s.id === activeSessionId ? 'active' : ''}`}
                    onClick={() => { onSwitchSession(s.id); setShowSessionList(false); }}
                  >
                    <span className="session-title">{s.title}</span>
                    <button
                      className="session-delete-btn"
                      onClick={(e) => onDeleteSession(s.id, e)}
                      title="删除"
                    >
                      <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M2 4h12v1H2V4zm2-2h8v1H4V2zm1 4h1v7H5V6zm4 0h1v7H9V6zM3 5h10l-1 10H4L3 5z" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 新建对话 - 圆圈加号图标 */}
          <button
            className="cc-icon-btn"
            onClick={onNewSession}
            title="新建对话"
            style={{ width: '24px', height: '24px' }}
          >
            <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 1.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm.75 2.25h-1.5v2.5h-2.5v1.5h2.5v2.5h1.5v-2.5h2.5v-1.5h-2.5v-2.5z" />
            </svg>
          </button>

        </div>

        <span style={{ flex: 1 }} />
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'none', letterSpacing: 'normal' }}>
          {activeModel}
        </span>
      </div>

      <div className="chat-history">
        {messages.map((msg, index) => {
          if (msg.role === 'system_info') {
            return (
              <div
                key={index}
                className="system-info-msg"
                style={{
                  alignSelf: 'center',
                  backgroundColor: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '6px',
                  padding: '6px 14px',
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  margin: '8px 0',
                  maxWidth: '90%',
                  textAlign: 'center',
                }}
              >
                {msg.content}
              </div>
            );
          }

          const isUser = msg.role === 'user';

          const handleStartEdit = () => {
            setEditingIndex(index);
            setEditContent(msg.content);
            setIsEditing(true);
          };

          const handleCancelEdit = () => {
            setIsEditing(false);
            setEditingIndex(null);
            setEditContent('');
          };

          const handleConfirmEdit = () => {
            if (onEditAndResend && editContent.trim()) {
              onEditAndResend(index, editContent.trim());
            }
            handleCancelEdit();
          };

          return (
            <div key={index} className={`message-item ${isUser ? 'user-msg' : 'assistant-msg'}`}>

              {/* Header Row: Avatar + Name + Edit Button */}
              <div className="message-header">
                {isUser ? (
                  <>
                    <div className="sender-group">
                      <span className="sender-name">你</span>
                    </div>
                    <div
                      className="avatar"
                      onClick={() => fileInputRef.current?.click()}
                      title="点击更换头像"
                      style={{ cursor: 'pointer' }}
                    >
                      {userAvatar ? (
                        <img src={userAvatar} alt="用户头像" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                      ) : (
                        <span>你</span>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div
                      className="avatar"
                      onClick={() => setCropTarget('assistant')}
                      title="点击更换导师头像"
                      style={{ cursor: 'pointer' }}
                    >
                      {assistantAvatar ? (
                        <img src={assistantAvatar} alt="导师头像" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                      ) : (
                        <span>师</span>
                      )}
                    </div>
                    <span className="sender-name">媚吻锋</span>
                  </>
                )}
              </div>

              {/* Message Bubble */}
              {isUser && isEditing && editingIndex === index ? (
                <div className="message-bubble editing">
                  <textarea
                    className="edit-textarea"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    rows={3}
                    autoFocus
                  />
                  <div className="edit-actions">
                    <button className="edit-confirm-btn" onClick={handleConfirmEdit}>重新发送</button>
                    <button className="edit-cancel-btn" onClick={handleCancelEdit}>取消</button>
                  </div>
                </div>
              ) : (
                <div className="message-bubble">
                  {renderMessageContent(msg.content)}
                  {msg.streaming && <span className="typing-cursor" />}
                  {isUser && (
                    <button className="edit-msg-btn" onClick={handleStartEdit} title="编辑并重发">
                      <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M11.5 1a.5.5 0 0 1 .354.146l2 2A.5.5 0 0 1 14 3.5v.793L4.5 13.793 1 15l1.207-3.5L11.5 1zm-1.207 2.5L8.5 1.707 2 8.207V9.5h1.293L11.5 1.5zm1.914 0l.793-.793-1.207-1.207-.793.793 1.207 1.207z" />
                      </svg>
                    </button>
                  )}
                </div>
              )}

            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      {/* 对话输入框 - Claude Code 风格双行卡片 */}
      <div className="input-area" style={{ position: 'relative' }}>
        {/* 自动补全浮窗 */}
        {showCommandList && (
          <div
            className="command-list-popover"
            style={{
              position: 'absolute',
              bottom: '100%',
              marginBottom: '8px',
              left: '24px',
              right: '24px',
              backgroundColor: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              zIndex: 9999,
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
                  className={`command-item ${idx === activeCommandIndex ? 'active' : ''}`}
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

        {/* 显示当前跟踪的激活文件 (给用户的视觉反馈) */}
        {isVsCode && selectedFilePath && (
          <div style={{
            padding: '4px 10px',
            fontSize: '10px',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-secondary)',
            borderTopLeftRadius: '8px',
            borderTopRightRadius: '8px',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}>
            <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M13.85 4.44l-3.28-3.3a.5.5 0 0 0-.35-.14H2.5a.5.5 0 0 0-.5.5v13a.5.5 0 0 0 .5.5h11a.5.5 0 0 0 .5-.5V4.8a.5.5 0 0 0-.15-.36zM10.5 2.21L12.79 4.5H10.5V2.21zM13 14H3V2h6.5v3a.5.5 0 0 0 .5.5h3v8.5z"/></svg>
            当前追踪 (@current_file): {selectedFilePath.split('\\').pop().split('/').pop()}
          </div>
        )}

        {/* 卡片式输入框 */}
        <div className="input-wrapper" style={{ borderTopLeftRadius: isVsCode && selectedFilePath ? '0' : '8px', borderTopRightRadius: isVsCode && selectedFilePath ? '0' : '8px' }}>
          {/* 行1：文字输入区 */}
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="与媚吻锋交流…"
            value={inputText}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
          />

          {/* 行2：工具栏 */}
          <div className="input-toolbar">
            {/* 左侧：快捷指令按钮 */}
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <button
                className="shortcuts-trigger-btn"
                onClick={() => setShowShortcuts(!showShortcuts)}
                title="快捷工具"
              >
                <svg width="20" height="20" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M2.5 1A1.5 1.5 0 0 0 1 2.5v11A1.5 1.5 0 0 0 2.5 15h11A1.5 1.5 0 0 0 15 13.5v-11A1.5 1.5 0 0 0 13.5 1h-11zm-.5 1.5a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 .5.5v11a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11zM10 4.5L6 11.5h1L11 4.5h-1z" />
                </svg>
              </button>
              {showShortcuts && (
                <div
                  className="shortcuts-popover"
                  style={{
                    position: 'absolute',
                    bottom: '100%',
                    marginBottom: '8px',
                    left: 0,
                    background: 'var(--bg-panel)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '8px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    boxShadow: 'var(--shadow-lg)',
                    zIndex: 9999,
                    width: '140px'
                  }}
                >
                  {[
                    { cmd: '/lesson', label: '⚡ 开始上课' },
                    { cmd: '/submit', label: '📝 交作业' },
                    { cmd: '/reward', label: '🌸 讨要奖励' },
                    { cmd: '/summarize', label: '💾 总结记忆' },
                    { cmd: '/prepare', label: '📂 备课同步' },
                    { cmd: '/update_persona', label: '🔄 更新人设' },
                  ].map(item => (
                    <div
                      key={item.cmd}
                      onClick={() => {
                        executeSlashCommand(item.cmd);
                        setShowShortcuts(false);
                      }}
                      style={{
                        padding: '6px 12px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        borderRadius: '4px',
                        transition: 'background 0.2s',
                        color: 'var(--text-primary)'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-tertiary)'}
                      onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      {item.label}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 右侧：发送按钮 */}
            <button
              className="send-button"
              onClick={sendMessage}
              disabled={!inputText.trim() || isStreaming}
              title="发送消息"
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 1l6 6h-5v8H7V7H2l6-6z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
