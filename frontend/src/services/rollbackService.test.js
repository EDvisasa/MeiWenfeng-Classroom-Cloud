import { describe, it, expect, vi } from 'vitest';
import { executeRecursiveRollback } from './rollbackService';

describe('executeRecursiveRollback Service', () => {
  it('rolls back multiple turns in strict LIFO order down to target index', async () => {
    const messages = [
      { role: 'user', content: 'Turn 1 User' },
      { role: 'assistant', content: 'Turn 1 Asst' },
      { role: 'user', content: 'Turn 2 User' },
      { role: 'assistant', content: 'Turn 2 Asst' },
      { role: 'user', content: 'Turn 3 User' },
      { role: 'assistant', content: 'Turn 3 Asst' },
    ];

    const callLogs = [];
    const mockFetch = vi.fn().mockImplementation((url, opts) => {
      const body = JSON.parse(opts.body);
      callLogs.push(body);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success' })
      });
    });

    // Edit Turn 1 (index 0)
    const result = await executeRecursiveRollback({
      messages,
      index: 0,
      activeSessionId: 'sess_1',
      apiBase: 'http://localhost:8000',
      fetchFn: mockFetch
    });

    expect(result.success).toBe(true);
    expect(result.remainingMessages.length).toBe(0);
    // Should have called 3 times in LIFO order: Turn 3 -> Turn 2 -> Turn 1
    expect(callLogs.length).toBe(3);
    expect(callLogs[0]).toEqual({
      expected_user_msg: 'Turn 3 User',
      expected_assistant_msg: 'Turn 3 Asst'
    });
    expect(callLogs[1]).toEqual({
      expected_user_msg: 'Turn 2 User',
      expected_assistant_msg: 'Turn 2 Asst'
    });
    expect(callLogs[2]).toEqual({
      expected_user_msg: 'Turn 1 User',
      expected_assistant_msg: 'Turn 1 Asst'
    });
  });

  it('rolls back only the tail turn if editing the last turn', async () => {
    const messages = [
      { role: 'user', content: 'Turn 1 User' },
      { role: 'assistant', content: 'Turn 1 Asst' },
      { role: 'user', content: 'Turn 2 User' },
      { role: 'assistant', content: 'Turn 2 Asst' },
    ];

    const callLogs = [];
    const mockFetch = vi.fn().mockImplementation((url, opts) => {
      callLogs.push(JSON.parse(opts.body));
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success' })
      });
    });

    // Edit Turn 2 (index 2)
    const result = await executeRecursiveRollback({
      messages,
      index: 2,
      activeSessionId: 'sess_1',
      apiBase: 'http://localhost:8000',
      fetchFn: mockFetch
    });

    expect(result.success).toBe(true);
    expect(result.remainingMessages.length).toBe(2);
    expect(result.remainingMessages[0].content).toBe('Turn 1 User');
    expect(result.remainingMessages[1].content).toBe('Turn 1 Asst');
    // Only Turn 2 rolled back
    expect(callLogs.length).toBe(1);
    expect(callLogs[0]).toEqual({
      expected_user_msg: 'Turn 2 User',
      expected_assistant_msg: 'Turn 2 Asst'
    });
  });

  it('halts immediately if backend reports 409 conflict / temporal drift', async () => {
    const messages = [
      { role: 'user', content: 'Turn 1 User' },
      { role: 'assistant', content: 'Turn 1 Asst' },
      { role: 'user', content: 'Turn 2 User' },
      { role: 'assistant', content: 'Turn 2 Asst' },
    ];

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ detail: '时序已漂移：期望助手回复与数据库记录不符' })
    });

    const result = await executeRecursiveRollback({
      messages,
      index: 0,
      activeSessionId: 'sess_1',
      apiBase: 'http://localhost:8000',
      fetchFn: mockFetch
    });

    expect(result.success).toBe(false);
    expect(result.error).toContain('时序已漂移');
    // Halted on first failure without continuing
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('correctly groups and pops turns that contain interspersed system_info hints in one step', async () => {
    const messages = [
      { role: 'user', content: 'Turn 1 User' },
      { role: 'system_info', content: '🔍 成功检索并加载 4 个片段' },
      { role: 'assistant', content: 'Turn 1 Asst' },
      { role: 'user', content: 'Turn 2 User' },
      { role: 'system_info', content: '🔍 成功检索并加载 7 个长期记忆' },
      { role: 'assistant', content: 'Turn 2 Asst' },
    ];

    const callLogs = [];
    const mockFetch = vi.fn().mockImplementation((url, opts) => {
      callLogs.push(JSON.parse(opts.body));
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'success' })
      });
    });

    // Edit Turn 2 (index 3)
    const result = await executeRecursiveRollback({
      messages,
      index: 3,
      activeSessionId: 'sess_1',
      apiBase: 'http://localhost:8000',
      fetchFn: mockFetch
    });

    expect(result.success).toBe(true);
    // Only Turn 2 rolled back (all 3 messages of Turn 2 popped in ONE step!)
    expect(callLogs.length).toBe(1);
    expect(callLogs[0]).toEqual({
      expected_user_msg: 'Turn 2 User',
      expected_assistant_msg: 'Turn 2 Asst'
    });
    expect(result.remainingMessages.length).toBe(3);
    expect(result.remainingMessages[0].content).toBe('Turn 1 User');
    expect(result.remainingMessages[1].content).toBe('🔍 成功检索并加载 4 个片段');
    expect(result.remainingMessages[2].content).toBe('Turn 1 Asst');
  });
});
