import React from 'react';

export default function StatusPanel({
  currentThought,
  affection,
  personaType,
  handlePersonaTypeChange,
  models,
  activeModel,
  handleModelChange,
  activeSubModel,
  courseProgress
}) {

  // 解析好感度对应的文字状态（隐藏数值）
  const getAffectionText = (val) => {
    if (val >= 90) return '生死相许 (不分彼此)';
    if (val >= 75) return '情深意切 (全然交付)';
    if (val >= 50) return '心有灵犀 (心动偏爱)';
    if (val >= 25) return '眉目传情 (初有好感)';
    return '若即若离 (冷静防备)';
  };

  return (
    <section className="ide-panel right-panel">
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '6px' }}>
            <path fillRule="evenodd" clipRule="evenodd" d="M8 1.54L1 4.88v1.37l.86.41v4.83l.25.32 5.56 2.65h.66l5.56-2.65.25-.32V6.66l.86-.41V4.88L8 1.54zm5.14 5.58L8 9.56 2.86 7.12v4.29l5.14 2.45 5.14-2.45V7.12zM8 2.66l5.22 2.5L8 7.66 2.78 5.16 8 2.66z" />
          </svg>
          <span>导师与大纲状态</span>
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

      <div className="right-content">
        {/* 导师状态卡片 */}
        <div className="character-widget" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div className="thought-box">
            <div className="thought-header">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 17h6a6 6 0 1 0-3-11.2A6.5 6.5 0 0 0 4 12.5 5 5 0 0 0 9 17Z" />
                <circle cx="6" cy="20" r="1.5" stroke="none" fill="currentColor" />
                <circle cx="3" cy="22" r="1" stroke="none" fill="currentColor" />
              </svg>
              此刻内心
            </div>
            {currentThought}
          </div>
          <div className="character-details">
            <div className="character-role">授课状态：正在指导修行</div>
            <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              当前态度：<span style={{ color: 'var(--accent-pink)', fontWeight: '600' }}>{getAffectionText(affection)}</span>
            </div>
          </div>
        </div>




        {/* 课程进度面板 */}
        <div className="progress-widget">
          <div className="widget-title">修行进度表</div>
          <ul className="syllabus-list">
            {courseProgress.map((item) => (
              <li key={item.id} className={`syllabus-item ${item.status}`}>
                <div className="phase-tag">{item.phase}</div>
                <div className="topic-row">
                  <div className={`topic-status ${item.status}`} />
                  <span className="topic-title">{item.topic}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
