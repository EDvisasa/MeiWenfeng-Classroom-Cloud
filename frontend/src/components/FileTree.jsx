import React, { useState, useEffect } from 'react';

export default function FileTree({ 
  selectedFilePath, 
  selectedFileContent,
  onFileSelect,
  rootPath,
  setRootPath
}) {
  const [treeData, setTreeData] = useState([]);
  const [openNodes, setOpenNodes] = useState({});
  const [syncStatus, setSyncStatus] = useState({});
  const [loading, setLoading] = useState(false);
  const [inputPath, setInputPath] = useState(rootPath || '');

  useEffect(() => {
    fetchFileTree(rootPath);
    fetchSyncStatus();
    
    // 轮询 RAGFlow 文档解析状态，间隔5秒
    const interval = setInterval(fetchSyncStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchFileTree = async (path) => {
    setLoading(true);
    try {
      const url = `http://localhost:8000/api/chat/files/list?root_dir=${encodeURIComponent(path || '')}`;
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
      const res = await fetch('http://localhost:8000/api/chat/files/sync_status');
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
      const res = await fetch(`http://localhost:8000/api/chat/files/content?file_path=${encodeURIComponent(node.path)}`);
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
      
      const res = await fetch('http://localhost:8000/api/chat/files/sync', {
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
                title="上传至 RAGFlow"
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
    </section>
  );
}
