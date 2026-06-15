import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';
export default function FileTree({ 
  selectedFilePath, 
  selectedFileContent,
  onFileSelect,
  rootPath,
  setRootPath,
  sessions = [],
  activeSessionId = '',
  onSwitchSession,
  onNewSession,
  onDeleteSession
}) {
  const [treeData, setTreeData] = useState([]);
  const [openNodes, setOpenNodes] = useState({});
  const [syncStatus, setSyncStatus] = useState({});
  const [loading, setLoading] = useState(false);
  const [inputPath, setInputPath] = useState(rootPath || '');
  const [activeTab, setActiveTab] = useState('files'); // 'files' | 'history'

  useEffect(() => {
    fetchFileTree(rootPath);
    fetchSyncStatus();
    
    // 轮询知识库文档解析状态，间隔15秒，避免终端日志刷屏
    const interval = setInterval(fetchSyncStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  const fetchFileTree = async (path) => {
    setLoading(true);
    try {
      const url = `${API_BASE}/api/chat/files/list?root_dir=${encodeURIComponent(path || '')}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setTreeData(data.tree || []);
        if (data.root_path) {
          setRootPath(data.root_path);
          setInputPath(data.root_path);
        }
      }
    } catch (e) {
      console.error("Failed to fetch file tree:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/files/sync_status`);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'success') {
          setSyncStatus(data.documents || {});
        }
      }
    } catch (e) {
      console.error("Failed to fetch sync status:", e);
    }
  };

  const handleMount = () => {
    fetchFileTree(inputPath);
  };

  const handleRefresh = () => {
    fetchFileTree(rootPath);
    fetchSyncStatus();
  };

  const toggleNode = (path) => {
    setOpenNodes(prev => ({
      ...prev,
      [path]: !prev[path]
    }));
  };

  const handleFileClick = async (node) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/files/content?file_path=${encodeURIComponent(node.path)}`);
      if (res.ok) {
        const data = await res.json();
        onFileSelect(node.path, data.content);
      }
    } catch (e) {
      console.error("Failed to fetch file content:", e);
    }
  };

  const handleFileSync = async (node) => {
    try {
      setSyncStatus(prev => ({
        ...prev,
        [node.name]: { status: 'parsing' }
      }));
      
      const res = await fetch(`${API_BASE}/api/chat/files/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: node.path })
      });
      if (res.ok) {
        fetchSyncStatus();
      } else {
        setSyncStatus(prev => {
          const updated = { ...prev };
          delete updated[node.name];
          return updated;
        });
      }
    } catch (e) {
      console.error("Failed to sync file:", e);
    }
  };

  const handleSyncAllMarkdown = async () => {
    const mdFiles = [];
    const findMd = (nodes) => {
      for (const n of nodes) {
        if (n.is_dir) {
          findMd(n.children || []);
        } else if (n.name.endsWith('.md')) {
          mdFiles.push(n);
        }
      }
    };
    findMd(treeData);

    for (const f of mdFiles) {
      await handleFileSync(f);
    }
  };

  const renderNode = (node) => {
    const isSelected = selectedFilePath === node.path;
    const isFolder = node.is_dir;
    const isOpen = openNodes[node.path];

    if (isFolder) {
      return (
        <li key={node.path} className="tree-folder">
          <div 
            className="folder-title" 
            onClick={() => toggleNode(node.path)}
          >
            <span>{isOpen ? '📂' : '📁'}</span>
            <span>{node.name}</span>
          </div>
          {isOpen && node.children && (
            <ul className="folder-items">
              {node.children.map(child => renderNode(child))}
            </ul>
          )}
        </li>
      );
    } else {
      const fileStatus = syncStatus[node.name];
      let statusDot = '⚪';
      let statusTitle = '未同步';
      if (fileStatus) {
        if (fileStatus.status === 'completed' || fileStatus.status === 'success') {
          statusDot = '🟢';
          statusTitle = '已同步';
        } else if (fileStatus.status === 'parsing' || fileStatus.status === 'running') {
          statusDot = '🔄';
          statusTitle = '解析中';
        }
      }

      return (
        <li 
          key={node.path} 
          className={`file-item ${isSelected ? 'active' : ''}`}
          onClick={() => handleFileClick(node)}
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
            <span>📄</span>
            <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{node.name}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
            <span title={statusTitle} style={{ fontSize: '10px' }}>{statusDot}</span>
            {!fileStatus && (
              <button 
                onClick={(e) => { e.stopPropagation(); handleFileSync(node); }}
                title="上传至知识库"
                style={{
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  fontSize: '11px',
                  padding: '0 2px',
                  color: 'var(--text-secondary)'
                }}
              >
                📤
              </button>
            )}
          </div>
        </li>
      );
    }
  };

  return (
    <section className="ide-panel left-panel">
      {/* Tab 切换栏 */}
      <div 
        style={{ 
          display: 'flex', 
          borderBottom: '1px solid var(--border-color)', 
          background: 'rgba(255, 255, 255, 0.2)' 
        }}
      >
        <button 
          onClick={() => setActiveTab('files')}
          style={{
            flex: 1,
            padding: '10px 12px',
            fontSize: '12px',
            fontWeight: 'bold',
            background: activeTab === 'files' ? 'rgba(255, 255, 255, 0.4)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'files' ? '2.5px solid var(--accent-pink)' : '2.5px solid transparent',
            cursor: 'pointer',
            color: activeTab === 'files' ? 'var(--accent-pink)' : 'var(--text-secondary)',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          📁 项目讲义
        </button>
        <button 
          onClick={() => setActiveTab('history')}
          style={{
            flex: 1,
            padding: '10px 12px',
            fontSize: '12px',
            fontWeight: 'bold',
            background: activeTab === 'history' ? 'rgba(255, 255, 255, 0.4)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'history' ? '2.5px solid var(--accent-pink)' : '2.5px solid transparent',
            cursor: 'pointer',
            color: activeTab === 'history' ? 'var(--accent-pink)' : 'var(--text-secondary)',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          📜 历史记录
        </button>
      </div>

      {activeTab === 'files' ? (
        <>
          {/* 路径控制挂载区域 */}
          <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input 
                type="text" 
                value={inputPath}
                onChange={(e) => setInputPath(e.target.value)}
                placeholder="本地路径，如 D:/MeiWenfeng-Classroom"
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  fontSize: '12px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  outline: 'none'
                }}
              />
              <button 
                onClick={handleMount}
                style={{
                  padding: '4px 8px',
                  fontSize: '11px',
                  background: 'var(--accent-pink)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                挂载
              </button>
            </div>
            
            {/* 工具按钮栏 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px' }}>
              <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>
                {loading ? '正在读取...' : '本地项目浏览器'}
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  onClick={handleRefresh} 
                  title="刷新文件树"
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px' }}
                >
                  🔄
                </button>
                <button 
                  onClick={handleSyncAllMarkdown} 
                  title="同步所有 Markdown"
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '13px' }}
                >
                  🚀
                </button>
              </div>
            </div>
          </div>

          <div className="panel-header" style={{ height: '30px', padding: '0 12px', background: 'rgba(0,0,0,0.05)' }}>
            <span style={{ fontSize: '11px', textTransform: 'uppercase' }}>📁 {rootPath ? rootPath.split('/').pop() : '未挂载'}</span>
          </div>

          <ul className="file-tree" style={{ flex: 1 }}>
            {treeData.length > 0 ? (
              treeData.map(node => renderNode(node))
            ) : (
              <div style={{ padding: '20px', textAlign: 'center', fontSize: '12px', color: 'var(--text-secondary)' }}>
                没有文件或文件夹。请输入路径进行挂载。
              </div>
            )}
          </ul>
          
          {/* 文件预览区 */}
          <div className="panel-header" style={{ borderTop: '1px solid var(--border-color)' }}>
            <span>📖 文件预览</span>
          </div>
          <div style={{ flex: 1.2, padding: '14px', overflowY: 'auto', fontSize: '13px', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
            {selectedFilePath ? (
              <div style={{ whiteSpace: 'pre-wrap', fontFamily: selectedFilePath.endsWith('.txt') ? 'var(--font-mono)' : 'var(--font-sans)' }}>
                {selectedFileContent}
              </div>
            ) : (
              <div style={{ textAlign: 'center', marginTop: '20px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                选择左侧文件以进行预览
              </div>
            )}
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* 新建会话按钮区域 */}
          <div style={{ padding: '12px', borderBottom: '1px solid var(--border-color)' }}>
            <button 
              onClick={onNewSession}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'var(--accent-pink)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                boxShadow: '0 2px 8px rgba(75, 108, 183, 0.2)'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--accent-pink-hover)'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--accent-pink)'}
            >
              ➕ 新建对话会话
            </button>
          </div>

          {/* 会话列表 */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '8px' }}>
            {sessions.map(s => {
              const isActive = s.id === activeSessionId;
              return (
                <div 
                  key={s.id}
                  onClick={() => onSwitchSession(s.id)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    marginBottom: '6px',
                    cursor: 'pointer',
                    background: isActive ? 'rgba(75, 108, 183, 0.08)' : 'transparent',
                    borderLeft: isActive ? '3px solid var(--accent-pink)' : '3px solid transparent',
                    transition: 'all 0.2s'
                  }}
                  className="session-item"
                  onMouseOver={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)';
                  }}
                  onMouseOut={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', flex: 1 }}>
                    <span style={{ fontSize: '14px' }}>💬</span>
                    <span style={{ 
                      fontSize: '13px', 
                      color: isActive ? 'var(--accent-pink)' : 'var(--text-primary)',
                      fontWeight: isActive ? '600' : 'normal',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {s.title}
                    </span>
                  </div>
                  
                  <button 
                    onClick={(e) => onDeleteSession(s.id, e)}
                    title="删除会话"
                    style={{
                      border: 'none',
                      background: 'transparent',
                      cursor: 'pointer',
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      padding: '4px',
                      opacity: isActive ? 1 : 0.6,
                      transition: 'opacity 0.2s'
                    }}
                    onMouseOver={(e) => {
                      e.stopPropagation();
                      e.currentTarget.style.opacity = 1;
                      e.currentTarget.style.color = 'var(--danger)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }}
                  >
                    🗑️
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 底部保留：因为是全盘同步，保留全局状态栏位置 */}
      <div style={{ padding: '10px', background: 'var(--surface-color)', borderTop: '1px solid var(--border-color)' }}>
        <h4 style={{ fontSize: '13px', margin: '0 0 10px 0', color: 'var(--text-secondary)' }}>知识库同步状态 (ChromaDB)</h4>
        {Object.keys(syncStatus).length > 0 ? (
          Object.entries(syncStatus).map(([filename, fileStatus]) => (
            <div key={filename} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '150px' }}>📄 {filename}</span>
              <span>{fileStatus.status === 'completed' || fileStatus.status === 'success' ? '🟢' : '🔄'}</span>
            </div>
          ))
        ) : (
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
            🟢 已连接 (暂无手动挂载的文档)
          </div>
        )}
      </div>
    </section>
  );
}
