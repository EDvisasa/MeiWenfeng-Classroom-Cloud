import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatPanel from './ChatPanel';
import { COMMANDS } from '../constants/commands';

// Mock heavy child components and utilities to isolate ChatPanel behavior

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

  it('TDD 4: renders markdown_doc system_info message without ReferenceError and parses custom cards', () => {
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });

    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          type: 'markdown_doc',
          path: 'data/materials/Lessons/test_lesson.md',
          content: '# 课程导学\n这里是一段介绍文本。\n<explainer title="重点原理解析">这里是深层次的理论说明。</explainer>'
        }
      ]
    };

    render(<ChatPanel {...props} />);

    expect(screen.getByText('📖 本地知识档案')).toBeInTheDocument();
    expect(screen.getByText(/文件路径：data\/materials\/Lessons\/test_lesson\.md/)).toBeInTheDocument();
    expect(screen.getByText(/这里是一段介绍文本。/)).toBeInTheDocument();
    expect(screen.getByText('重点原理解析')).toBeInTheDocument();
    expect(screen.getByText(/这里是深层次的理论说明。/)).toBeInTheDocument();

    global.fetch = originalFetch;
  });

  it('TDD 5 [Bug #8]: triggers system_context fetch when isStreaming changes from true to false', async () => {
    const originalFetch = global.fetch;
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ baseSystemTokens: 100, system_prompt: "updated prompt" })
    });
    global.fetch = mockFetch;

    const props = {
      ...getBaseProps(),
      isStreaming: true,
      messages: [{ role: 'assistant', content: '流式生成完毕的内容' }]
    };

    const { rerender } = render(<ChatPanel {...props} />);
    expect(mockFetch).toHaveBeenCalled();
    mockFetch.mockClear();

    // Rerender with isStreaming=false while messages.length remains the same
    rerender(<ChatPanel {...props} isStreaming={false} />);
    expect(mockFetch).toHaveBeenCalled();

    global.fetch = originalFetch;
  });

  it('TDD 6 [Bug #9]: triggers system_context fetch when opening system prompt modal or clicking button', async () => {
    const originalFetch = global.fetch;
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ baseSystemTokens: 200, system_prompt: "latest system prompt" })
    });
    global.fetch = mockFetch;

    const props = {
      ...getBaseProps(),
      isStreaming: false,
      messages: [{ role: 'user', content: '现在呢？' }]
    };

    render(<ChatPanel {...props} />);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    mockFetch.mockClear();

    const btn = screen.getByTitle('查看实时组装报文视窗 (Assembled Context Payload)');
    fireEvent.click(btn);

    expect(mockFetch).toHaveBeenCalledTimes(1);

    global.fetch = originalFetch;
  });

  it('renders call_openclaw_agent tool block friendly name as OpenClaw', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          blocks: [
            { type: 'tool', tool_name: 'call_openclaw_agent', status: 'done', output: 'ok' }
          ]
        }
      ]
    };
    render(<ChatPanel {...props} />);
    expect(screen.getByText('OpenClaw')).toBeInTheDocument();
  });

  it('TDD 7 [Bug #21]: shortcuts-popover honors SSOT and renders all commands with descriptions', () => {
    const executeSlashCommand = vi.fn();
    const props = {
      ...getBaseProps(),
      executeSlashCommand
    };

    render(<ChatPanel {...props} />);

    const triggerBtn = screen.getByTitle('快捷工具');
    expect(triggerBtn).toBeInTheDocument();

    fireEvent.click(triggerBtn);

    expect(screen.getByText('⚡ 快捷指令菜单')).toBeInTheDocument();

    COMMANDS.forEach(cmdItem => {
      expect(screen.getByText(cmdItem.cmd)).toBeInTheDocument();
      expect(screen.getByText(cmdItem.desc)).toBeInTheDocument();
    });

    const missionCmd = screen.getByText('/set_mission');
    fireEvent.click(missionCmd);
    expect(executeSlashCommand).toHaveBeenCalledWith('/set_mission');
  });

  it('TDD 8 [Bug #21]: command-list-popover renders filteredCommands with aligned grid layout', () => {
    const selectCommand = vi.fn();
    const props = {
      ...getBaseProps(),
      showCommandList: true,
      filteredCommands: COMMANDS,
      activeCommandIndex: 0,
      selectCommand
    };

    render(<ChatPanel {...props} />);

    expect(screen.getByText('⚡ Quick Commands')).toBeInTheDocument();
    COMMANDS.forEach(cmdItem => {
      expect(screen.getByText(cmdItem.cmd)).toBeInTheDocument();
      expect(screen.getByText(cmdItem.desc)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('/plan'));
    expect(selectCommand).toHaveBeenCalledWith(expect.objectContaining({ cmd: '/plan' }));
  });

  it('TDD 9 [Bug #23]: ExplainerBlock renders with strict containment (maxWidth 100% and minWidth 0) preventing flex blowout', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          content: 'Here is the setting:\n<explainer title="凡人修仙传同人设定">\n```xml\n<媚吻锋_凡妻角色基础>\n测试超长单行代码不折行\n</媚吻锋_凡妻角色基础>\n```\n</explainer>'
        }
      ]
    };

    const { container } = render(<ChatPanel {...props} />);

    expect(screen.getByText('凡人修仙传同人设定')).toBeInTheDocument();
    const explainerCard = container.querySelector('[style*="max-width: 100%"]');
    expect(explainerCard).toBeInTheDocument();
    expect(explainerCard).toHaveStyle({ maxWidth: '100%', minWidth: '0px' });
  });

  it('TDD 10: renders attached user images in chat bubble and image upload button in toolbar', () => {
    const dummyImage = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==';
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'user',
          content: '看这张截图',
          images: [dummyImage]
        }
      ]
    };

    const { container } = render(<ChatPanel {...props} />);

    // Check image upload button exists in toolbar
    const uploadBtn = container.querySelector('.image-upload-btn');
    expect(uploadBtn).toBeInTheDocument();

    // Check user message renders attached image
    const attachedImg = container.querySelector('.chat-bubble-img');
    expect(attachedImg).toBeInTheDocument();
    expect(attachedImg).toHaveAttribute('src', dummyImage);
  });

  it('TDD 11 [Bug #26]: pasting single image from clipboard adds exactly one image chip preview', async () => {
    const props = getBaseProps();
    const { container } = render(<ChatPanel {...props} />);
    const textarea = container.querySelector('.chat-input');
    expect(textarea).toBeInTheDocument();

    const dummyFile = new File(['fake-image-bytes'], 'screenshot.png', { type: 'image/png' });

    await act(async () => {
      fireEvent.paste(textarea, {
        clipboardData: {
          files: [dummyFile],
          items: [
            {
              type: 'image/png',
              getAsFile: () => dummyFile
            }
          ]
        }
      });
    });

    await waitFor(() => {
      const chips = container.querySelectorAll('.input-image-chip');
      expect(chips.length).toBe(1);
    });
  });

  it('TDD 12 [ISSUE-31]: image upload button is disabled and shows tooltip when active model does not support vision', () => {
    const props = {
      ...getBaseProps(),
      models: [
        { id: 1, name: 'DeepSeek', supports_vision: 0 }
      ],
      activeModel: 'DeepSeek'
    };

    const { container } = render(<ChatPanel {...props} />);
    const uploadBtn = container.querySelector('.image-upload-btn');
    expect(uploadBtn).toBeInTheDocument();
    expect(uploadBtn).toHaveStyle({ cursor: 'not-allowed' });
    expect(uploadBtn).toHaveAttribute('title', '当前模型未开启识图能力');

    const fileInput = uploadBtn.querySelector('input[type="file"]');
    expect(fileInput).toBeDisabled();
  });

  it('TDD 13 [ISSUE-31]: shows warning toast and intercepts paste when active model does not support vision', async () => {
    const props = {
      ...getBaseProps(),
      models: [
        { id: 1, name: 'DeepSeek', supports_vision: 0 }
      ],
      activeModel: 'DeepSeek'
    };

    const { container } = render(<ChatPanel {...props} />);
    const textarea = container.querySelector('.chat-input');
    const dummyFile = new File(['fake-bytes'], 'test.png', { type: 'image/png' });

    await act(async () => {
      fireEvent.paste(textarea, {
        clipboardData: {
          files: [dummyFile]
        }
      });
    });

    const toast = container.querySelector('.vision-warning-toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveTextContent('当前模型不支持识图');

    const chips = container.querySelectorAll('.input-image-chip');
    expect(chips.length).toBe(0);
  });

  it('TDD 14 [ISSUE-31]: supports controlled selectedImages and setSelectedImages props from parent', async () => {
    const mockSetSelectedImages = vi.fn();
    const mockSendMessage = vi.fn();
    const testImages = [{ id: 'img_test_1', name: 'photo.jpg', dataUrl: 'data:image/jpeg;base64,123' }];

    const props = {
      ...getBaseProps(),
      inputText: 'Check this image',
      sendMessage: mockSendMessage,
      selectedImages: testImages,
      setSelectedImages: mockSetSelectedImages
    };

    const { container } = render(<ChatPanel {...props} />);
    const chips = container.querySelectorAll('.input-image-chip');
    expect(chips.length).toBe(1);
    expect(chips[0]).toHaveAttribute('title', 'photo.jpg');

    const sendBtn = container.querySelector('.send-button');
    await act(async () => {
      fireEvent.click(sendBtn);
    });

    expect(mockSendMessage).toHaveBeenCalledWith({
      text: 'Check this image',
      images: ['data:image/jpeg;base64,123']
    });
    expect(mockSetSelectedImages).toHaveBeenCalledWith([]);
  });

  it('TDD 15 [Bug #27]: clears input text via setInputText when user sends a message or presses Enter', async () => {
    const mockSendMessage = vi.fn();
    const mockSetInputText = vi.fn();

    const props = {
      ...getBaseProps(),
      inputText: 'Question for the tutor',
      setInputText: mockSetInputText,
      sendMessage: mockSendMessage
    };

    const { container } = render(<ChatPanel {...props} />);
    const sendBtn = container.querySelector('.send-button');
    expect(sendBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(sendBtn);
    });

    expect(mockSendMessage).toHaveBeenCalledWith({
      text: 'Question for the tutor',
      images: []
    });
    expect(mockSetInputText).toHaveBeenCalledWith('');

    // Also verify Enter key triggers send and clear
    mockSendMessage.mockClear();
    mockSetInputText.mockClear();

    const textarea = container.querySelector('.chat-input');
    await act(async () => {
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    });

    expect(mockSendMessage).toHaveBeenCalledWith({
      text: 'Question for the tutor',
      images: []
    });
    expect(mockSetInputText).toHaveBeenCalledWith('');
  });

  it('TDD 16 [ISSUE-32]: /cooldown is registered in COMMANDS SSOT', () => {
    const cooldownCmd = COMMANDS.find((c) => c.cmd === '/cooldown');
    expect(cooldownCmd).toBeDefined();
    expect(cooldownCmd.desc).toMatch(/静心专注|余韵温存/);
  });

  it('TDD 17: decodes [系统提示] prefix from assistant message into outside system-info-msg pill', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          content: '[系统提示] 开启清醒贤者模式。好感度回退至常态（85/100），生理不应期已重置（25）。\n\n敏锐察觉到你眉宇间的肃然与专注，轻轻收敛起平素的嬉闹娇媚。'
        }
      ]
    };

    const { container } = render(<ChatPanel {...props} />);
    const systemPill = container.querySelector('.system-info-msg');
    expect(systemPill).toBeInTheDocument();
    expect(systemPill.textContent).toContain('开启清醒贤者模式');
    expect(systemPill.textContent).toContain('85/100');

    // Speech bubble must NOT contain [系统提示]
    const bubble = container.querySelector('.message-bubble');
    expect(bubble).toBeInTheDocument();
    expect(bubble.textContent).not.toContain('[系统提示]');
    expect(bubble.textContent).toContain('敏锐察觉到你眉宇间的肃然与专注');
  });

  it('TDD 18 [Bug #30]: renders persona_update_progress card in loading, done, and error states', () => {
    // 1. Loading state
    const loadingProps = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          type: 'persona_update_progress',
          state: 'loading',
          content: '导师正在提炼并更新角色设定卡，请稍候...'
        }
      ]
    };
    const { container: c1 } = render(<ChatPanel {...loadingProps} />);
    const loadingPill = c1.querySelector('.system-info-msg');
    expect(loadingPill).toBeInTheDocument();
    expect(loadingPill.textContent).toContain('导师正在提炼并更新角色设定卡，请稍候...');

    // 2. Done state
    const doneProps = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          type: 'persona_update_progress',
          state: 'done',
          content: '角色卡已更新，最新精简人设已同步！'
        }
      ]
    };
    const { container: c2 } = render(<ChatPanel {...doneProps} />);
    const donePill = c2.querySelector('.system-info-msg');
    expect(donePill).toBeInTheDocument();
    expect(donePill.textContent).toContain('角色卡已更新，最新精简人设已同步！');

    // 3. Error state
    const errorProps = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          type: 'persona_update_progress',
          state: 'error',
          error: '在目录中未找到匹配的原版人设卡片'
        }
      ]
    };
    const { container: c3 } = render(<ChatPanel {...errorProps} />);
    const errorPill = c3.querySelector('.system-info-msg');
    expect(errorPill).toBeInTheDocument();
    expect(errorPill.textContent).toContain('在目录中未找到匹配的原版人设卡片');
  });

  it('TDD 19 [Bug #30]: renders system_info with text fallback when content is undefined', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          text: 'Fallback text when content is missing'
        }
      ]
    };
    const { container } = render(<ChatPanel {...props} />);
    const pill = container.querySelector('.system-info-msg');
    expect(pill).toBeInTheDocument();
    expect(pill.textContent).toContain('Fallback text when content is missing');
  });

  it('TDD 20 [Bug #30]: safely unpacks object payload { text: "..." } in system messages', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'system_info',
          type: 'persona_update_progress',
          state: 'loading',
          content: { text: '正在读取原版人设...' }
        },
        {
          role: 'system_info',
          content: { text: 'Fallback object text' }
        }
      ]
    };
    const { container } = render(<ChatPanel {...props} />);
    const pills = container.querySelectorAll('.system-info-msg');
    expect(pills.length).toBe(2);
    expect(pills[0].textContent).toContain('正在读取原版人设...');
    expect(pills[1].textContent).toContain('Fallback object text');
  });

  it('TDD 21 [ISSUE-38]: renders message containing markdown GFM table in ChatPanel', () => {
    const props = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          content: '| 项目 | 内容 |\n|---|---|\n| 基本信息 | 冯杰龙 |'
        }
      ]
    };
    const { container } = render(<ChatPanel {...props} />);
    const textBlock = container.querySelector('.text-block');
    expect(textBlock).toBeInTheDocument();
    expect(screen.getByTestId('react-markdown')).toHaveTextContent('| 项目 | 内容 |');
  });
});
