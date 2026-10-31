import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../config';
export default function DatabaseViewer({ onClose }) {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState('');
  const [tableData, setTableData] = useState({ columns: [], data: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedCell, setExpandedCell] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [totalCount, setTotalCount] = useState(0);
  const dragPosRef = useRef({ x: 0, y: 0 });

  // Fetch list of tables on mount
  useEffect(() => {
    fetchTables();
  }, []);

  // Fetch table data when a table is selected
  useEffect(() => {
    setExpandedCell(null);
    setCurrentPage(1);
    if (selectedTable) {
      fetchTableData(selectedTable, 1, pageSize);
    } else {
      setTableData({ columns: [], data: [] });
      setTotalCount(0);
    }
  }, [selectedTable]);

  // Handle Escape key to collapse expanded cell first, or close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (expandedCell) {
          setExpandedCell(null);
        } else if (onClose) {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [expandedCell, onClose]);

  const fetchTables = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/db/tables`);
      if (res.ok) {
        const data = await res.json();
        setTables(data.tables || []);
        if (data.tables && data.tables.length > 0) {
          setSelectedTable(data.tables[0]);
        }
      } else {
        setError('Failed to fetch tables');
      }
    } catch (err) {
      setError(err.toString());
    }
  };

  const fetchTableData = async (tableName, page = currentPage, size = pageSize) => {
    if (!tableName) return;
    setLoading(true);
    setError('');
    setExpandedCell(null);
    try {
      const offset = (page - 1) * size;
      const res = await fetch(`${API_BASE}/api/chat/db/tables/${tableName}?limit=${size}&offset=${offset}`);
      if (res.ok) {
        const data = await res.json();
        setTableData({ columns: data.columns || [], data: data.data || [] });
        const total = typeof data.total === 'number' ? data.total : (data.data ? data.data.length : 0);
        setTotalCount(total);
      } else {
        setError(`Failed to fetch data for ${tableName}`);
      }
    } catch (err) {
      setError(err.toString());
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const startRow = totalCount === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endRow = Math.min(currentPage * pageSize, totalCount);

  const handlePrevPage = () => {
    if (currentPage > 1 && !loading) {
      const newPage = currentPage - 1;
      setCurrentPage(newPage);
      fetchTableData(selectedTable, newPage, pageSize);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages && !loading) {
      const newPage = currentPage + 1;
      setCurrentPage(newPage);
      fetchTableData(selectedTable, newPage, pageSize);
    }
  };

  const handlePageSizeChange = (e) => {
    const newSize = Number(e.target.value);
    setPageSize(newSize);
    setCurrentPage(1);
    fetchTableData(selectedTable, 1, newSize);
  };

  return (
    <div className="crop-modal-overlay" style={{ zIndex: 9999 }}>
      <div 
        className="crop-modal-content" 
        style={{ 
          width: '80%', 
          maxWidth: '1000px', 
          height: '80vh', 
          display: 'flex', 
          flexDirection: 'column', 
          padding: '0', 
          overflow: 'hidden' 
        }}
      >
        {/* Header */}
        <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-secondary)' }}>
          <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px', fontSize: '15px' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ verticalAlign: 'middle' }}><path d="M14 3c0 1.1-2.7 2-6 2S2 4.1 2 3s2.7-2 6-2 6 .9 6 2zm0 4c0 1.1-2.7 2-6 2S2 8.1 2 7V5c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm0 4c0 1.1-2.7 2-6 2S2 12.1 2 11V9c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm-6 4c-3.3 0-6-.9-6-2v-2c.8.6 2.3 1 4 1s3.2-.4 4-1v2c0 1.1-2.7 2-6 2z"/></svg>
            内置数据库查看器 (只读)
          </h3>
          <button 
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: '20px', cursor: 'pointer', color: 'var(--text-secondary)' }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          {/* Sidebar */}
          <div style={{ width: '200px', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)' }}>
            <div style={{ padding: '12px', fontSize: '13px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>数据表列表</div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {tables.map(t => (
                <div 
                  key={t}
                  onClick={() => setSelectedTable(t)}
                  style={{
                    padding: '10px 16px',
                    cursor: 'pointer',
                    fontSize: '13px',
                    background: selectedTable === t ? 'rgba(75, 108, 183, 0.1)' : 'transparent',
                    borderLeft: selectedTable === t ? '3px solid var(--accent-pink)' : '3px solid transparent',
                    color: selectedTable === t ? 'var(--accent-pink)' : 'var(--text-primary)',
                    fontWeight: selectedTable === t ? 'bold' : 'normal',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                >
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '6px', flexShrink: 0 }}><path d="M1 3h14v10H1V3zm2 2v2h3V5H3zm5 0v2h5V5H8zM3 8v3h3V8H3zm5 0v3h5V8H8z"/></svg>
                  {t}
                </div>
              ))}
            </div>
          </div>

          {/* Main Content */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-primary)' }}>
            
            {/* Toolbar */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'relative', zIndex: 20, background: 'var(--bg-primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '14px', fontWeight: 'bold' }}>{selectedTable || '请选择数据表'}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  💡 点击单元格可原地展开 / 展开后右下角可自由拉伸宽高
                </span>
              </div>
              <button 
                onClick={() => selectedTable && fetchTableData(selectedTable, currentPage, pageSize)}
                disabled={!selectedTable || loading}
                style={{
                  padding: '6px 12px',
                  background: 'var(--accent-pink)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (selectedTable && !loading) ? 'pointer' : 'not-allowed',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  opacity: loading ? 0.7 : 1
                }}
              >
                {loading ? '刷新中...' : '🔄 刷新当前表'}
              </button>
            </div>

            {/* Error Message */}
            {error && (
              <div style={{ padding: '12px 16px', color: 'var(--danger)', fontSize: '13px', background: 'rgba(220, 20, 60, 0.1)' }}>
                {error}
              </div>
            )}

            {/* Table Area */}
            <div style={{ flex: 1, overflow: 'auto', padding: '0 16px 16px 16px', position: 'relative' }}>
              {tableData.columns.length > 0 ? (
                <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: '13px', textAlign: 'left' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                    <tr>
                      {tableData.columns.map(col => (
                        <th key={col} style={{ 
                          padding: '10px 12px', 
                          borderBottom: '2px solid var(--border-color)', 
                          background: 'var(--bg-secondary)', 
                          position: 'sticky', 
                          top: 0, 
                          zIndex: 10,
                          color: 'var(--text-primary)',
                          fontWeight: '600'
                        }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.data.map((row, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        {tableData.columns.map(col => {
                          const cellKey = `${idx}_${col}`;
                          const isExpanded = expandedCell === cellKey;
                          let cellValue = row[col];
                          const isNull = cellValue === null || cellValue === undefined;

                          // 保持完整原始字符串用于缩放展开
                          let fullText = isNull 
                            ? 'NULL' 
                            : (typeof cellValue === 'object' ? JSON.stringify(cellValue, null, 2) : String(cellValue));

                          // 未展开时的紧凑文本：超长文本保留前 160 字符并提示点击缩放
                          const isLong = fullText.length > 160;
                          let displayText = fullText;
                          if (!isExpanded && isLong) {
                            displayText = fullText.substring(0, 160) + '... (点击缩放展开)';
                          }

                          const handleMouseDown = (e) => {
                            dragPosRef.current = { x: e.clientX, y: e.clientY };
                          };

                          const handleCellClick = (e) => {
                            if (isNull) return;
                            // 如果发生明显拖拽（调整大小或划选文本），则不触发收回切换
                            const dx = Math.abs(e.clientX - dragPosRef.current.x);
                            const dy = Math.abs(e.clientY - dragPosRef.current.y);
                            if (dx > 5 || dy > 5) return;
                            setExpandedCell(prev => prev === cellKey ? null : cellKey);
                          };

                          return (
                            <td 
                              key={col} 
                              style={{ 
                                padding: '8px 12px', 
                                minWidth: isExpanded ? '380px' : (col === 'id' ? '50px' : '100px'),
                                maxWidth: isExpanded ? '850px' : '280px',
                                verticalAlign: 'top',
                                transition: 'all 0.2s ease'
                              }}
                            >
                              <div 
                                className={`db-table-cell ${isExpanded ? 'db-cell-expanded' : 'db-cell-compact'}`}
                                onMouseDown={handleMouseDown}
                                onClick={handleCellClick}
                                title={isExpanded ? '点击缩回紧凑视图（右下角 ◢ 可自由拖拽拉伸）' : (isNull ? '空值 (NULL)' : (isLong ? '点击原地缩放展开查看全文' : '点击缩放查看'))}
                                style={{
                                  minWidth: isExpanded ? '360px' : 'auto',
                                  maxWidth: isExpanded ? '850px' : '280px',
                                  maxHeight: isExpanded ? '400px' : '52px',
                                  resize: isExpanded ? 'both' : 'none',
                                  overflow: isExpanded ? 'auto' : 'hidden',
                                  wordBreak: 'break-all',
                                  whiteSpace: isExpanded ? 'pre-wrap' : 'normal',
                                  color: isNull ? 'var(--text-secondary)' : 'var(--text-primary)',
                                  fontStyle: isNull ? 'italic' : 'normal',
                                  cursor: isNull ? 'default' : 'pointer',
                                  padding: isExpanded ? '10px 14px' : '4px 6px',
                                  borderRadius: '4px',
                                  fontSize: isExpanded ? '12px' : '13px',
                                  lineHeight: isExpanded ? '1.6' : '1.4',
                                  fontFamily: isExpanded ? 'var(--font-mono, Consolas, Monaco, monospace)' : 'inherit',
                                  userSelect: isExpanded ? 'text' : 'none'
                                }}
                              >
                                {displayText}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                    {tableData.data.length === 0 && !loading && (
                      <tr>
                        <td colSpan={tableData.columns.length} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                          数据表为空
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-secondary)' }}>
                  {loading ? '加载中...' : '请在左侧选择数据表'}
                </div>
              )}
            </div>
            
            {/* Footer Pagination */}
            <div className="db-pagination-bar">
              <div className="db-pagination-info">
                <span>共 {totalCount} 条记录</span>
                {totalCount > 0 && (
                  <span style={{ opacity: 0.8 }}>
                    (第 {startRow} - {endRow} 条)
                  </span>
                )}
              </div>

              <div className="db-pagination-controls">
                <select 
                  className="db-pagination-select"
                  value={pageSize}
                  onChange={handlePageSizeChange}
                  disabled={loading}
                  aria-label="每页显示条数"
                >
                  <option value={50}>50 条/页</option>
                  <option value={100}>100 条/页</option>
                  <option value={200}>200 条/页</option>
                </select>

                <button 
                  type="button"
                  className="db-pagination-btn"
                  onClick={handlePrevPage}
                  disabled={currentPage <= 1 || loading}
                  title="上一页"
                  aria-label="上一页"
                >
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                    <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
                  </svg>
                  <span>上一页</span>
                </button>

                <div className="db-pagination-page-indicator">
                  第 <strong>{currentPage}</strong> / {totalPages} 页
                </div>

                <button 
                  type="button"
                  className="db-pagination-btn"
                  onClick={handleNextPage}
                  disabled={currentPage >= totalPages || loading}
                  title="下一页"
                  aria-label="下一页"
                >
                  <span>下一页</span>
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                    <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z"/>
                  </svg>
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
