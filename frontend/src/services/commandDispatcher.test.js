import { describe, it, expect, vi } from 'vitest';
import { dispatchSystemCommand } from './commandDispatcher';

describe('commandDispatcher /update_persona tests', () => {
  it('handles SSE streaming with json_escape object { text: "..." } correctly without throwing', async () => {
    const sseChunks = [
      'data: {"text": "[系统更新] 正在检测本地角色卡源目录..."}\n\n',
      'data: {"text": "[系统更新] 发现最新原版人设：媚吻锋人物性格卡片V1.0.txt"}\n\n',
      'data: {"text": "*伸了个懒腰，柔柔地搂住你的胳膊*“夫君，奴家已经把自己的小档案更新好啦”"}\n\n'
    ];

    let currentChunk = 0;
    const mockReader = {
      read: vi.fn().mockImplementation(async () => {
        if (currentChunk < sseChunks.length) {
          const chunk = sseChunks[currentChunk++];
          return { value: new TextEncoder().encode(chunk), done: false };
        }
        return { value: undefined, done: true };
      })
    };

    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => mockReader
      }
    });

    let messages = [];
    const setMessages = vi.fn((updater) => {
      if (typeof updater === 'function') {
        messages = updater(messages);
      } else {
        messages = updater;
      }
    });

    const context = {
      setMessages,
      API_BASE: 'http://localhost:8000',
      getNowStr: () => '2026-10-20 00:30:00'
    };

    try {
      const handled = await dispatchSystemCommand('/update_persona', context);
      expect(handled).toBe(true);

      // Verify messages state
      // 1: user msg
      expect(messages[0].role).toBe('user');
      expect(messages[0].content).toBe('/update_persona');

      // Verify initial loading message
      const initialMsgs = setMessages.mock.calls[0][0]([]);
      expect(initialMsgs[1].content).toBe('导师正在提炼并更新角色设定卡，请稍候...');

      // 2: system_info progress (after done)
      expect(messages[1].role).toBe('system_info');
      expect(messages[1].type).toBe('persona_update_progress');
      expect(messages[1].state).toBe('done');
      expect(messages[1].content).toContain('角色设定卡提炼完毕，人设已同步。');

      // 3: Pure system card - no assistant dialogue bubble appended
      expect(messages.length).toBe(2);
      expect(messages.some(m => m.role === 'assistant')).toBe(false);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('handles Chinese command alias "更新人设" and "/更新人设"', async () => {
    const mockReader = {
      read: vi.fn().mockResolvedValue({ value: undefined, done: true })
    };
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader }
    });

    const setMessages = vi.fn();
    const context = {
      setMessages,
      API_BASE: 'http://localhost:8000',
      getNowStr: () => '2026-10-20 00:30:00'
    };

    try {
      expect(await dispatchSystemCommand('更新人设', context)).toBe(true);
      expect(await dispatchSystemCommand('/更新人设', context)).toBe(true);
    } finally {
      global.fetch = originalFetch;
    }
  });
});
