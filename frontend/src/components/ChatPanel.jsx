import React from 'react';
import { encode } from 'gpt-tokenizer';
import { API_BASE } from '../config';
import { parseAndMergeBlocks } from '../utils/blockParser';
import { AlertTriangle, Check, X } from 'lucide-react';
import MissionProposalCard from './MissionProposalCard';
import QuizBlock from './QuizBlock';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, prism } from 'react-syntax-highlighter/dist/esm/styles/prism';

const BashApprovalCard = ({ pendingApproval, onApprove, onReject }) => {
  const [timeLeft, setTimeLeft] = React.useState(60);

  React.useEffect(() => {
    if (!pendingApproval) return;
    
    setTimeLeft(60);
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [pendingApproval]);

  if (!pendingApproval) return null;

  return (
    <div style={{
      position: 'absolute',
      bottom: '100%',
      marginBottom: '12px',
      left: 0,
      width: '100%',
      boxSizing: 'border-box',
      background: 'var(--bg-panel, #ffffff)',
      border: '1px solid var(--border-color, #e2e8f0)',
      borderRadius: '12px',
      padding: '16px',
      boxShadow: 'var(--shadow-lg, 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1))',
      zIndex: 10000,
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      color: 'var(--text-primary, #1e293b)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#ef4444' }}>
          <AlertTriangle size={18} />
          <span style={{ fontSize: '13px', fontWeight: '600', letterSpacing: '0.2px' }}>需要授权执行 Bash 命令</span>
        </div>
        <div style={{ fontSize: '12px', color: timeLeft <= 10 ? '#ef4444' : 'var(--text-secondary, #64748b)', fontFamily: 'monospace' }}>
          {timeLeft}s
        </div>
      </div>
      
      <div style={{
        background: 'var(--bg-secondary, #f8fafc)',
        padding: '10px 12px',
        borderRadius: '6px',
        border: '1px solid var(--border-color, #e2e8f0)',
        overflowX: 'auto',
      }}>
        <pre style={{ margin: 0, fontSize: '12px', fontFamily: 'monospace', color: 'var(--text-primary, #334155)' }}>
          {pendingApproval.command}
        </pre>
      </div>

      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '4px' }}>
        <button
          onClick={onReject}
          disabled={timeLeft === 0}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 16px',
            borderRadius: '6px',
            border: '1px solid var(--border-color, #e2e8f0)',
            background: 'transparent',
            color: 'var(--text-primary, #334155)',
            fontSize: '13px',
            fontWeight: '500',
            cursor: timeLeft === 0 ? 'not-allowed' : 'pointer',
            opacity: timeLeft === 0 ? 0.5 : 1,
            transition: 'background 0.2s'
          }}
          onMouseOver={(e) => !timeLeft === 0 && (e.currentTarget.style.background = 'var(--bg-secondary, #f1f5f9)')}
          onMouseOut={(e) => !timeLeft === 0 && (e.currentTarget.style.background = 'transparent')}
        >
          <X size={14} /> 拒绝
        </button>
        <button
          onClick={onApprove}
          disabled={timeLeft === 0}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 16px',
            borderRadius: '6px',
            border: 'none',
            background: '#0066ff',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: '600',
            cursor: timeLeft === 0 ? 'not-allowed' : 'pointer',
            opacity: timeLeft === 0 ? 0.5 : 1,
            boxShadow: '0 2px 4px rgba(0, 102, 255, 0.2)',
            transition: 'background 0.2s, opacity 0.2s'
          }}
          onMouseOver={(e) => !timeLeft === 0 && (e.currentTarget.style.background = '#0052cc')}
          onMouseOut={(e) => !timeLeft === 0 && (e.currentTarget.style.background = '#0066ff')}
        >
          <Check size={14} /> 允许执行
        </button>
      </div>
    </div>
  );
};

const ToolBlock = ({ block, idx }) => {
  const isRunning = block.status === 'running';
  const friendlyName = block.tool_name === 'execute_bash' ? 'Bash'
    : block.tool_name === 'read_file' ? 'Read'
    : block.tool_name === 'grep_search' ? 'Grep'
    : block.tool_name === 'default_api:run_command' ? 'Bash'
      : block.tool_name;

  const [isExpanded, setIsExpanded] = React.useState(false);
  const THRESHOLD = 30;
  const hasLongOutput = block.output && block.output.length > THRESHOLD;

  return (
    <div key={idx} className="claude-tool-block">
      <div className="claude-tool-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: hasLongOutput ? 'pointer' : 'default' }} onClick={() => hasLongOutput && setIsExpanded(!isExpanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className={`claude-tool-status-dot ${isRunning ? 'running' : 'done'}`}></div>
          <span className="claude-tool-name">{friendlyName}</span>
        </div>
        {hasLongOutput && (
          <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
            {isExpanded ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M14.7 10.3a1 1 0 01-1.4 1.4L8 6.42 2.7 11.7a1 1 0 01-1.4-1.4l6-6a1 1 0 011.4 0l6 6z" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1.3 5.7a1 1 0 011.4-1.4L8 9.58l5.3-5.3a1 1 0 011.4 1.4l-6 6a1 1 0 01-1.4 0l-6-6z" /></svg>
            )}
          </div>
        )}
      </div>
      <div
        className={`claude-tool-io ${hasLongOutput && !isExpanded ? 'collapsed' : ''} ${hasLongOutput ? 'clickable' : ''}`}
        onClick={() => hasLongOutput && setIsExpanded(!isExpanded)}
      >
        <div className="claude-tool-io-row">
          <span className="claude-tool-io-label">IN</span>
          <span className="claude-tool-io-content">{block.command}</span>
        </div>
        {block.output && (
          <div className="claude-tool-io-row">
            <span className="claude-tool-io-label">OUT</span>
            <span className="claude-tool-io-content" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {block.output}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

const ThinkingBlock = ({ block, idx }) => {
  const isRunning = block.status === 'running';
  const [isExpanded, setIsExpanded] = React.useState(isRunning);

  React.useEffect(() => {
    setIsExpanded(isRunning);
  }, [isRunning]);

  const hasLongOutput = block.text && (block.text.length > 50 || block.text.includes('\n'));

  return (
    <div key={`thought_${idx}`} className="claude-tool-block">
      <div className="claude-tool-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: hasLongOutput ? 'pointer' : 'default' }} onClick={() => hasLongOutput && setIsExpanded(!isExpanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className={`claude-tool-status-dot ${isRunning ? 'running' : 'done'}`}></div>
          <span className="claude-tool-name">Thinking</span>
        </div>
        {hasLongOutput && (
          <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
            {isExpanded ? (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M14.7 10.3a1 1 0 01-1.4 1.4L8 6.42 2.7 11.7a1 1 0 01-1.4-1.4l6-6a1 1 0 011.4 0l6 6z" /></svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1.3 5.7a1 1 0 011.4-1.4L8 9.58l5.3-5.3a1 1 0 011.4 1.4l-6 6a1 1 0 01-1.4 0l-6-6z" /></svg>
            )}
          </div>
        )}
      </div>
      <div
        className={`thinking-content ${hasLongOutput && !isExpanded ? 'collapsed' : ''} ${hasLongOutput ? 'clickable' : ''}`}
        onClick={() => hasLongOutput && setIsExpanded(!isExpanded)}
      >
        {block.text}
      </div>
    </div>
  );
};

const RetryBlock = ({ block, idx }) => {
  const isRunning = block.status === 'running';
  const [isExpanded, setIsExpanded] = React.useState(isRunning);

  React.useEffect(() => {
    setIsExpanded(isRunning);
  }, [isRunning]);

  return (
    <div key={`retry_${idx}`} className="claude-tool-block" style={{ border: '1px solid var(--border-color)', borderRadius: '8px', padding: '8px 12px', backgroundColor: 'var(--bg-panel)' }}>
      <div className="claude-tool-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }} onClick={() => setIsExpanded(!isExpanded)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <div className={`claude-tool-status-dot ${isRunning ? 'running' : block.status}`} style={{ backgroundColor: block.status === 'failed' ? 'var(--text-error, #f87171)' : undefined }}></div>
          <span className="claude-tool-name">
             {isRunning ? 'Reconnecting...' : (block.status === 'failed' ? 'Connection failed' : 'Connected')}
          </span>
        </div>
        <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
          {isExpanded ? (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M14.7 10.3a1 1 0 01-1.4 1.4L8 6.42 2.7 11.7a1 1 0 01-1.4-1.4l6-6a1 1 0 011.4 0l6 6z" /></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M1.3 5.7a1 1 0 011.4-1.4L8 9.58l5.3-5.3a1 1 0 011.4 1.4l-6 6a1 1 0 01-1.4 0l-6-6z" /></svg>
          )}
        </div>
      </div>
      {isExpanded && block.error_msg && (
        <div className="claude-tool-io">
           <div className="claude-tool-io-row" style={{ borderBottom: 'none', flexDirection: 'row', alignItems: 'flex-start' }}>
             <span className="claude-tool-io-label" style={{ color: 'var(--text-secondary)', borderColor: 'var(--border-color)' }}>LOG</span>
             <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, wordBreak: 'break-word' }}>
               <span className="claude-tool-io-content" style={{ fontWeight: '500', color: 'var(--text-primary)' }}>{block.error_msg}</span>
               {isRunning && block.retry_info && (
                 <span className="claude-tool-io-content" style={{ color: 'var(--text-secondary)' }}>{block.retry_info}</span>
               )}
             </div>
           </div>
        </div>
      )}
    </div>
  );
};

export default function ChatPanel({
  theme,
  messages,
  models,
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
  selectedFilePath,
  stopGeneration,
  pendingApproval,
  setPendingApproval
}) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [showShortcuts, setShowShortcuts] = React.useState(false);
  const [editingIndex, setEditingIndex] = React.useState(null);
  const [editContent, setEditContent] = React.useState('');

  const pendingMission = React.useMemo(() => {
    if (!messages || messages.length === 0) return null;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role !== 'assistant') return null;
    
    let blocks = [];
    if (Array.isArray(lastMsg.blocks)) {
        blocks = parseAndMergeBlocks(lastMsg.blocks);
    } else if (lastMsg.content) {
        blocks = parseAndMergeBlocks(lastMsg.content);
    }
    
    const missionBlock = blocks.find(b => b.type === 'mission_proposal');
    return missionBlock ? missionBlock.data : null;
  }, [messages]);

  const handleApprovalSubmit = async (action) => {
    if (!pendingApproval) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/chat/approve_tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approval_id: pendingApproval.approval_id,
          action: action
        })
      });
      if (!res.ok) console.error("Failed to submit approval");
    } catch (e) {
      console.error(e);
    }
    setPendingApproval(null);
  };

  const [baseSystemTokens, setBaseSystemTokens] = React.useState(0);
  const [dynamicTokens, setDynamicTokens] = React.useState(0);
  const [decayStates, setDecayStates] = React.useState({});

  // 获取当前激活模型的 max_context_tokens
  const activeModelConfig = models?.find(m => m.name === activeModel);
  const maxTokens = activeModelConfig?.max_context_tokens || 8192;

  // 请求后端获取 hidden system context tokens
  React.useEffect(() => {
    const fetchSystemTokens = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/system_context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: messages,
            persona_type: localStorage.getItem('persona_type') || 'simplified',
            current_file_path: selectedFilePath || '',
            cursor_line: 0,
            custom_max_tokens: maxTokens
          })
        });
        if (res.ok) {
          const data = await res.json();
          setBaseSystemTokens(data.baseSystemTokens || 0);
        }
      } catch (e) {
        console.error('Failed to fetch system tokens:', e);
      }
    };
    
    // 我们在会话改变或新消息发出后，以及切换具有不同最大 Token 数的模型时，静默刷新底层 Token 占用
    fetchSystemTokens();
  }, [messages.length, activeSessionId, selectedFilePath, activeModel, maxTokens]);

  // 计算前端动态 tokens
  React.useEffect(() => {
    try {
      let count = encode(inputText).length;
      
      // 简单近似计算：累加当前会话内的文本长度
      const recentMsgs = messages.slice(-20);
      for (const msg of recentMsgs) {
        if (typeof msg.content === 'string') {
          count += encode(msg.content).length;
        } else if (Array.isArray(msg.blocks)) {
           const txt = msg.blocks.filter(b => b.type === 'text').map(b => b.text).join('\n');
           count += encode(txt).length;
        }
      }
      setDynamicTokens(count);
    } catch (e) {
      console.error('Token count error:', e);
    }
  }, [inputText, messages]);

  const totalTokens = baseSystemTokens + dynamicTokens;
  const tokenRatio = Math.min(totalTokens / maxTokens, 1);
  // 颜色：安全为次要文本色，>70% 为粉色，>90% 为红色
  const tokenColor = tokenRatio > 0.9 ? 'var(--text-error, #f87171)' : tokenRatio > 0.7 ? 'var(--accent-pink)' : 'var(--text-secondary)';
  const radius = 6;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - tokenRatio * circumference;

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

  // 自定义 Markdown 渲染组件
  const MarkdownComponents = {
    // 覆盖斜体渲染，保持粉色动作文本效果
    em: ({node, ...props}) => <span className="action-text" {...props} />,
    // 覆盖代码块渲染，支持语法高亮
    code({node, inline, className, children, ...props}) {
      const match = /language-(\w+)/.exec(className || '');
      const syntaxStyle = theme === 'light' ? prism : vscDarkPlus;
      return !inline && match ? (
        <SyntaxHighlighter
          style={syntaxStyle}
          language={match[1]}
          PreTag="div"
          customStyle={{ borderRadius: '6px', margin: '1em 0' }}
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className={className} style={{ background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: '4px', color: 'var(--text-primary)', fontFamily: 'Consolas, Monaco, monospace', fontSize: '0.9em' }} {...props}>
          {children}
        </code>
      );
    }
  };

  const renderNormalizedBlocks = (blocks) => {
    return blocks.map((block, idx) => {
      if (block.type === 'thinking') {
        return <ThinkingBlock key={`thought_${idx}`} block={block} idx={idx} />;
      } else if (block.type === 'tool') {
        return <ToolBlock key={`tool_${idx}`} block={block} idx={idx} />;
      } else if (block.type === 'retry') {
        return <RetryBlock key={`retry_${idx}`} block={block} idx={idx} />;
      } else if (block.type === 'text') {
        return <div key={`text_${idx}`} className="text-block"><ReactMarkdown components={MarkdownComponents}>{block.text}</ReactMarkdown></div>;
      } else if (block.type === 'quiz') {
        return <QuizBlock 
          key={`quiz_${idx}`} 
          data={block.data}
          onQuizSubmit={(result) => {
            if (sendMessage) {
              const escapeQuotes = (str) => (str || '').replace(/"/g, '&quot;');
              const msg = `我选了：${result.selectedOption}\n<submit_quiz_result is_correct="${result.isCorrect}" selected="${escapeQuotes(result.selectedOption)}" />`;
              sendMessage(msg);
            }
          }}
        />;
      } else if (block.type === 'explainer') {
        return (
          <div key={`exp_${idx}`} style={{ margin: '16px 0', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px 12px', fontSize: '13px', fontWeight: 'bold', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-primary)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
              {block.title}
            </div>
            <div style={{ padding: '12px', background: 'var(--bg-panel)', fontSize: '13px', lineHeight: '1.6', color: 'var(--text-primary)' }}>
              <div className="text-block"><ReactMarkdown components={MarkdownComponents}>{block.text}</ReactMarkdown></div>
            </div>
          </div>
        );
      } else if (block.type === 'glossary') {
        return (
          <div key={`glos_${idx}`} style={{ margin: '12px 0', padding: '10px 14px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '6px', fontSize: '13px', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ marginTop: '2px' }}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg></span>
            <div>
              <span style={{ fontWeight: 'bold', color: '#10b981', marginRight: '6px' }}>{block.term}</span>
              <span style={{ color: 'var(--text-primary)', lineHeight: '1.5' }}>{block.text}</span>
            </div>
          </div>
        );
      }
      return null;
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
            if (msg.type === 'decay_prompt') {
              const state = decayStates[index] || 'prompt'; // 'prompt', 'loading', 'done', 'hidden'
              if (state === 'hidden') return null;
              
              return (
                <div key={index} className="system-info-msg" style={{ alignSelf: 'center', backgroundColor: 'var(--bg-tertiary)', border: '1px solid var(--accent-pink)', borderRadius: '6px', padding: '10px 14px', fontSize: '12px', color: 'var(--text-primary)', margin: '12px 0', maxWidth: '90%', textAlign: 'center', boxShadow: '0 2px 8px rgba(244, 114, 182, 0.15)' }}>
                  {state === 'prompt' && (
                    <>
                      <div style={{ marginBottom: '10px', fontWeight: 'bold' }}>💡 {msg.content}</div>
                      <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
                        <button onClick={async () => {
                          setDecayStates(prev => ({...prev, [index]: 'loading'}));
                          try {
                            const res = await fetch(`${API_BASE}/api/chat/force_decay`, { method: 'POST' });
                            if (res.ok) setDecayStates(prev => ({...prev, [index]: 'done'}));
                            else setDecayStates(prev => ({...prev, [index]: 'prompt'}));
                          } catch(e) {
                            setDecayStates(prev => ({...prev, [index]: 'prompt'}));
                          }
                        }} style={{ padding: '6px 14px', background: 'var(--accent-pink)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>立即整理</button>
                        <button onClick={() => {
                          setDecayStates(prev => ({...prev, [index]: 'hidden'}));
                        }} style={{ padding: '6px 14px', background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', borderRadius: '4px', cursor: 'pointer' }}>暂不整理</button>
                      </div>
                    </>
                  )}
                  {state === 'loading' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center', color: 'var(--accent-pink)', fontWeight: 'bold' }}>
                      <svg style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
                      导师正在整理学习档案当中，请稍后...
                    </div>
                  )}
                  {state === 'done' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'center', color: '#10b981', fontWeight: 'bold' }}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                      档案整理完毕，记忆已同步。
                    </div>
                  )}
                </div>
              );
            }

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
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                {msg.icon === 'books' && (
                  <svg style={{ animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite', color: 'var(--accent-pink)' }} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
                )}
                {msg.icon === 'check' && (
                  <svg style={{ color: '#10b981' }} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                )}
                {msg.content}
              </div>
            );
          }

          const blocks = msg.blocks || [{ type: 'text', text: msg.content || '' }];
          const mergedBlocks = parseAndMergeBlocks(blocks, msg.streaming);
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
                      {msg.timestamp && <span className="message-timestamp">{typeof msg.timestamp === 'string' && msg.timestamp.length > 16 ? msg.timestamp.substring(0, 16).replace('T', ' ') : msg.timestamp}</span>}
                      <span className="sender-name">你</span>
                    </div>
                    <div
                      className="avatar"
                      onClick={() => { setCropTarget('user'); fileInputRef.current?.click(); }}
                      title="点击更换头像"
                      style={{ cursor: 'pointer' }}
                    >
                      {userAvatar && userAvatar !== 'default_student' ? (
                        <img src={userAvatar} alt="用户头像" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                      ) : (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: '65%', height: '65%', color: 'var(--text-primary)' }}>
                          <circle cx="12" cy="6" r="3" />
                          <path d="M12 13c-2.5-1.5-6.5-1.5-9 0v6.5c2.5-1.5 6.5-1.5 9 0" />
                          <path d="M12 13c2.5-1.5 6.5-1.5 9 0v6.5c-2.5-1.5-6.5-1.5-9 0" />
                          <line x1="12" y1="13" x2="12" y2="19.5" />
                        </svg>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div
                      className="avatar"
                      onClick={() => { setCropTarget('assistant'); fileInputRef.current?.click(); }}
                      title="点击更换导师头像"
                      style={{ cursor: 'pointer' }}
                    >
                      {assistantAvatar && assistantAvatar !== 'default_tutor' ? (
                        <img src={assistantAvatar} alt="导师头像" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
                      ) : (
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: '65%', height: '65%', color: 'var(--accent-pink)' }}>
                          <path d="M22 10v6M2 10l10-5 10 5-10 5z" />
                          <path d="M6 12v5c3 3 9 3 12 0v-5" />
                        </svg>
                      )}
                    </div>
                    <div className="sender-group">
                      <span className="sender-name">媚吻锋</span>
                      {msg.timestamp && <span className="message-timestamp">{typeof msg.timestamp === 'string' && msg.timestamp.length > 16 ? msg.timestamp.substring(0, 16).replace('T', ' ') : msg.timestamp}</span>}
                    </div>
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
                <>
                  <div className="message-bubble">
                    {msg.blocks && msg.blocks.length > 0 ? (
                      renderNormalizedBlocks(parseAndMergeBlocks(msg.blocks).filter(b => b.type !== 'retry'))
                    ) : (
                      <div className="message-content">
                        {renderNormalizedBlocks(parseAndMergeBlocks(msg.content))}
                      </div>
                    )}
                    {(isStreaming && msg.streaming && !pendingApproval) && <span className="typing-cursor" />}
                    {isUser && (
                      <button className="edit-msg-btn" onClick={handleStartEdit} title="编辑并重发">
                        <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                          <path d="M11.5 1a.5.5 0 0 1 .354.146l2 2A.5.5 0 0 1 14 3.5v.793L4.5 13.793 1 15l1.207-3.5L11.5 1zm-1.207 2.5L8.5 1.707 2 8.207V9.5h1.293L11.5 1.5zm1.914 0l.793-.793-1.207-1.207-.793.793 1.207 1.207z" />
                        </svg>
                      </button>
                    )}
                  </div>
                  {msg.blocks && msg.blocks.some(b => b.type === 'retry') && (
                    <div style={{ marginTop: '8px' }}>
                      {renderNormalizedBlocks(parseAndMergeBlocks(msg.blocks).filter(b => b.type === 'retry'))}
                    </div>
                  )}
                </>
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
              ⚡ Quick Commands
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

        {/* 整体输入区容器：确保卡片浮在 Tracking 栏和输入框的上方 */}
        <div style={{ position: 'relative', display: 'flex', flexDirection: 'column' }}>
          {/* 瞬态拦截审批卡片 */}
          <BashApprovalCard 
            pendingApproval={pendingApproval}
            onApprove={() => handleApprovalSubmit('approve')}
            onReject={() => handleApprovalSubmit('reject')}
          />

          <MissionProposalCard
            proposalData={pendingMission}
            onConfirm={(data) => {
              const escapeQuotes = (str) => (str || '').replace(/"/g, '&quot;');
              const msg = `好的老婆，我确认学习目标！<finalize_mission goal="${escapeQuotes(data.goal)}" time="${escapeQuotes(data.time)}" constraints="${escapeQuotes(data.constraints)}" skill="${escapeQuotes(data.skill)}" />`;
              if (sendMessage) sendMessage(msg);
            }}
            onReject={(feedback, data) => {
              const msg = `对这个目标草案不太满意：${feedback}`;
              if (sendMessage) sendMessage(msg);
            }}
          />

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
              <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M13.85 4.44l-3.28-3.3a.5.5 0 0 0-.35-.14H2.5a.5.5 0 0 0-.5.5v13a.5.5 0 0 0 .5.5h11a.5.5 0 0 0 .5-.5V4.8a.5.5 0 0 0-.15-.36zM10.5 2.21L12.79 4.5H10.5V2.21zM13 14H3V2h6.5v3a.5.5 0 0 0 .5.5h3v8.5z" /></svg>
              Tracking (@current_file): {selectedFilePath.split('\\').pop().split('/').pop()}
            </div>
          )}

          {/* 卡片式输入框 */}
          <div className="input-wrapper" style={{ borderTopLeftRadius: isVsCode && selectedFilePath ? '0' : '8px', borderTopRightRadius: isVsCode && selectedFilePath ? '0' : '8px' }}>
          {/* 行1：文字输入区 */}
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Chat with tutor..."
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

              {/* 环形 Token 指示器 */}
              <div 
                className="token-ring-indicator" 
                title={`Token 用量: ${totalTokens} / ${maxTokens}\n包含隐藏上下文 (系统设定/RAG/记忆): ${baseSystemTokens}\n当前对话: ${dynamicTokens}`}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  width: '24px', 
                  height: '24px',
                  cursor: 'help'
                }}
              >
                <svg width="18" height="18" viewBox="0 0 18 18">
                  <circle 
                    cx="9" cy="9" r={radius} 
                    fill="none" 
                    stroke="var(--border-color)" 
                    strokeWidth="2.5" 
                  />
                  <circle 
                    cx="9" cy="9" r={radius} 
                    fill="none" 
                    stroke={tokenColor} 
                    strokeWidth="2.5" 
                    strokeDasharray={circumference} 
                    strokeDashoffset={strokeDashoffset} 
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 0.3s ease, stroke 0.3s ease', transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
                  />
                </svg>
              </div>

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
                    { cmd: '/lesson', label: '/lesson' },
                    { cmd: '/submit', label: '/submit' },
                    { cmd: '/reward', label: '/reward' },
                    { cmd: '/summarize', label: '/summarize' },
                    { cmd: '/prepare', label: '/prepare' },
                    { cmd: '/update_persona', label: '/update_persona' },
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

            {/* 右侧：发送/停止按钮 */}
            {isStreaming ? (
              <button
                className="stop-button pulse-stop"
                onClick={stopGeneration}
                title="停止生成"
              >
                <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                  <rect x="3" y="3" width="10" height="10" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                className="send-button"
                onClick={sendMessage}
                disabled={!inputText.trim()}
                title="发送消息"
              >
                <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 1l6 6h-5v8H7V7H2l6-6z" />
                </svg>
              </button>
            )}
          </div>
          </div>
        </div>
      </div>
    </section>
  );
}
