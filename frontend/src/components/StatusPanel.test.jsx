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

    // 断言封印遮罩渲染
    expect(screen.getByText(/任务设立中，知识库被封印/)).toBeInTheDocument();

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

});
