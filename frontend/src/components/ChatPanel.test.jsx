import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatPanel from './ChatPanel';
import { COMMANDS } from '../constants/commands';

// Mock heavy child components and utilities to isolate ChatPanel behavior

vi.mock('./MissionProposalCard', () => ({
  default: ({ proposalData, onConfirm }) => (
    <div data-testid="mission-card">
      Mission
      {proposalData && (
        <button
          type="button"
          data-testid="mission-confirm-mock"
          onClick={() => onConfirm?.(proposalData)}
        >
          ConfirmMock
        </button>
      )}
    </div>
  )
}));

vi.mock('./QuizBlock', () => ({
  default: () => <div data-testid="quiz-block">Quiz</div>
}));

vi.mock('react-markdown', () => ({
  default: ({ children, remarkPlugins: plugins }) => (
    <div
      data-testid="react-markdown"
      data-has-glossary-plugin={String(Array.isArray(plugins) && plugins.some((p) => p?.name === 'remarkGlossaryTags'))}
    >
      {children}
    </div>
  )
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

  it('TDD 22 [ISSUE-49]: renders atmosphere_suggestion system message with one-click button', () => {
    const onSwitchAtmosphere = vi.fn();
    const props = {
      ...getBaseProps(),
      onSwitchAtmosphere,
      messages: [
        {
          role: 'system_info',
          type: 'atmosphere_suggestion',
          content: '当前正在上课且处于【生活模式】，点击一键切换为【研学模式】以启用高校水准精确推导'
        }
      ]
    };
    const { container } = render(<ChatPanel {...props} />);
    const pill = container.querySelector('.system-info-msg');
    expect(pill).toBeInTheDocument();
    expect(pill.textContent).toContain('当前正在上课且处于【生活模式】');

    const btn = screen.getByText('一键切换为研学');
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onSwitchAtmosphere).toHaveBeenCalledWith('study');
  });

  it('TDD 23 [ISSUE-53]: renders search_memory block as Remembering... with glow running dot and toggleable details', () => {
    const runningProps = {
      ...getBaseProps(),
      isStreaming: true,
      messages: [
        {
          role: 'assistant',
          streaming: true,
          content: '',
          blocks: [
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: "Remembering: '4.7k'",
              output: '',
              status: 'running'
            }
          ]
        }
      ]
    };

    const { container, rerender } = render(<ChatPanel {...runningProps} />);
    expect(screen.getByText('Remembering...')).toBeInTheDocument();
    expect(screen.queryByText('search_memory')).not.toBeInTheDocument();
    expect(container.querySelector('.claude-tool-status-dot.running.remembering')).toBeInTheDocument();
    expect(screen.getByText("Remembering: '4.7k'")).toBeInTheDocument();

    const doneProps = {
      ...getBaseProps(),
      isStreaming: false,
      messages: [
        {
          role: 'assistant',
          streaming: false,
          content: '找到了当时的约定。',
          blocks: [
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: "Remembering: '4.7k'",
              output: '- [journal #10 | 2026-10-15] 4.7kΩ',
              status: 'done'
            }
          ]
        }
      ]
    };

    rerender(<ChatPanel {...doneProps} />);
    expect(container.querySelector('.claude-tool-status-dot.done')).toBeInTheDocument();
    expect(container.querySelector('.claude-tool-status-dot.running')).not.toBeInTheDocument();

    const ioBox = container.querySelector('.claude-tool-io');
    expect(ioBox).toHaveClass('collapsed');
    fireEvent.click(container.querySelector('.claude-tool-header'));
    expect(ioBox).not.toHaveClass('collapsed');
  });

  it('TDD 24 [ISSUE-53]: groups consecutive search_memory calls into one expandable Remembering... card without merging other tools', () => {
    const groupedRunningProps = {
      ...getBaseProps(),
      isStreaming: true,
      messages: [
        {
          role: 'assistant',
          streaming: true,
          content: '',
          blocks: [
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: "Remembering: '4.7k'",
              output: '- [journal #10] 4.7kΩ',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: 'Remembering detail: journal#10',
              output: '',
              status: 'running'
            },
            {
              type: 'tool',
              tool_name: 'execute_bash',
              command: 'echo ok',
              output: 'ok',
              status: 'done'
            }
          ]
        }
      ]
    };

    const { container, rerender } = render(<ChatPanel {...groupedRunningProps} />);
    expect(screen.getAllByText('Remembering...')).toHaveLength(1);
    expect(screen.getByText('Bash')).toBeInTheDocument();
    expect(container.querySelector('.claude-tool-status-dot.running.remembering')).toBeInTheDocument();

    const groupedDoneProps = {
      ...getBaseProps(),
      isStreaming: false,
      messages: [
        {
          role: 'assistant',
          streaming: false,
          content: '找到了。',
          blocks: [
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: "Remembering: '4.7k'",
              output: '- [journal #10] 4.7kΩ',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: 'Remembering detail: journal#10',
              output: '完整记录：4.7k 上拉电阻',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'execute_bash',
              command: 'echo ok',
              output: 'ok',
              status: 'done'
            }
          ]
        }
      ]
    };

    rerender(<ChatPanel {...groupedDoneProps} />);
    expect(screen.getAllByText('Remembering...')).toHaveLength(1);
    const memoryCard = screen.getByText('Remembering...').closest('.claude-tool-block');
    expect(memoryCard.querySelector('.claude-tool-status-dot.done')).toBeInTheDocument();
    expect(memoryCard.querySelector('.claude-tool-status-dot.running')).not.toBeInTheDocument();

    // Collapsed by default: step-by-step full details stay folded until clicked
    expect(screen.queryByText('完整记录：4.7k 上拉电阻')).not.toBeInTheDocument();
    fireEvent.click(memoryCard.querySelector('.claude-tool-header'));
    expect(screen.getByText("Remembering: '4.7k'")).toBeInTheDocument();
    expect(screen.getByText('- [journal #10] 4.7kΩ')).toBeInTheDocument();
    expect(screen.getByText('Remembering detail: journal#10')).toBeInTheDocument();
    expect(screen.getByText('完整记录：4.7k 上拉电阻')).toBeInTheDocument();

    // Collapses again on second click
    fireEvent.click(memoryCard.querySelector('.claude-tool-header'));
    expect(screen.queryByText('完整记录：4.7k 上拉电阻')).not.toBeInTheDocument();
  });

  it('TDD 25 [ISSUE-67]: groups adjacent heterogeneous [Memory] tools (calendar, timeline, search, expand) into a single Remembering... card', () => {
    const crossToolProps = {
      ...getBaseProps(),
      isStreaming: false,
      messages: [
        {
          role: 'assistant',
          streaming: false,
          content: '翻过日程和时间线找到了。',
          blocks: [
            {
              type: 'tool',
              tool_name: 'get_memory_calendar',
              command: 'Remembering calendar: 2026-10',
              output: '[Memory Calendar Overview] - [2026-10-15] 2 sessions',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'get_memory_timeline',
              command: 'Remembering timeline: 2026-10-15',
              output: '- [journal #10 | 2026-10-15] I2C 上拉电阻...',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'search_memory',
              command: "Remembering: '4.7k'",
              output: '- [conversation #102] 约定焊 4.7k',
              status: 'done'
            },
            {
              type: 'tool',
              tool_name: 'expand_memory',
              command: 'Remembering detail: journal#10',
              output: '完整记录：标准模式采用 4.7kΩ',
              status: 'done'
            }
          ]
        }
      ]
    };

    render(<ChatPanel {...crossToolProps} />);
    expect(screen.getAllByText('Remembering...')).toHaveLength(1);
    expect(screen.getByText('(4 steps)')).toBeInTheDocument();
    expect(screen.queryByText('get_memory_calendar')).not.toBeInTheDocument();
    expect(screen.queryByText('expand_memory')).not.toBeInTheDocument();

    const memoryCard = screen.getByText('Remembering...').closest('.claude-tool-block');
    expect(screen.queryByText('完整记录：标准模式采用 4.7kΩ')).not.toBeInTheDocument();
    fireEvent.click(memoryCard.querySelector('.claude-tool-header'));
    expect(screen.getByText('Remembering calendar: 2026-10')).toBeInTheDocument();
    expect(screen.getByText('Remembering timeline: 2026-10-15')).toBeInTheDocument();
    expect(screen.getByText("Remembering: '4.7k'")).toBeInTheDocument();
    expect(screen.getByText('Remembering detail: journal#10')).toBeInTheDocument();
    expect(screen.getByText('完整记录：标准模式采用 4.7kΩ')).toBeInTheDocument();
  });

  it('renders nested <glossary> inside <explainer> card and bold bullets inline with glossary plugin wired (Bug #50)', () => {
    const explainerProps = {
      ...getBaseProps(),
      messages: [
        {
          role: 'assistant',
          content: `普通说明：
- **前置要点（<glossary term="KV-Cache">键值缓存机制</glossary>）**：普通段内术语。
<explainer title="小模型架构解析">
> **📚 课程归属**：模型架构

### 一、它到底“小”在哪儿？
- **巧思机制（<glossary term="Looped Transformer">循环层架构：将中间若干层神经网络权重重复运行多次。</glossary>）**：物理上只有 24 层。
</explainer>`,
        },
      ],
    };

    const { container } = render(<ChatPanel {...explainerProps} />);
    expect(screen.getByText('小模型架构解析')).toBeInTheDocument();
    const mdNodes = screen.getAllByTestId('react-markdown');
    expect(mdNodes.length).toBeGreaterThanOrEqual(2);
    expect(mdNodes.every((el) => el.getAttribute('data-has-glossary-plugin') === 'true')).toBe(true);
    // Inline <glossary> must NOT split text/explainer into standalone block GlossaryBlock elements
    expect(mdNodes[0]).toHaveTextContent('<glossary term="KV-Cache">键值缓存机制</glossary>');
    expect(container.querySelector('.explainer-content-wrapper [data-testid="react-markdown"]')).toHaveTextContent(
      '<glossary term="Looped Transformer">'
    );
  });

  it('TDD 26 [Bug #51]: paginates long session list popover (8 per page) instead of overflowing screen', () => {
    const manySessions = [
      { id: 'openclaw_trio_chat', title: '小白有话说...', messages: [] },
      ...Array.from({ length: 19 }, (_, idx) => ({
        id: `s-${idx + 1}`,
        title: `历史会话 ${idx + 1}`,
        messages: [],
      })),
    ];

    const props = {
      ...getBaseProps(),
      sessions: manySessions,
      activeSessionId: 's-1',
      showSessionList: true,
      setShowSessionList: vi.fn(),
      onSwitchSession: vi.fn(),
      onDeleteSession: vi.fn(),
    };

    const { container } = render(<ChatPanel {...props} />);
    const popover = container.querySelector('.session-list-popover');
    expect(popover).toBeInTheDocument();

    // Page 1 shows at most 8 items: trio + 历史会话 1..7
    expect(container.querySelectorAll('.session-item')).toHaveLength(8);
    expect(screen.getByText(/小白有话说/)).toBeInTheDocument();
    expect(screen.getByText('历史会话 7')).toBeInTheDocument();
    expect(screen.queryByText('历史会话 8')).not.toBeInTheDocument();
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled();

    // Next page -> Page 2 (历史会话 8..15)
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(container.querySelectorAll('.session-item')).toHaveLength(8);
    expect(screen.getByText('历史会话 8')).toBeInTheDocument();
    expect(screen.getByText('历史会话 15')).toBeInTheDocument();
    expect(screen.queryByText('历史会话 7')).not.toBeInTheDocument();

    // Next page -> Page 3 (历史会话 16..19)
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
    expect(container.querySelectorAll('.session-item')).toHaveLength(4);
    expect(screen.getByText('历史会话 19')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled();
  });

  it('TDD 27 [Bug #51]: locates active session page, filters by search, and closes on outside click or Escape', () => {
    const manySessions = Array.from({ length: 18 }, (_, idx) => ({
      id: `s-${idx + 1}`,
      title: `调试会话 ${idx + 1}`,
      messages: [],
    }));
    const setShowSessionList = vi.fn();

    const { container, rerender } = render(
      <ChatPanel
        {...getBaseProps()}
        sessions={manySessions}
        activeSessionId="s-12"
        showSessionList={true}
        setShowSessionList={setShowSessionList}
        onSwitchSession={vi.fn()}
        onDeleteSession={vi.fn()}
      />
    );

    // s-12 is at index 11 -> automatically opens Page 2 (items 9..16)
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(container.querySelector('.session-list-body .session-item.active')).toHaveTextContent('调试会话 12');

    // Filter by keyword
    const searchInput = screen.getByLabelText('搜索历史对话');
    fireEvent.change(searchInput, { target: { value: '18' } });
    expect(container.querySelectorAll('.session-item')).toHaveLength(1);
    expect(screen.getByText('调试会话 18')).toBeInTheDocument();

    // Clear search -> returns to Page 1 cleanly
    fireEvent.change(searchInput, { target: { value: '' } });
    expect(screen.getByText('1 / 3')).toBeInTheDocument();

    // Outside click & Escape dismiss popover
    fireEvent.mouseDown(document.body);
    expect(setShowSessionList).toHaveBeenCalledWith(false);

    setShowSessionList.mockClear();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(setShowSessionList).toHaveBeenCalledWith(false);

    // Shrinking sessions list clamps page cleanly when on last page
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    expect(screen.getByText('3 / 3')).toBeInTheDocument();
    rerender(
      <ChatPanel
        {...getBaseProps()}
        sessions={manySessions.slice(0, 10)}
        activeSessionId="s-1"
        showSessionList={true}
        setShowSessionList={setShowSessionList}
        onSwitchSession={vi.fn()}
        onDeleteSession={vi.fn()}
      />
    );
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
  });

  it('TDD 28 [Bug #52]: pauses auto-scroll when scrolled up during streaming and shows floating scroll-to-bottom button', () => {
    let mockScrollHeight = 1200;
    const baseProps = {
      ...getBaseProps(),
      activeSessionId: 's-1',
      isStreaming: true,
      messages: [
        { role: 'user', content: '讲一下卷积神经网络' },
        { role: 'assistant', blocks: [{ type: 'text', text: '正在蹦字第1段' }], streaming: true },
      ],
    };

    const { container, rerender } = render(<ChatPanel {...baseProps} />);
    const historyEl = container.querySelector('.chat-history');
    Object.defineProperty(historyEl, 'clientHeight', { configurable: true, value: 400 });
    Object.defineProperty(historyEl, 'scrollHeight', { configurable: true, get: () => mockScrollHeight });

    // Start at bottom -> streaming update auto-scrolls cleanly with zero floating button
    historyEl.scrollTop = 800;
    fireEvent.scroll(historyEl);
    mockScrollHeight = 1350;
    rerender(
      <ChatPanel
        {...baseProps}
        messages={[
          { role: 'user', content: '讲一下卷积神经网络' },
          { role: 'assistant', blocks: [{ type: 'text', text: '正在蹦字第1段\n正在蹦字第2段' }], streaming: true },
        ]}
      />
    );
    expect(historyEl.scrollTop).toBe(1350);
    expect(screen.queryByRole('button', { name: '回到底部' })).not.toBeInTheDocument();

    // User scrolls up past threshold (> 120px) to read earlier messages
    historyEl.scrollTop = 300;
    fireEvent.scroll(historyEl);
    const btn = screen.getByRole('button', { name: '回到底部' });
    expect(btn).toHaveClass('streaming');
    expect(btn).toHaveAttribute('title', '正在生成 · 回到底部');

    // Subsequent SSE token updates must NOT pull user down while scrolled up
    mockScrollHeight = 1600;
    rerender(
      <ChatPanel
        {...baseProps}
        messages={[
          { role: 'user', content: '讲一下卷积神经网络' },
          { role: 'assistant', blocks: [{ type: 'text', text: '正在蹦字第1段\n正在蹦字第2段\n正在蹦字第3段' }], streaming: true },
        ]}
      />
    );
    expect(historyEl.scrollTop).toBe(300);
    expect(screen.getByRole('button', { name: '回到底部' })).toBeInTheDocument();

    // Clicking button jumps back to bottom, hides button, and re-enables sticky follow
    fireEvent.click(btn);
    expect(historyEl.scrollTop).toBe(1600);
    expect(screen.queryByRole('button', { name: '回到底部' })).not.toBeInTheDocument();

    mockScrollHeight = 1750;
    rerender(
      <ChatPanel
        {...baseProps}
        messages={[
          { role: 'user', content: '讲一下卷积神经网络' },
          { role: 'assistant', blocks: [{ type: 'text', text: '正在蹦字第1段\n第2段\n第3段\n第4段' }], streaming: true },
        ]}
      />
    );
    expect(historyEl.scrollTop).toBe(1750);
  });

  it('TDD 29 [Bug #52]: resumes sticky scroll when manually scrolled back down, on session switch, or new user turn, without yanking on historical edit', () => {
    let mockScrollHeight = 1200;
    const makeProps = (overrides = {}) => ({
      ...getBaseProps(),
      activeSessionId: 's-1',
      isStreaming: false,
      messages: [
        { role: 'user', content: '早先问题' },
        { role: 'assistant', content: '早先长回答' },
      ],
      ...overrides,
    });

    const { container, rerender } = render(<ChatPanel {...makeProps({ isStreaming: true })} />);
    const historyEl = container.querySelector('.chat-history');
    Object.defineProperty(historyEl, 'clientHeight', { configurable: true, value: 400 });
    Object.defineProperty(historyEl, 'scrollHeight', { configurable: true, get: () => mockScrollHeight });

    // Scroll up while idle -> button stays visible with idle label
    historyEl.scrollTop = 200;
    fireEvent.scroll(historyEl);
    expect(screen.getByRole('button', { name: '回到底部' })).toBeInTheDocument();

    // Manually scroll back near bottom (gap = 20 <= 48) -> button hides & sticky resumes
    historyEl.scrollTop = 780;
    fireEvent.scroll(historyEl);
    expect(screen.queryByRole('button', { name: '回到底部' })).not.toBeInTheDocument();
    mockScrollHeight = 1400;
    rerender(
      <ChatPanel
        {...makeProps({
          isStreaming: true,
          messages: [
            { role: 'user', content: '早先问题' },
            { role: 'assistant', content: '早先长回答（继续输出）' },
          ],
        })}
      />
    );
    expect(historyEl.scrollTop).toBe(1400);

    // Scroll up again, then inline edit an existing assistant message -> must NOT yank down
    historyEl.scrollTop = 100;
    fireEvent.scroll(historyEl);
    rerender(
      <ChatPanel
        {...makeProps({
          isStreaming: false,
          messages: [
            { role: 'user', content: '早先问题' },
            { role: 'assistant', content: '手工修订后的早先回答' },
          ],
        })}
      />
    );
    expect(historyEl.scrollTop).toBe(100);
    const idleBtn = screen.getByRole('button', { name: '回到底部' });
    expect(idleBtn).not.toHaveClass('streaming');
    expect(idleBtn).toHaveAttribute('title', '回到底部');

    // Sending a new user message re-engages bottom lock automatically
    mockScrollHeight = 1500;
    rerender(
      <ChatPanel
        {...makeProps({
          isStreaming: true,
          messages: [
            { role: 'user', content: '早先问题' },
            { role: 'assistant', content: '手工修订后的早先回答' },
            { role: 'user', content: '新问题' },
          ],
        })}
      />
    );
    expect(historyEl.scrollTop).toBe(1500);
    expect(screen.queryByRole('button', { name: '回到底部' })).not.toBeInTheDocument();

    // Scroll up again, then switch activeSessionId -> snaps cleanly to bottom
    historyEl.scrollTop = 120;
    fireEvent.scroll(historyEl);
    mockScrollHeight = 900;
    rerender(
      <ChatPanel
        {...makeProps({
          activeSessionId: 's-2',
          isStreaming: false,
          messages: [
            { role: 'assistant', content: '另一个会话的历史消息' },
          ],
        })}
      />
    );
    expect(historyEl.scrollTop).toBe(900);
    expect(screen.queryByRole('button', { name: '回到底部' })).not.toBeInTheDocument();
  });
});

describe('ChatPanel Finalize Mission Rendering Tests (Bug #53)', () => {
  const makeBaseProps = (overrides = {}) => ({
    theme: 'light',
    messages: [],
    models: [],
    activeModel: 'DeepSeek',
    onEditAndResend: vi.fn(),
    onEditAiMessage: vi.fn(),
    chatEndRef: { current: null },
    inputRef: { current: document.createElement('textarea') },
    inputText: '',
    handleInputChange: vi.fn(),
    handleKeyDown: vi.fn(),
    sendMessage: vi.fn(),
    stopGeneration: vi.fn(),
    isStreaming: false,
    sessions: [{ id: 's-1', title: '/set_mission' }],
    activeSessionId: 's-1',
    ...overrides,
  });

  it('renders assistant <finalize_mission /> as a finalized contract card while keeping user messages raw and roleplay-free', () => {
    const assistantMsg = [
      '我眼见你落笔应下这桩学契。',
      '',
      '<finalize_mission goal="系统研读《滴天髓》原典并结合名家批注解析入门" time="每日50分钟" constraints="结合网络名家批注解析资料" skill="零基础小白" course_id="ditiansui_bazi"',
      '/>',
      '',
      '输入 /lesson 即可开讲第一课。',
    ].join('\n');

    const userMsg =
      '我已确定学习目标<finalize_mission goal="系统研读《滴天髓》原典并结合名家批注解析入门" time="每日50分钟" constraints="结合网络名家批注解析资料" skill="零基础小白" course_id="ditiansui_bazi" /> 并咨询 <property_update mood="test" /> 与 <glossary term="术语">解释</glossary>';

    const { container } = render(
      <ChatPanel
        {...makeBaseProps({
          messages: [
            { role: 'user', content: userMsg },
            { role: 'assistant', content: assistantMsg },
          ],
        })}
      />
    );

    const cards = container.querySelectorAll('.mission-finalized-card');
    expect(cards).toHaveLength(1);
    expect(cards[0]).toHaveTextContent('学习契约已立项');
    expect(cards[0]).toHaveTextContent('已归档');
    expect(cards[0]).toHaveTextContent('系统研读《滴天髓》原典并结合名家批注解析入门');
    expect(cards[0]).toHaveTextContent('每日50分钟');
    expect(cards[0]).toHaveTextContent('结合网络名家批注解析资料');
    expect(cards[0]).toHaveTextContent('零基础小白');
    expect(cards[0]).toHaveTextContent('ditiansui_bazi');

    const markdownNodes = screen.getAllByTestId('react-markdown');
    const userBubbleMd = markdownNodes.find((el) => el.textContent.includes('我已确定学习目标'));
    expect(userBubbleMd).toBeTruthy();
    expect(userBubbleMd).toHaveAttribute('data-has-glossary-plugin', 'false');
    expect(userBubbleMd.textContent).toContain('<finalize_mission');
    expect(userBubbleMd.textContent).toContain('<property_update mood="test" />');

    const assistantBubble = container.querySelector('.assistant-msg .message-bubble');
    expect(assistantBubble).toBeTruthy();
    expect(assistantBubble.textContent).not.toContain('<finalize_mission');
    expect(assistantBubble.textContent).toContain('我眼见你落笔应下这桩学契。');
    expect(assistantBubble.textContent).toContain('输入 /lesson 即可开讲第一课。');
  });

  it('forwards course_id with neutral teaching confirmation phrasing when MissionProposalCard confirms', () => {
    const sendMessage = vi.fn();
    render(
      <ChatPanel
        {...makeBaseProps({
          sendMessage,
          messages: [
            {
              role: 'assistant',
              content:
                '<mission_proposal goal="系统研读《滴天髓》" time="每日50分钟" constraints="精读" skill="零基础" course_id="ditiansui_bazi" />',
            },
          ],
        })}
      />
    );

    fireEvent.click(screen.getByTestId('mission-confirm-mock'));

    expect(sendMessage).toHaveBeenCalledTimes(1);
    const sent = sendMessage.mock.calls[0][0];
    expect(sent).toMatch(/^我已确定学习目标<finalize_mission /);
    expect(sent).not.toContain('老婆');
    expect(sent).toContain('goal="系统研读《滴天髓》"');
    expect(sent).toContain('course_id="ditiansui_bazi"');
  });

  it('sends active atmosphere_mode and persona_type to /api/chat/system_context and refetches on toggle (Bug #54)', async () => {
    const originalFetch = global.fetch;
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ baseSystemTokens: 120, system_prompt: 'preview' }),
    });
    global.fetch = mockFetch;

    try {
      const { rerender } = render(
        <ChatPanel
          {...makeBaseProps({
            atmosphereMode: 'study',
            personaType: 'original',
            messages: [{ role: 'user', content: '查看当前模式' }],
          })}
        />
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalled();
      });
      const firstBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(firstBody.atmosphere_mode).toBe('study');
      expect(firstBody.persona_type).toBe('original');

      mockFetch.mockClear();
      rerender(
        <ChatPanel
          {...makeBaseProps({
            atmosphereMode: 'daily',
            personaType: 'simplified',
            messages: [{ role: 'user', content: '查看当前模式' }],
          })}
        />
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(1);
      });
      const secondBody = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(secondBody.atmosphere_mode).toBe('daily');
      expect(secondBody.persona_type).toBe('simplified');
    } finally {
      global.fetch = originalFetch;
    }
  });
});
