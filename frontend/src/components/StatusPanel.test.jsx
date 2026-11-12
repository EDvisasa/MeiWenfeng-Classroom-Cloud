import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import StatusPanel from './StatusPanel';

describe('StatusPanel Behavior Tests (ISSUE-56 Phase 1)', () => {

  const defaultProps = {
    currentThought: 'Thinking deeply...',
    affection: 80,
    personaType: 'simplified',
    handlePersonaTypeChange: vi.fn(),
    atmosphereMode: 'daily',
    handleAtmosphereModeChange: vi.fn(),
    models: [],
    activeModel: 'DeepSeek',
    handleModelChange: vi.fn(),
    activeSubModel: '',
    mission: { current_mission: 'Learn TDD In Depth', is_drafting: false },
    autoSummarize: true,
    onToggleAutoSummarize: vi.fn(),
    memoryStatus: {
      uncompacted_count: 2,
      threshold: 3,
      total_diaries: 5,
      recent_diaries: [
        { id: 101, timestamp: '2026-11-12 18:00:00', summary: '这是第一篇关于TDD的浓缩日记。', level: 1 },
        { id: 100, timestamp: '2026-11-11 12:00:00', summary: '这是第二篇关于架构设计的浓缩日记。', level: 1 }
      ]
    },
    onSummarizeMemory: vi.fn(),
    isSummarizingMemory: false,
    onOpenDatabaseViewer: vi.fn()
  };

  it('行为1：区块双核心渲染验证 (Renders two core sections: Persona & Memory Cognition)', () => {
    render(<StatusPanel {...defaultProps} />);
    
    // 断言导师状态区块标题与记忆中枢标题存在
    expect(screen.getByText('导师与授课状态')).toBeInTheDocument();
    expect(screen.getByText('记忆与学情沉淀')).toBeInTheDocument();
    
    // 断言内心想法与态度渲染
    expect(screen.getByText('此刻内心')).toBeInTheDocument();
    expect(screen.getByText('Thinking deeply...')).toBeInTheDocument();
    expect(screen.getByText('情深意切 (全然交付)')).toBeInTheDocument();
  });

  it('行为2：课题卡片拟定期（草稿锁定）与正常期状态切换 (Mission card drafting lock & active state)', () => {
    // 正常期
    const { rerender } = render(<StatusPanel {...defaultProps} />);
    expect(screen.getByText('课题执行中')).toBeInTheDocument();
    expect(screen.getByText('Learn TDD In Depth')).toBeInTheDocument();

    // 拟定期（草稿锁定）
    const draftProps = {
      ...defaultProps,
      mission: { current_mission: '制定新阶段计划', is_drafting: true }
    };
    rerender(<StatusPanel {...draftProps} />);
    expect(screen.getByText('目标拟定中 · 锁定')).toBeInTheDocument();
    expect(screen.getByText(/当前正在拟定学习计划/)).toBeInTheDocument();
  });

  it('行为3：自动/手动整理胶囊切换与回调 (Auto/Manual summarization toggle)', () => {
    const onToggleAutoSummarize = vi.fn();
    const { rerender } = render(
      <StatusPanel {...defaultProps} autoSummarize={true} onToggleAutoSummarize={onToggleAutoSummarize} />
    );

    const autoBtn = screen.getByText('自动整理');
    expect(autoBtn).toBeInTheDocument();
    expect(screen.getByText(/自动模式：满 3 篇自动触发后台浓缩/)).toBeInTheDocument();

    fireEvent.click(autoBtn);
    expect(onToggleAutoSummarize).toHaveBeenCalledTimes(1);

    // 切为手动模式
    rerender(
      <StatusPanel {...defaultProps} autoSummarize={false} onToggleAutoSummarize={onToggleAutoSummarize} />
    );
    expect(screen.getByText('手动整理')).toBeInTheDocument();
    expect(screen.getByText(/手动模式：已暂停自动触发，原始记录静默累加中/)).toBeInTheDocument();
  });

  it('行为4：未归档进度条与一键立即归档按钮状态 (Progress bar & manual archive action)', () => {
    const onSummarizeMemory = vi.fn();
    const { rerender } = render(
      <StatusPanel {...defaultProps} onSummarizeMemory={onSummarizeMemory} />
    );

    // 进度计数
    expect(screen.getByText('2 / 3 篇')).toBeInTheDocument();

    // 立即归档按钮可点击
    const archiveBtn = screen.getByText('立即归档');
    expect(archiveBtn).not.toBeDisabled();
    fireEvent.click(archiveBtn);
    expect(onSummarizeMemory).toHaveBeenCalledTimes(1);

    // 归档进行中 (Loading) 状态
    rerender(
      <StatusPanel {...defaultProps} isSummarizingMemory={true} />
    );
    const loadingBtn = screen.getByText('正在整理中...');
    expect(loadingBtn).toBeDisabled();

    // 未归档为 0 时禁用
    rerender(
      <StatusPanel
        {...defaultProps}
        memoryStatus={{ ...defaultProps.memoryStatus, uncompacted_count: 0 }}
      />
    );
    expect(screen.getByText('立即归档')).toBeDisabled();
  });

  it('行为5：近期浓缩日记时间轴渲染与折叠交互 (Recent diaries timeline & expand toggle)', () => {
    render(<StatusPanel {...defaultProps} />);

    expect(screen.getByText('近期浓缩日记')).toBeInTheDocument();
    expect(screen.getByText('共 5 篇')).toBeInTheDocument();
    expect(screen.getAllByText('L1 纪要')).toHaveLength(2);
    expect(screen.getByText(/这是第一篇关于TDD的浓缩日记/)).toBeInTheDocument();
    expect(screen.getByText(/这是第二篇关于架构设计的浓缩日记/)).toBeInTheDocument();
  });

  it('行为6：暂无日记时的优雅空状态 (Empty diaries state)', () => {
    render(
      <StatusPanel
        {...defaultProps}
        memoryStatus={{ uncompacted_count: 0, threshold: 3, total_diaries: 0, recent_diaries: [] }}
      />
    );

    expect(screen.getByText(/暂无已归档日记/)).toBeInTheDocument();
  });

  it('行为7：底部查看底层数据库快捷入口 (Database viewer link)', () => {
    const onOpenDatabaseViewer = vi.fn();
    render(<StatusPanel {...defaultProps} onOpenDatabaseViewer={onOpenDatabaseViewer} />);

    const dbLink = screen.getByText('查看完整 memory_logs 数据表');
    expect(dbLink).toBeInTheDocument();
    fireEvent.click(dbLink);
    expect(onOpenDatabaseViewer).toHaveBeenCalledWith('memory_logs');
  });

  it('行为8：顶部胶囊按钮强制单行不折行 (Header pills never wrap)', () => {
    render(<StatusPanel {...defaultProps} />);

    const pills = ['媚吻锋', '精简', '生活'].map((label) => screen.getByText(label));
    pills.forEach((pill) => {
      const btn = pill.closest('button');
      expect(btn).not.toBeNull();
      expect(btn.style.whiteSpace).toBe('nowrap');
      expect(btn.style.flexShrink).toBe('0');
    });
  });

  it('行为9：零 Emoji 原则全面审计 (Zero Emoji across component)', () => {
    const { container } = render(<StatusPanel {...defaultProps} />);
    const emojiRegex = /\p{Extended_Pictographic}/u;
    expect(container.textContent).not.toMatch(emojiRegex);
  });

  it('行为10：Markdown 格式的 Mission 文本智能解码与结构化展开 (Decodes raw markdown mission into clean Goal and expandable meta details)', () => {
    const rawMarkdownMission = `# Mission Objective\n\n**Goal**: 捋顺OpenAI关于Navier-Stokes方程有限时间爆破论文的核心逻辑\n\n**Time Budget**: 每日1小时\n\n**Constraints**: 零预算、不看视频教程、以放松探索为主\n\n**Verified Skill Level**: 大学高数/线代基础，微积分尚可，但散度与矩阵运动学概念已生锈`;

    render(
      <StatusPanel
        {...defaultProps}
        mission={{ current_mission: rawMarkdownMission, is_drafting: false }}
      />
    );

    // 断言不直接暴露原始 Markdown 标签 '# Mission Objective' 或 '**Goal**:'
    expect(screen.queryByText(/# Mission Objective/)).not.toBeInTheDocument();
    expect(screen.queryByText(/\*\*Goal\*\*/)).not.toBeInTheDocument();

    // 断言解码后的目标文本清晰显示
    expect(screen.getByText('捋顺OpenAI关于Navier-Stokes方程有限时间爆破论文的核心逻辑')).toBeInTheDocument();
    // 断言时间预算 Chip 胶囊正常展示
    expect(screen.getByText('每日1小时')).toBeInTheDocument();

    // 点击展开约束与基础
    const expandBtn = screen.getByText('查看约束与基准水平');
    expect(expandBtn).toBeInTheDocument();
    fireEvent.click(expandBtn);

    // 展开后应能看到约束与基础
    expect(screen.getByText('零预算、不看视频教程、以放松探索为主')).toBeInTheDocument();
    expect(screen.getByText(/大学高数\/线代基础/)).toBeInTheDocument();
  });

});
