import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { API_BASE } from '../config';

const PreviewEditModal = ({ isOpen, onClose, fileData, onSaveSuccess }) => {
  const [mode, setMode] = useState('preview');
  const [editedContent, setEditedContent] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);

  useEffect(() => {
    if (fileData) {
      setEditedContent(fileData.content || '');
      setMode('preview');
      setSaveStatus(null);
    }
  }, [fileData]);

  if (!isOpen || !fileData) return null;

  // 解析路径展示面包屑与分类标签
  const pathParts = (fileData.path || '').replace(/\\/g, '/').split('/');
  const fileName = pathParts.pop() || fileData.path;
  const folderName = pathParts.join('/') || 'Root';

  const getCategoryBadge = (folder) => {
    const lower = folder.toLowerCase();
    if (lower.includes('reference') || lower.includes('docs')) return { label: '📚 知识引录 / Codex', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.12)' };
    if (lower.includes('lesson') || lower.includes('course')) return { label: '📖 理论课时 / Lesson', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' };
    if (lower.includes('sandbox') || lower.includes('exercise')) return { label: '💻 互动沙盒 / Sandbox', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.12)' };
    return { label: '📄 档案资源 / File', color: '#64748b', bg: 'rgba(100, 116, 139, 0.12)' };
  };

  const badge = getCategoryBadge(folderName);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/chat/materials/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: fileData.path,
          content: editedContent
        })
      });

      if (res.ok) {
        setSaveStatus({
          type: 'success',
          message: '✨ 保存成功！RAG 向量库后台同步已触发'
        });
        if (onSaveSuccess) {
          onSaveSuccess(editedContent);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setSaveStatus({
          type: 'error',
          message: `❌ 保存失败：${errData.detail || res.statusText}`
        });
      }
    } catch (e) {
      setSaveStatus({
        type: 'error',
        message: `❌ 网络请求出错：${e.message}`
      });
    } finally {
      setIsSaving(false);
    }
  };

  // 专为 Studio 级排版设计的定制化 Markdown 组件
  const markdownComponents = {
    h1: ({ children, ...props }) => (
      <h1
        style={{
          fontSize: '24px',
          fontWeight: '700',
          color: 'var(--modal-text, #1e293b)',
          borderBottom: '1px solid var(--modal-border, #e2e8f0)',
          paddingBottom: '12px',
          marginTop: '8px',
          marginBottom: '20px',
          fontFamily: "'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: '-0.02em'
        }}
        {...props}
      >
        {children}
      </h1>
    ),
    h2: ({ children, ...props }) => (
      <h2
        style={{
          fontSize: '19px',
          fontWeight: '600',
          color: 'var(--modal-text, #1e293b)',
          marginTop: '28px',
          marginBottom: '14px',
          fontFamily: "'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
          letterSpacing: '-0.01em'
        }}
        {...props}
      >
        {children}
      </h2>
    ),
    h3: ({ children, ...props }) => (
      <h3
        style={{
          fontSize: '16px',
          fontWeight: '600',
          color: 'var(--modal-text, #1e293b)',
          marginTop: '22px',
          marginBottom: '10px',
          fontFamily: "'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif'"
        }}
        {...props}
      >
        {children}
      </h3>
    ),
    p: ({ children, ...props }) => (
      <p
        style={{
          fontSize: '15px',
          lineHeight: '1.8',
          color: 'var(--modal-text, #334155)',
          marginBottom: '16px',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        }}
        {...props}
      >
        {children}
      </p>
    ),
    ul: ({ children, ...props }) => (
      <ul
        style={{
          paddingLeft: '24px',
          marginBottom: '18px',
          color: 'var(--modal-text, #334155)',
          fontSize: '15px',
          lineHeight: '1.8',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        }}
        {...props}
      >
        {children}
      </ul>
    ),
    ol: ({ children, ...props }) => (
      <ol
        style={{
          paddingLeft: '24px',
          marginBottom: '18px',
          color: 'var(--modal-text, #334155)',
          fontSize: '15px',
          lineHeight: '1.8',
          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        }}
        {...props}
      >
        {children}
      </ol>
    ),
    blockquote: ({ children, ...props }) => (
      <blockquote
        style={{
          borderLeft: '4px solid var(--modal-accent, #3b82f6)',
          background: 'var(--modal-code-bg, #f8fafc)',
          padding: '14px 18px',
          borderRadius: '0 8px 8px 0',
          margin: '20px 0',
          color: 'var(--modal-text-muted, #64748b)',
          fontStyle: 'normal'
        }}
        {...props}
      >
        {children}
      </blockquote>
    ),
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <div style={{ margin: '20px 0', borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--modal-border, rgba(255,255,255,0.1))', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={match[1]}
            PreTag="div"
            customStyle={{ margin: 0, padding: '18px', background: '#181a20', fontSize: '13.5px', lineHeight: '1.6', fontFamily: "'Fira Code', 'JetBrains Mono', Consolas, monospace" }}
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      ) : (
        <code
          className={className}
          style={{
            background: 'var(--modal-code-bg, #f1f5f9)',
            border: '1px solid var(--modal-border, #e2e8f0)',
            padding: '3px 7px',
            borderRadius: '6px',
            color: 'var(--modal-accent, #2563eb)',
            fontFamily: "'Fira Code', 'JetBrains Mono', Consolas, monospace",
            fontSize: '0.88em',
            fontWeight: '500',
            whiteSpace: 'pre-wrap'
          }}
          {...props}
        >
          {children}
        </code>
      );
    }
  };

  return (
    <div
      className="modal-backdrop"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(12px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        animation: 'fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-container"
        style={{
          width: '100%',
          maxWidth: '920px',
          height: '86vh',
          maxHeight: '840px',
          backgroundColor: 'var(--modal-bg, #ffffff)',
          borderRadius: '16px',
          border: '1px solid var(--modal-border, #e2e8f0)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.45), 0 0 0 1px rgba(255, 255, 255, 0.05) inset',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          transition: 'background-color 0.2s ease, border-color 0.2s ease'
        }}
      >
        {/* Header - Studio Breadcrumb & Segmented Control */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 24px',
            borderBottom: '1px solid var(--modal-border, #e2e8f0)',
            backgroundColor: 'var(--modal-header-bg, #f8f9fb)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: '600',
                color: badge.color,
                background: badge.bg,
                border: `1px solid ${badge.color}33`,
                flexShrink: 0
              }}
            >
              {badge.label}
            </span>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '14px',
                color: 'var(--modal-text-muted, #64748b)',
                fontFamily: "'Inter', sans-serif",
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {folderName !== 'Root' && <span>{folderName} /</span>}
              <span style={{ fontWeight: '600', color: 'var(--modal-text, #1e293b)' }}>{fileName}</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexShrink: 0 }}>
            {/* macOS / Linear 风格分段控制器 */}
            <div
              style={{
                display: 'flex',
                background: 'var(--modal-code-bg, #f1f5f9)',
                padding: '3px',
                borderRadius: '10px',
                border: '1px solid var(--modal-border, rgba(0,0,0,0.06))'
              }}
            >
              <button
                onClick={() => setMode('preview')}
                style={{
                  padding: '6px 16px',
                  borderRadius: '7px',
                  border: 'none',
                  background: mode === 'preview' ? 'var(--modal-bg, #ffffff)' : 'transparent',
                  color: mode === 'preview' ? 'var(--modal-text, #1e293b)' : 'var(--modal-text-muted, #64748b)',
                  cursor: 'pointer',
                  fontWeight: mode === 'preview' ? '600' : '500',
                  fontSize: '13px',
                  boxShadow: mode === 'preview' ? '0 2px 6px rgba(0, 0, 0, 0.08)' : 'none',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
                }}
              >
                📖 效果预览
              </button>
              <button
                onClick={() => setMode('edit')}
                style={{
                  padding: '6px 16px',
                  borderRadius: '7px',
                  border: 'none',
                  background: mode === 'edit' ? 'var(--modal-bg, #ffffff)' : 'transparent',
                  color: mode === 'edit' ? 'var(--modal-text, #1e293b)' : 'var(--modal-text-muted, #64748b)',
                  cursor: 'pointer',
                  fontWeight: mode === 'edit' ? '600' : '500',
                  fontSize: '13px',
                  boxShadow: mode === 'edit' ? '0 2px 6px rgba(0, 0, 0, 0.08)' : 'none',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
                }}
              >
                ✏️ 源码编辑
              </button>
            </div>

            <button
              title="关闭窗口"
              onClick={onClose}
              style={{
                background: 'transparent',
                border: '1px solid transparent',
                color: 'var(--modal-text-muted, #64748b)',
                fontSize: '16px',
                cursor: 'pointer',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '8px',
                transition: 'all 0.15s ease'
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.background = 'var(--modal-code-bg, #f1f5f9)';
                e.currentTarget.style.color = 'var(--modal-text, #1e293b)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--modal-text-muted, #64748b)';
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Body - Studio Typography Area */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '32px 40px',
            position: 'relative',
            backgroundColor: 'var(--modal-bg, #ffffff)'
          }}
        >
          {mode === 'preview' ? (
            <div
              className="markdown-body"
              style={{
                color: 'var(--modal-text, #334155)',
                fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                maxWidth: '800px',
                margin: '0 auto'
              }}
            >
              <ReactMarkdown components={markdownComponents}>{editedContent}</ReactMarkdown>
            </div>
          ) : (
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              placeholder="在此输入 Markdown 源码内容..."
              style={{
                width: '100%',
                height: '100%',
                minHeight: '450px',
                background: 'var(--modal-code-bg, #f8fafc)',
                color: 'var(--modal-text, #0f172a)',
                border: '1px solid var(--modal-border, #e2e8f0)',
                borderRadius: '10px',
                padding: '20px',
                fontFamily: "'Fira Code', 'JetBrains Mono', Consolas, monospace",
                fontSize: '14px',
                lineHeight: '1.7',
                outline: 'none',
                resize: 'none',
                boxShadow: '0 2px 4px rgba(0,0,0,0.02) inset'
              }}
            />
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 24px',
            borderTop: '1px solid var(--modal-border, #e2e8f0)',
            backgroundColor: 'var(--modal-header-bg, #f8f9fb)'
          }}
        >
          <div>
            {saveStatus && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '13px',
                  color: saveStatus.type === 'success' ? '#10b981' : '#ef4444',
                  fontWeight: '600',
                  background: saveStatus.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${saveStatus.type === 'success' ? '#10b98133' : '#ef444433'}`
                }}
              >
                {saveStatus.message}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={onClose}
              style={{
                padding: '8px 18px',
                borderRadius: '8px',
                border: '1px solid var(--modal-border, #e2e8f0)',
                background: 'var(--modal-bg, #ffffff)',
                color: 'var(--modal-text, #334155)',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '13px',
                transition: 'all 0.15s ease'
              }}
              onMouseOver={(e) => (e.currentTarget.style.background = 'var(--modal-code-bg, #f1f5f9)')}
              onMouseOut={(e) => (e.currentTarget.style.background = 'var(--modal-bg, #ffffff)')}
            >
              关闭
            </button>
            {mode === 'edit' && (
              <button
                onClick={handleSave}
                disabled={isSaving || editedContent === (fileData.content || '')}
                style={{
                  padding: '8px 20px',
                  borderRadius: '8px',
                  border: 'none',
                  background: isSaving || editedContent === (fileData.content || '')
                    ? 'rgba(59, 130, 246, 0.4)'
                    : '#3b82f6',
                  color: '#ffffff',
                  cursor: isSaving || editedContent === (fileData.content || '') ? 'not-allowed' : 'pointer',
                  fontWeight: '600',
                  fontSize: '13px',
                  boxShadow: isSaving || editedContent === (fileData.content || '') ? 'none' : '0 4px 12px rgba(59, 130, 246, 0.35)',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)'
                }}
              >
                {isSaving ? '正在保存...' : '💾 保存修改'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PreviewEditModal;
