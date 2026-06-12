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
      <div className="panel-header">
        <span>⚙️ 导师与大纲状态</span>
      </div>

      <div className="right-content">
        {/* 导师状态卡片 */}
        <div className="character-widget">
          <div className="thought-box">
            {currentThought}
          </div>
          <div className="character-details">
            <div className="character-name">媚吻锋</div>
            <div className="character-role">授课状态：正在指导修行</div>
            <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              当前态度：<span style={{ color: 'var(--accent-pink)', fontWeight: '600' }}>{getAffectionText(affection)}</span>
            </div>
          </div>
        </div>

        {/* 导师人设切换 */}
        <div className="model-widget" style={{ marginTop: '14px' }}>
          <div className="widget-title">🎭 导师人设卡类型</div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
            <button
              onClick={() => handlePersonaTypeChange('simplified')}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '12px',
                borderRadius: '4px',
                border: '1px solid var(--border-color)',
                background: personaType === 'simplified' ? 'var(--accent-pink)' : 'var(--bg-secondary)',
                color: personaType === 'simplified' ? 'white' : 'var(--text-primary)',
                cursor: personaType === 'simplified' ? 'default' : 'pointer',
                fontWeight: 'bold',
                transition: 'all 0.2s ease'
              }}
            >
              精简人设
            </button>
            <button
              onClick={() => handlePersonaTypeChange('original')}
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '12px',
                borderRadius: '4px',
                border: '1px solid var(--border-color)',
                background: personaType === 'original' ? 'var(--accent-pink)' : 'var(--bg-secondary)',
                color: personaType === 'original' ? 'white' : 'var(--text-primary)',
                cursor: personaType === 'original' ? 'default' : 'pointer',
                fontWeight: 'bold',
                transition: 'all 0.2s ease'
              }}
            >
              原版人设
            </button>
          </div>
        </div>

        {/* 模型选择配置 */}
        <div className="model-widget">
          <div className="widget-title">⚙️ 切换大语言模型</div>
          <select 
            className="model-selector" 
            value={models.find(m => m.name === activeModel)?.id || ''}
            onChange={(e) => handleModelChange(e.target.value)}
          >
            {models.map(m => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.protocol.toUpperCase()})
              </option>
            ))}
          </select>
          {activeSubModel && (
            <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
              活动子模型: <span style={{ color: 'var(--accent-pink)', fontWeight: 'bold' }}>{activeSubModel}</span>
            </div>
          )}
        </div>


        {/* 课程进度面板 */}
        <div className="progress-widget">
          <div className="widget-title">📖 修行进度表</div>
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
