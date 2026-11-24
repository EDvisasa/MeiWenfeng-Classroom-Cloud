import React, { useState } from 'react';

// 解析 Markdown 格式的 Mission 文本为易于界面优雅排版的结构化数据
export function parseMissionObjective(mission) {
  if (!mission) {
    return {
      isUnknown: true,
      goal: '自由探索中 (未指定长期课题)',
      timeBudget: '',
      constraints: '',
      skillLevel: ''
    };
  }

  // 优先采用后端直接解析并返回的结构化字段
  if (mission.parsed_goal && mission.parsed_goal !== '未知目标') {
    return {
      isUnknown: false,
      goal: mission.parsed_goal,
      timeBudget: mission.time_budget || '',
      constraints: mission.constraints || '',
      skillLevel: mission.skill_level || ''
    };
  }

  const raw = mission.current_mission || '';
  if (!raw || raw === '未知目标') {
    return {
      isUnknown: true,
      goal: '自由探索中 (未指定长期课题)',
      timeBudget: '',
      constraints: '',
      skillLevel: ''
    };
  }

  // 正则提取标准 4 要素（Matt Pocock 模板）
  const goalMatch = raw.match(/\*\*Goal\*\*:\s*([^\n\r]+)/i);
  const timeMatch = raw.match(/\*\*Time Budget\*\*:\s*([^\n\r]+)/i);
  const constraintsMatch = raw.match(/\*\*Constraints\*\*:\s*([^\n\r]+)/i);
  const skillMatch = raw.match(/\*\*Verified Skill Level\*\*:\s*([^\n\r]+)/i);

  if (goalMatch) {
    return {
      isUnknown: false,
      goal: goalMatch[1].trim(),
      timeBudget: timeMatch ? timeMatch[1].trim() : '',
      constraints: constraintsMatch ? constraintsMatch[1].trim() : '',
      skillLevel: skillMatch ? skillMatch[1].trim() : ''
    };
  }

  // 兜底清洗：剥离 Markdown 标题符 (#) 与加粗符 (**)
  let cleaned = raw
    .replace(/^#+\s+/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .trim();

  return {
    isUnknown: false,
    goal: cleaned || '自由探索中',
    timeBudget: '',
    constraints: '',
    skillLevel: ''
  };
}

export default function StatusPanel({
  currentThought,
  affection,
  personaType,
  handlePersonaTypeChange,
  atmosphereMode = 'daily',
  handleAtmosphereModeChange,
  models,
  activeModel,
  handleModelChange,
  activeSubModel,
  mission,
  knowledgeTree,
  courses = [],
  selectedCourseId = 'default',
  activeCourseId = 'default',
  isInLesson = false,
  onSelectCourse,
  onFileClick,
  autoSummarize = true,
  onToggleAutoSummarize,
  memoryStatus = { uncompacted_count: 0, threshold: 10, total_diaries: 0, recent_diaries: [] },
  onSummarizeMemory,
  isSummarizingMemory = false,
  onOpenDatabaseViewer
}) {
  const [expandedDiaries, setExpandedDiaries] = useState({});
  const [showMissionDetails, setShowMissionDetails] = useState(false);
  const [showCoursePicker, setShowCoursePicker] = useState(false);
  const canSwitchCourse = !mission?.is_drafting && !isInLesson;

  React.useEffect(() => {
    if (!canSwitchCourse && showCoursePicker) {
      setShowCoursePicker(false);
    }
  }, [canSwitchCourse, showCoursePicker]);

  // 解析好感度对应的文字状态（隐藏数值）
  const getAffectionText = (val) => {
    if (val >= 90) return '生死相许 (不分彼此)';
    if (val >= 75) return '情深意切 (全然交付)';
    if (val >= 50) return '心有灵犀 (心动偏爱)';
    if (val >= 25) return '眉目传情 (初有好感)';
    return '若即若离 (冷静防备)';
  };

  const toggleDiaryExpand = (id) => {
    setExpandedDiaries((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const isDrafting = Boolean(mission?.is_drafting);
  const parsedMission = parseMissionObjective(mission);
  const uncompactedCount = memoryStatus?.uncompacted_count ?? 0;
  const threshold = memoryStatus?.threshold ?? 10;
  const totalDiaries = memoryStatus?.total_diaries ?? 0;
  const recentDiaries = memoryStatus?.recent_diaries ?? [];

  const progressPercent = Math.min(100, Math.round((uncompactedCount / (threshold || 10)) * 100));

  // 人设 / 氛围 / 整理切换胶囊按钮：统一视觉并强制单行不换行，避免面板变窄时被挤成两行
  const pillStyle = ({ active, muted = false } = {}) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '0 10px',
    height: '24px',
    fontSize: '12px',
    fontWeight: 600,
    lineHeight: 1,
    whiteSpace: 'nowrap',
    flexShrink: 0,
    borderRadius: '12px',
    border: '1px solid var(--border-color)',
    background: muted ? 'var(--bg-primary)' : (active ? 'var(--accent-pink)' : 'transparent'),
    color: muted || !active ? 'var(--text-primary)' : 'white',
    cursor: 'pointer',
    transition: 'all 0.2s',
    outline: 'none',
    boxSizing: 'border-box'
  });

  return (
    <section className="ide-panel right-panel custom-scrollbar" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', overflowX: 'hidden' }}>
      
      {/* 区块 1: 导师与授课状态 */}
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', minWidth: 0, flexShrink: 1, whiteSpace: 'nowrap', overflow: 'hidden' }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '6px' }}>
            <path fillRule="evenodd" clipRule="evenodd" d="M8 1.54L1 4.88v1.37l.86.41v4.83l.25.32 5.56 2.65h.66l5.56-2.65.25-.32V6.66l.86-.41V4.88L8 1.54zm5.14 5.58L8 9.56 2.86 7.12v4.29l5.14 2.45 5.14-2.45V7.12zM8 2.66l5.22 2.5L8 7.66 2.78 5.16 8 2.66z" />
          </svg>
          <span>导师与授课状态</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
          <button
            style={pillStyle({ muted: true })}
            title="选择导师 (暂未开放)"
          >
            媚吻锋
          </button>
          <button
            onClick={() => handlePersonaTypeChange && handlePersonaTypeChange(personaType === 'original' ? 'simplified' : 'original')}
            style={pillStyle({ active: personaType === 'simplified' })}
            title="点击切换导师人设类型（粉色为精简版，透明为原版）"
          >
            {personaType === 'simplified' ? '精简' : '原版'}
          </button>
          <button
            onClick={() => handleAtmosphereModeChange && handleAtmosphereModeChange(atmosphereMode === 'daily' ? 'study' : 'daily')}
            style={pillStyle({ active: atmosphereMode === 'study' })}
            title="点击切换氛围模式（粉色为研学，透明为生活）"
          >
            {atmosphereMode === 'study' ? '研学' : '生活'}
          </button>
        </div>
      </div>

      <div className="right-content" style={{ flex: 'none', padding: '12px 16px 12px 16px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div className="character-widget" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div className="thought-box">
            <div className="thought-header">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 17h6a6 6 0 1 0-3-11.2A6.5 6.5 0 0 0 4 12.5 5 5 0 0 0 9 17Z" />
                <circle cx="6" cy="20" r="1.5" stroke="none" fill="currentColor" />
                <circle cx="3" cy="22" r="1" stroke="none" fill="currentColor" />
              </svg>
              此刻内心
            </div>
            <div className="thought-content">
              {currentThought}
            </div>
          </div>
          <div className="character-details" style={{ paddingLeft: '8px' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              当前态度：<span style={{ color: 'var(--accent-pink)', fontWeight: '600' }}>{getAffectionText(affection)}</span>
            </div>
          </div>
        </div>

        {/* 当前学习课题卡片 */}
        {(() => {
          const currentCourseSelection = (isInLesson ? activeCourseId : selectedCourseId) || 'default';
          const customCourses = (Array.isArray(courses) ? courses : []).filter(
            (c) => c && c.id !== 'default' && !c.is_default
          );
          const courseList = [...customCourses];
          if (
            currentCourseSelection &&
            currentCourseSelection !== 'default' &&
            !courseList.some((c) => c && c.id === currentCourseSelection)
          ) {
            courseList.push({ id: currentCourseSelection, name: currentCourseSelection, is_default: false });
          }
          const canExpandCoursePicker = canSwitchCourse && courseList.length > 0;
          const selectedCourseObj =
            currentCourseSelection && currentCourseSelection !== 'default'
              ? courseList.find((c) => c.id === currentCourseSelection)
              : null;

          return (
            <div
              className={`mission-card ${isDrafting ? 'mission-card-drafting' : ''} ${canExpandCoursePicker ? 'mission-card-interactive' : ''} ${showCoursePicker && canExpandCoursePicker ? 'mission-card-expanded' : ''}`}
            >
              <div
                className={`mission-card-trigger ${canExpandCoursePicker ? 'clickable' : ''}`}
                role={canExpandCoursePicker ? 'button' : undefined}
                tabIndex={canExpandCoursePicker ? 0 : undefined}
                aria-expanded={canExpandCoursePicker ? showCoursePicker : undefined}
                aria-label={canExpandCoursePicker ? '点击展开或收起学习课题列表' : undefined}
                onClick={() => {
                  if (canExpandCoursePicker) setShowCoursePicker((prev) => !prev);
                }}
                onKeyDown={(e) => {
                  if (canExpandCoursePicker && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    setShowCoursePicker((prev) => !prev);
                  }
                }}
                title={
                  isInLesson
                    ? '上课锁定中，输入 /end_lesson 下课后可切换课题'
                    : canExpandCoursePicker
                      ? '点击卡片展开并切换当前待上课课题（下课后日常内容仍归档于全局日常记录文件（通用））'
                      : undefined
                }
              >
                <div className="mission-card-header">
                  {isDrafting ? (
                    <>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#ca8a04" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                      </svg>
                      <span className="mission-status-badge drafting">目标拟定中 · 锁定</span>
                    </>
                  ) : (
                    <>
                      {isInLesson ? (
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#0284c7" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        </svg>
                      ) : (
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                        </svg>
                      )}
                      <span className={`mission-status-badge ${isInLesson ? 'locked' : 'active'}`}>
                        {isInLesson ? '上课锁定中' : (!parsedMission.isUnknown ? '课题执行中' : '自由探索中')}
                      </span>
                      {(parsedMission.timeBudget || canExpandCoursePicker) && (
                        <div className="mission-card-header-right">
                          {parsedMission.timeBudget && (
                            <span className="mission-time-chip" title="每日学习时间预算">
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '3px' }}>
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                              </svg>
                              {parsedMission.timeBudget}
                            </span>
                          )}
                          {canExpandCoursePicker && (
                            <span className="mission-card-switch-hint">
                              <span>{showCoursePicker ? '收起' : '切换'}</span>
                              <svg
                                width="11"
                                height="11"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.3"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                style={{
                                  transform: showCoursePicker ? 'rotate(180deg)' : 'rotate(0deg)',
                                  transition: 'transform 0.2s ease'
                                }}
                              >
                                <polyline points="6 9 12 15 18 9"></polyline>
                              </svg>
                            </span>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>

                {!isDrafting && selectedCourseObj && (
                  <div className="mission-selected-course-name" title={selectedCourseObj.name || selectedCourseObj.id}>
                    {selectedCourseObj.name || selectedCourseObj.id}
                  </div>
                )}

                {/* 核心目标标题 */}
                <div className="mission-goal-title">
                  {parsedMission.goal}
                </div>
              </div>

              {showCoursePicker && canExpandCoursePicker && (
                <div className="mission-course-drawer" role="listbox" aria-label="选择学习课题">
                  {courseList.map((course) => {
                    const isSelected = course.id === currentCourseSelection;
                    return (
                      <button
                        key={course.id}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        className={`mission-course-option ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setShowCoursePicker(false);
                          if (onSelectCourse && course.id !== currentCourseSelection) {
                            onSelectCourse(course.id);
                          }
                        }}
                      >
                        <span className="mission-course-option-name">{course.name || course.id}</span>
                        {isSelected && (
                          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" className="mission-course-option-check">
                            <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
                          </svg>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

          {isDrafting ? (
            <div className="mission-draft-tip">
              当前正在拟定学习计划，输入框将定向进行需求拷问，完成后自动固化。
            </div>
          ) : (
            (parsedMission.constraints || parsedMission.skillLevel) && (
              <div className="mission-details-wrapper">
                <button
                  type="button"
                  className="mission-expand-toggle"
                  onClick={() => setShowMissionDetails(!showMissionDetails)}
                >
                  <svg
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    style={{
                      transform: showMissionDetails ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.2s',
                      marginRight: '4px'
                    }}
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                  {showMissionDetails ? '收起规划详情' : '查看约束与基准水平'}
                </button>

                {showMissionDetails && (
                  <div className="mission-meta-list">
                    {parsedMission.constraints && (
                      <div className="mission-meta-item">
                        <span className="mission-meta-label">约束条件:</span>
                        <span className="mission-meta-val">{parsedMission.constraints}</span>
                      </div>
                    )}
                    {parsedMission.skillLevel && (
                      <div className="mission-meta-item">
                        <span className="mission-meta-label">当前基础:</span>
                        <span className="mission-meta-val">{parsedMission.skillLevel}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          )}
            </div>
          );
        })()}
      </div>

      {/* 区块 2: 记忆与学情沉淀 */}
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px', marginTop: '4px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
          </svg>
          <span>记忆与学情沉淀</span>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
          <button
            onClick={() => onToggleAutoSummarize && onToggleAutoSummarize()}
            style={pillStyle({ active: autoSummarize })}
            title={autoSummarize ? `当前为自动整理模式（每满 ${threshold} 轮自动浓缩），点击切换为手动` : '当前为手动整理模式（静默累加），点击切回自动并立即追平'}
          >
            {autoSummarize ? '自动整理' : '手动整理'}
          </button>
        </div>
      </div>

      <div className="right-content" style={{ flex: '1 0 auto', display: 'flex', flexDirection: 'column', padding: '0 16px 16px 16px', gap: '10px' }}>
        <div className="memory-panel">
          
          {/* 未归档对话进度卡片 */}
          <div className="memory-progress-card">
            <div className="memory-progress-header">
              <span className="memory-progress-title">未归档对话</span>
              <span className="memory-progress-count">{uncompactedCount} / {threshold} 轮</span>
            </div>
            <div className="memory-progress-track">
              <div 
                className="memory-progress-fill" 
                style={{ width: `${progressPercent}%` }} 
              />
            </div>
            <div className="memory-progress-hint">
              {autoSummarize
                ? `自动模式：满 ${threshold} 轮对话自动触发后台浓缩`
                : '手动模式：已暂停自动触发，对话静默累加中'}
            </div>
            <button
              className="memory-archive-btn"
              onClick={() => onSummarizeMemory && onSummarizeMemory()}
              disabled={isSummarizingMemory || uncompactedCount === 0}
              title={uncompactedCount === 0 ? '暂无未归档对话' : '一键将当前未归档对话压缩为日记'}
            >
              {isSummarizingMemory ? '正在整理中...' : '立即归档'}
            </button>
          </div>

          {/* 最近浓缩日记时间轴 */}
          <div className="memory-diaries-section">
            <div className="memory-diaries-header">
              <span>近期浓缩日记</span>
              <span className="memory-diaries-badge">共 {totalDiaries} 篇</span>
            </div>

            {recentDiaries && recentDiaries.length > 0 ? (
              <div className="memory-diary-list">
                {recentDiaries.map((diary) => {
                  const isExpanded = expandedDiaries[diary.id];
                  const timeDisplay = diary.timestamp ? diary.timestamp.replace('T', ' ').slice(0, 16) : '';
                  const summaryText = diary.summary || '';
                  const shortSummary = summaryText.length > 70 && !isExpanded
                    ? summaryText.slice(0, 70) + '...'
                    : summaryText;

                  return (
                    <div key={diary.id} className="memory-diary-item">
                      <div 
                        className="memory-diary-header"
                        onClick={() => toggleDiaryExpand(diary.id)}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className="memory-diary-level-badge">L{diary.level || 1} 纪要</span>
                          <span className="memory-diary-time">{timeDisplay}</span>
                        </div>
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          style={{
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                            color: 'var(--text-muted)'
                          }}
                        >
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </div>
                      <div 
                        className="memory-diary-preview"
                        onClick={() => toggleDiaryExpand(diary.id)}
                        style={{ cursor: 'pointer' }}
                      >
                        {shortSummary}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="memory-empty-tip">
                暂无已归档日记<br/>(累计 {threshold} 轮对话后自动生成)
              </div>
            )}
          </div>

          {/* 底部查看数据库快捷入口 */}
          <div className="memory-panel-footer">
            <button
              className="memory-db-link"
              onClick={() => onOpenDatabaseViewer && onOpenDatabaseViewer('memory_logs')}
              title="查看底层 memory_logs 数据表"
            >
              <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: '5px' }}>
                <path d="M14 3c0 1.1-2.7 2-6 2S2 4.1 2 3s2.7-2 6-2 6 .9 6 2zm0 4c0 1.1-2.7 2-6 2S2 8.1 2 7V5c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm0 4c0 1.1-2.7 2-6 2S2 12.1 2 11V9c.8.6 2.3 1 4 1s3.2-.4 4-1v2zm-6 4c-3.3 0-6-.9-6-2v-2c.8.6 2.3 1 4 1s3.2-.4 4-1v2c0 1.1-2.7 2-6 2z" />
              </svg>
              查看完整 memory_logs 数据表
            </button>
          </div>

        </div>
      </div>
    </section>
  );
}
