import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi } from 'vitest';
import StatusPanel from './StatusPanel';

describe('StatusPanel Behavior Tests', () => {

  const mockKnowledgeTree = [
    {
      category: 'Lessons',
      files: [
        { name: '测试文档.md', path: 'Lessons/测试文档.md' }
      ]
    }
  ];

  const defaultProps = {
    currentThought: 'Thinking...',
    affection: 80,
    personaType: 'simplified',
    handlePersonaTypeChange: vi.fn(),
    models: [],
    activeModel: 'DeepSeek',
    handleModelChange: vi.fn(),
    activeSubModel: '',
    mission: { current_mission: 'Learn TDD', is_drafting: false },
    knowledgeTree: mockKnowledgeTree,
    onFileClick: vi.fn()
  };

  it('行为1：区块剥离渲染验证 (Renders two core sections)', () => {
    render(<StatusPanel {...defaultProps} />);
    
    // 断言导师状态区块标题存在
    expect(screen.getByText('导师与授课状态')).toBeInTheDocument();
    // 断言学习资料区块标题存在
    expect(screen.getByText('学习任务与资料')).toBeInTheDocument();
    
    // 断言节点存在
    expect(screen.getByText('Lessons')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('测试文档.md')).toBeInTheDocument();
  });

  it('行为2：拷问模式（草稿）防抖与封锁机制 (Drafting mode blocks clicks and shows overlay)', () => {
    const draftProps = {
      ...defaultProps,
      mission: { current_mission: 'Unknown', is_drafting: true },
      onFileClick: vi.fn()
    };
    render(<StatusPanel {...draftProps} />);

    // 断言锁定遮罩渲染
    expect(screen.getByText(/目标拟定中，知识库已锁定/)).toBeInTheDocument();

    // 点击文件，断言回调不被触发
    const fileNode = screen.getByText('测试文档.md');
    fireEvent.click(fileNode);
    expect(draftProps.onFileClick).not.toHaveBeenCalled();
  });

  it('行为3：正常模式（非草稿）的文件挂载穿透 (Normal mode triggers file click with path)', () => {
    render(<StatusPanel {...defaultProps} />);

    // 点击文件，断言回调触发且包含正确路径
    const fileNode = screen.getByText('测试文档.md');
    fireEvent.click(fileNode);
    expect(defaultProps.onFileClick).toHaveBeenCalledWith('Lessons/测试文档.md');
  });

  it('行为4：【生活/研学】氛围模式切换按钮渲染与点击回调 (Atmosphere mode toggle)', () => {
    const handleAtmosphereModeChange = vi.fn();
    const { rerender } = render(
      <StatusPanel
        {...defaultProps}
        atmosphereMode="daily"
        handleAtmosphereModeChange={handleAtmosphereModeChange}
      />
    );

    // 生活模式下渲染“生活”按钮
    const dailyBtn = screen.getByText('生活');
    expect(dailyBtn).toBeInTheDocument();
    fireEvent.click(dailyBtn);
    expect(handleAtmosphereModeChange).toHaveBeenCalledWith('study');

    // 研学模式下渲染“研学”按钮
    rerender(
      <StatusPanel
        {...defaultProps}
        atmosphereMode="study"
        handleAtmosphereModeChange={handleAtmosphereModeChange}
      />
    );
    const studyBtn = screen.getByText('研学');
    expect(studyBtn).toBeInTheDocument();
    fireEvent.click(studyBtn);
    expect(handleAtmosphereModeChange).toHaveBeenCalledWith('daily');
  });

  it('行为5：顶部三个胶囊按钮强制单行，绝不换行挤压 (Header pills never wrap)', () => {
    render(<StatusPanel {...defaultProps} />);

    // "媚吻锋" 三字按钮一旦被挤压就会折成「媚吻 / 锋」，这是本次 UI 缺陷的形态
    const pills = ['媚吻锋', '精简', '生活'].map((label) => screen.getByText(label));

    pills.forEach((pill) => {
      const btn = pill.closest('button');
      expect(btn).not.toBeNull();
      expect(btn.style.whiteSpace).toBe('nowrap');
      expect(btn.style.flexShrink).toBe('0');
    });

    // 按钮容器不得再叠加多余右外边距，避免与 panel-header 的内边距双重挤压
    const group = pills[0].closest('button').parentElement;
    expect(group.style.marginRight).toBe('');
  });

  it('行为6：区块标题单行展示，不折成两行 (Section title stays on one line)', () => {
    render(<StatusPanel {...defaultProps} />);

    const title = screen.getByText('导师与授课状态');
    const wrapper = title.parentElement;
    expect(wrapper.style.whiteSpace).toBe('nowrap');
    expect(wrapper.style.overflow).toBe('hidden');
  });

});
