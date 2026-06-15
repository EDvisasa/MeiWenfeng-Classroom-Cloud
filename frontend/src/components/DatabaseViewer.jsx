import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';
export default function DatabaseViewer({ onClose }) {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState('');
  const [tableData, setTableData] = useState({ columns: [], data: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch list of tables on mount
  useEffect(() => {
    fetchTables();
  }, []);

  // Fetch table data when a table is selected
  useEffect(() => {
    if (selectedTable) {
      fetchTableData(selectedTable);
    } else {
      setTableData({ columns: [], data: [] });
    }
  }, [selectedTable]);

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

  const fetchTableData = async (tableName) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/chat/db/tables/${tableName}`);
      if (res.ok) {
        const data = await res.json();
        setTableData({ columns: data.columns || [], data: data.data || [] });
      } else {
        setError(`Failed to fetch data for ${tableName}`);
      }
    } catch (err) {
      setError(err.toString());
    } finally {
      setLoading(false);
    }
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
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '14px', fontWeight: 'bold' }}>{selectedTable || '请选择数据表'}</span>
              <button 
                onClick={() => selectedTable && fetchTableData(selectedTable)}
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
            <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
              {tableData.columns.length > 0 ? (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
                  <thead>
                    <tr>
                      {tableData.columns.map(col => (
                        <th key={col} style={{ padding: '8px 12px', borderBottom: '2px solid var(--border-color)', background: 'var(--bg-secondary)', position: 'sticky', top: 0, zIndex: 1 }}>
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.data.map((row, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        {tableData.columns.map(col => {
                          let cellValue = row[col];
                          if (typeof cellValue === 'object' && cellValue !== null) {
                            cellValue = JSON.stringify(cellValue);
                          }
                          // Truncate long text to prevent DOM freezing
                          let textStr = String(cellValue !== null ? cellValue : 'NULL');
                          if (textStr.length > 200) {
                            textStr = textStr.substring(0, 200) + '... (truncated, ' + textStr.length + ' chars)';
                          }
                          return (
                            <td key={col} style={{ padding: '8px 12px', maxWidth: '300px' }}>
                              <div style={{
                                maxHeight: '60px',
                                overflowY: 'auto',
                                wordBreak: 'break-all',
                                color: cellValue === null ? 'var(--text-secondary)' : 'var(--text-primary)',
                                fontStyle: cellValue === null ? 'italic' : 'normal'
                              }}>
                                {textStr}
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
            
            {/* Footer */}
            <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border-color)', fontSize: '11px', color: 'var(--text-secondary)', background: 'var(--bg-secondary)', textAlign: 'right' }}>
              共 {tableData.data.length} 条记录 (最多显示 200 条)
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
