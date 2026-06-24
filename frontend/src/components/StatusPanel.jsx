import React, { useState } from 'react';

export default function StatusPanel({
  currentThought,
  affection,
  personaType,
  handlePersonaTypeChange,
  models,
  activeModel,
  handleModelChange,
  activeSubModel,
  mission,
  knowledgeTree,
  onFileClick
}) {

  // 解析好感度对应的文字状态（隐藏数值）
  const getAffectionText = (val) => {
    if (val >= 90) return '生死相许 (不分彼此)';
    if (val >= 75) return '情深意切 (全然交付)';
    if (val >= 50) return '心有灵犀 (心动偏爱)';
    if (val >= 25) return '眉目传情 (初有好感)';
    return '若即若离 (冷静防备)';
  };

  const [expandedCategories, setExpandedCategories] = useState(() => {
    const saved = localStorage.getItem('statusPanelExpanded');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {}
    }
    return {
      Lessons: false,
      LDRs: false,
      References: false,
      Settings: false
    };
  });

  const toggleCategory = (cat) => {
    setExpandedCategories(prev => {
      const next = { ...prev, [cat]: !prev[cat] };
      localStorage.setItem('statusPanelExpanded', JSON.stringify(next));
      return next;
    });
  };

  const isDrafting = mission?.is_drafting;

  return (
    <section className="ide-panel right-panel custom-scrollbar" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', overflowX: 'hidden' }}>
      
      {/* 区块 1: 导师与授课状态 */}
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '6px' }}>
            <path fillRule="evenodd" clipRule="evenodd" d="M8 1.54L1 4.88v1.37l.86.41v4.83l.25.32 5.56 2.65h.66l5.56-2.65.25-.32V6.66l.86-.41V4.88L8 1.54zm5.14 5.58L8 9.56 2.86 7.12v4.29l5.14 2.45 5.14-2.45V7.12zM8 2.66l5.22 2.5L8 7.66 2.78 5.16 8 2.66z" />
          </svg>
          <span>导师与授课状态</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', marginRight: '14px', marginTop: '2px' }}>
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '2px 10px',
              height: '24px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: '12px',
              border: '1px solid var(--border-color)',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              outline: 'none',
              boxSizing: 'border-box'
            }}
            title="选择导师 (暂未开放)"
          >
            媚吻锋
          </button>
          <button
            onClick={() => handlePersonaTypeChange(personaType === 'original' ? 'simplified' : 'original')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '2px 10px',
              height: '24px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: '12px',
              border: '1px solid var(--border-color)',
              background: personaType === 'simplified' ? 'var(--accent-pink)' : 'transparent',
              color: personaType === 'simplified' ? 'white' : 'var(--text-primary)',
              cursor: 'pointer',
              transition: 'all 0.2s',
              outline: 'none',
              boxSizing: 'border-box'
            }}
            title="点击切换导师人设类型（蓝色为精简版，透明为原版）"
          >
            {personaType === 'simplified' ? '精简' : '原版'}
          </button>
        </div>
      </div>

      <div className="right-content" style={{ flex: 'none', padding: '12px 16px 12px 16px', flexShrink: 0, gap: '6px' }}>
        <div className="character-widget" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div className="thought-box" style={{ padding: '12px 16px' }}>
            <div className="thought-header" style={{ marginBottom: '4px' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 17h6a6 6 0 1 0-3-11.2A6.5 6.5 0 0 0 4 12.5 5 5 0 0 0 9 17Z" />
                <circle cx="6" cy="20" r="1.5" stroke="none" fill="currentColor" />
                <circle cx="3" cy="22" r="1" stroke="none" fill="currentColor" />
              </svg>
              此刻内心
            </div>
            {currentThought}
          </div>
          <div className="character-details" style={{ paddingLeft: '8px' }}>
            <div className="character-role" style={{ fontSize: '12px' }}>当前目标：{mission?.current_mission !== "未知目标" ? "执行修行中" : "自由探索中"}</div>
            <div style={{ marginTop: '4px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              当前态度：<span style={{ color: 'var(--accent-pink)', fontWeight: '600' }}>{getAffectionText(affection)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 区块 2: 学习任务与资料 */}
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px', marginTop: '4px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
          </svg>
          <span>学习任务与资料</span>
        </div>
      </div>

      <div className="right-content" style={{ flex: '1 0 40%', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'visible', padding: '0 16px 0 16px' }}>
        {/* 草稿期间的视觉压制遮罩 */}
        {isDrafting && (
          <div style={{
            position: 'absolute',
            top: '4px', left: 0, right: 0, bottom: '10px',
            background: 'rgba(var(--bg-panel-rgb, 30,30,30), 0.7)',
            backdropFilter: 'blur(2px)',
            zIndex: 5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            fontWeight: 'bold',
            flexDirection: 'column',
            gap: '10px',
            textAlign: 'center',
            padding: '20px',
            borderRadius: '8px'
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent-pink)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            <span>任务设立中，知识库被封印。<br/>(等待签订契约)</span>
          </div>
        )}

        <div className="knowledge-tree" style={{ 
          flex: 1,
          filter: isDrafting ? 'blur(1px) grayscale(1)' : 'none',
          background: 'var(--bg-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          padding: '12px',
          margin: '0 0 10px 0',
          boxShadow: '0 2px 6px rgba(0,0,0,0.02)'
        }}>
          {knowledgeTree && knowledgeTree.length > 0 ? (
            knowledgeTree.map((catNode) => (
              <div key={catNode.category} style={{ marginBottom: '8px' }}>
                <div 
                  onClick={() => toggleCategory(catNode.category)}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    cursor: 'pointer', 
                    fontWeight: '600', 
                    color: 'var(--text-primary)',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    background: expandedCategories[catNode.category] ? 'var(--bg-hover)' : 'transparent',
                    userSelect: 'none',
                    transition: 'background 0.2s'
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                  onMouseLeave={e => { if(!expandedCategories[catNode.category]) e.currentTarget.style.background = 'transparent' }}
                >
                  <svg 
                    width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" 
                    style={{ 
                      marginRight: '8px', 
                      transform: expandedCategories[catNode.category] ? 'rotate(90deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                      color: 'var(--text-secondary)'
                    }}
                  >
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', color: 'var(--accent-pink)' }}>
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                  </svg>
                  <span style={{ flex: 1, fontSize: '13px' }}>{catNode.category}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: '10px' }}>
                    {catNode.files.length}
                  </span>
                </div>
                
                <div style={{
                  overflow: 'hidden',
                  transition: 'max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s',
                  maxHeight: expandedCategories[catNode.category] ? '500px' : '0',
                  opacity: expandedCategories[catNode.category] ? 1 : 0
                }}>
                  <ul style={{ listStyle: 'none', paddingLeft: '34px', margin: '4px 0 8px 0', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    {catNode.files.length > 0 ? (
                      catNode.files.map(f => (
                        <li 
                          key={f.path} 
                          onClick={() => !isDrafting && onFileClick && onFileClick(f.path)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            padding: '6px 8px',
                            cursor: isDrafting ? 'not-allowed' : 'pointer',
                            color: 'var(--text-secondary)',
                            fontSize: '12px',
                            borderRadius: '4px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            transition: 'all 0.15s'
                          }}
                          onMouseEnter={(e) => {
                            if(!isDrafting) {
                              e.currentTarget.style.background = 'var(--bg-hover)';
                              e.currentTarget.style.color = 'var(--text-primary)';
                              e.currentTarget.style.transform = 'translateX(4px)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if(!isDrafting) {
                              e.currentTarget.style.background = 'transparent';
                              e.currentTarget.style.color = 'var(--text-secondary)';
                              e.currentTarget.style.transform = 'translateX(0)';
                            }
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px', minWidth: '12px', opacity: 0.6 }}>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                            <line x1="16" y1="13" x2="8" y2="13"></line>
                            <line x1="16" y1="17" x2="8" y2="17"></line>
                            <polyline points="10 9 9 9 8 9"></polyline>
                          </svg>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{f.name}</span>
                        </li>
                      ))
                    ) : (
                      <li style={{ padding: '6px 8px', color: 'var(--text-muted)', fontSize: '11px', fontStyle: 'italic', display: 'flex', alignItems: 'center' }}>
                        <span style={{ width: '12px', marginRight: '6px' }} />
                        暂无档案
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', padding: '20px 0' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ margin: '0 auto 8px auto', display: 'block', opacity: 0.5 }}>
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              暂无物理文件缓存
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
