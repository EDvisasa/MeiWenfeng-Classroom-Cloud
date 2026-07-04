import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatPanel from './ChatPanel';

// Mock heavy child components and utilities to isolate ChatPanel behavior
vi.mock('../utils/blockParser', () => ({
  parseAndMergeBlocks: vi.fn((blocksOrString) => {
    // Return dummy block to bypass complex rendering
    if (typeof blocksOrString === 'string') {
      return [{ type: 'text', text: blocksOrString }];
    }
    return blocksOrString;
  })
}));

vi.mock('./MissionProposalCard', () => ({
  default: () => <div data-testid="mission-card">Mission</div>
}));

vi.mock('./QuizBlock', () => ({
  default: () => <div data-testid="quiz-block">Quiz</div>
}));

vi.mock('react-markdown', () => ({
  default: ({ children }) => <div data-testid="react-markdown">{children}</div>
}));

vi.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }) => <div data-testid="syntax-highlighter">{children}</div>
}));

describe('ChatPanel Editing Behavior Tests', () => {
  const mockOnEditAndResend = vi.fn();
  const mockOnEditAiMessage = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const getBaseProps = () => ({
    theme: 'light',
    messages: [],
    models: [],
    activeModel: 'DeepSeek',
    onEditAndResend: mockOnEditAndResend,
    onEditAiMessage: mockOnEditAiMessage,
    chatEndRef: { current: null },
    inputRef: { current: document.createElement('textarea') },
    inputText: '',
    handleInputChange: vi.fn(),
    handleKeyDown: vi.fn(),
    sendMessage: vi.fn(),
    stopGeneration: vi.fn(),
    isStreaming: false
  });

  it('TDD 1: Assistant message can be edited and saved (Raw Edit)', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          content: 'Hello, <think>I am testing</think>'
        }
      ]
    };

    render(<ChatPanel {...props} />);

    // 1. Enter edit mode
    // The assistant edit button has the 'raw-edit-btn' class and '查看并编辑原始流' title
    const rawEditBtn = screen.getByTitle('查看并编辑原始流');
    expect(rawEditBtn).toBeInTheDocument();
    
    fireEvent.click(rawEditBtn);

    // 2. Initial content is correct
    const textarea = document.querySelector('.edit-textarea');
    expect(textarea.value).toBe('Hello, <think>I am testing</think>');

    // 3. Cancel editing does not trigger callback
    fireEvent.change(textarea, { target: { value: 'Changed content' } });
    const cancelBtn = screen.getByText('取消');
    fireEvent.click(cancelBtn);

    expect(mockOnEditAiMessage).not.toHaveBeenCalled();
    // Re-render means textarea should be gone (or not the edit one)
    expect(screen.queryByText('保存修改')).not.toBeInTheDocument();

    // 4. Save modifications triggers callback
    fireEvent.click(screen.getByTitle('查看并编辑原始流'));
    const newTextarea = document.querySelector('.edit-textarea');
    fireEvent.change(newTextarea, { target: { value: 'Saved content' } });
    
    const saveBtn = screen.getByText('保存修改');
    fireEvent.click(saveBtn);

    expect(mockOnEditAiMessage).toHaveBeenCalledTimes(1);
    expect(mockOnEditAiMessage).toHaveBeenCalledWith(0, 'Saved content');
  });

  it('TDD 2: User message editing triggers onEditAndResend', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'user',
          content: 'User message to edit'
        }
      ]
    };

    render(<ChatPanel {...props} />);

    // Enter edit mode
    // User edit button has '编辑并重发' title
    const userEditBtn = screen.getByTitle('编辑并重发');
    expect(userEditBtn).toBeInTheDocument();
    
    fireEvent.click(userEditBtn);

    // Initial content check
    const textarea = document.querySelector('.edit-textarea');
    expect(textarea.value).toBe('User message to edit');

    // Modify and confirm
    fireEvent.change(textarea, { target: { value: 'User edited' } });
    const resendBtn = screen.getByText('重新发送');
    fireEvent.click(resendBtn);

    expect(mockOnEditAndResend).toHaveBeenCalledTimes(1);
    expect(mockOnEditAndResend).toHaveBeenCalledWith(0, 'User edited');
  });

  it('TDD 3: BashApprovalCard auto-dismisses when 60s countdown expires', async () => {
    vi.useFakeTimers();
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });

    const mockSetPendingApproval = vi.fn();
    const props = {
      ...getBaseProps(),
      pendingApproval: {
        approval_id: 'test-timeout-id',
        tool_name: 'execute_bash',
        command: 'echo "hello"'
      },
      setPendingApproval: mockSetPendingApproval
    };

    render(<ChatPanel {...props} />);

    // Verify card is present
    expect(screen.getByText('需要授权执行 Bash 命令')).toBeInTheDocument();
    expect(screen.getByText('echo "hello"')).toBeInTheDocument();

    // Fast-forward 60 seconds inside async act
    await act(async () => {
      vi.advanceTimersByTime(60000);
    });

    // Verify setPendingApproval(null) was called to dismiss card
    expect(mockSetPendingApproval).toHaveBeenCalledWith(null);

    global.fetch = originalFetch;
    vi.useRealTimers();
  });
});

