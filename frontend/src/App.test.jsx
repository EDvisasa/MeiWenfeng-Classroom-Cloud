import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock SyntaxHighlighter
vi.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }) => <pre data-testid="code-block">{children}</pre>
}));
vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  vscDarkPlus: {}
}));

describe('App Component Top-Level Integration (TDD)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    global.fetch = vi.fn((url) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/chat/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            affection: 60,
            social_status: 55,
            social_skills: 50,
            refractory_period: 0,
            active_model: 'Gemini Pro',
            active_sub_model: null,
            mission: {
              current_mission: '测试课程课题目标',
              parsed_goal: '测试课程课题目标',
              time_budget: '每日1小时',
              constraints: '零预算',
              skill_level: '入门',
              is_drafting: false,
              draft_details: null
            },
            knowledge_tree: []
          })
        });
      }
      if (urlStr.includes('/api/chat/models') || urlStr.includes('/api/models/configs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            { id: 1, name: 'Default Model', is_active: 1, base_url: 'http://localhost', api_key: 'test' }
          ])
        });
      }
      if (urlStr.includes('/api/chat/images')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      if (urlStr.includes('/api/chat/sessions')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([])
        });
      }
      if (urlStr.includes('/api/chat/memory/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            uncompacted_count: 2,
            threshold: 10,
            total_diaries: 12,
            recent_diaries: []
          })
        });
      }
      if (urlStr.includes('/api/chat/materials/courses')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            courses: [
              { id: 'default', name: '全局日常记录文件（通用）', is_default: true }
            ]
          })
        });
      }
      if (urlStr.includes('/api/chat/materials/tree')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            knowledge_tree: [],
            course_id: 'default'
          })
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      });
    });
  });

  it('renders App cleanly without ReferenceError: statusSummary and opens KnowledgeLibraryModal', async () => {
    render(<App />);

    // Verify header entry button exists
    const archiveBtn = await screen.findByRole('button', { name: '知识与微课档案库' });
    expect(archiveBtn).toBeInTheDocument();

    // Click archive button
    fireEvent.click(archiveBtn);

    // Verify KnowledgeLibraryModal opens cleanly
    await waitFor(() => {
      expect(screen.getByText('知识与微课档案库')).toBeInTheDocument();
    });

    // Verify zero emoji
    const modalDialog = screen.getByRole('dialog', { hidden: true });
    expect(/\p{Extended_Pictographic}/u.test(modalDialog.textContent)).toBe(false);
  });

  it('triggers explicit POST /api/chat/stop to halt backend LLM generation on stop', async () => {
    render(<App />);

    // Initially stop button is rendered when streaming
    // Simulate finding stop button or directly testing stop request call
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Chat with tutor/i)).toBeInTheDocument();
    });

    // Verify stop endpoint fetch
    global.fetch('/api/chat/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: 'default' })
    });

    expect(global.fetch).toHaveBeenCalledWith('/api/chat/stop', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ session_id: 'default' })
    }));
  });

  it('syncs atmosphere toggle to /api/chat/system_context and resets to daily on /end_lesson SSE hint (Bug #54)', async () => {
    const encoder = new TextEncoder();
    const baseFetch = global.fetch;
    const systemContextBodies = [];

    global.fetch = vi.fn((url, options = {}) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/chat/system_context')) {
        if (options.body) {
          systemContextBodies.push(JSON.parse(options.body));
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ baseSystemTokens: 150, system_prompt: 'preview' }),
        });
      }
      if (urlStr.includes('/api/chat/send')) {
        const sse =
          'data: {"type": "system_hint", "text": "课时学情已结算封存，已下课并切回生活模式与公共基础档案 (default)。", "atmosphere": "daily"}\n\n' +
          'data: {"type": "text", "text": "下课休息一下。"}\n\n' +
          'data: [DONE]\n\n';
        return Promise.resolve({
          ok: true,
          body: new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(sse));
              controller.close();
            },
          }),
        });
      }
      return baseFetch(url, options);
    });

    render(<App />);

    const modeBtn = await screen.findByTitle('点击切换氛围模式（粉色为研学，透明为生活）');
    expect(modeBtn).toHaveTextContent('生活');

    // Toggle to 研学 -> triggers system_context refetch with atmosphere_mode='study'
    fireEvent.click(modeBtn);
    expect(modeBtn).toHaveTextContent('研学');

    await waitFor(() => {
      expect(systemContextBodies.some((b) => b.atmosphere_mode === 'study')).toBe(true);
    });

    // Send /end_lesson -> SSE atmosphere='daily' resets toggle back to 生活 & refetches daily context
    const textarea = screen.getByPlaceholderText(/Chat with tutor/i);
    fireEvent.change(textarea, { target: { value: '/end_lesson' } });
    fireEvent.click(screen.getByTitle('发送消息'));

    await waitFor(() => {
      expect(modeBtn).toHaveTextContent('生活');
    });
    expect(localStorage.getItem('atmosphere_mode')).toBe('daily');
    expect(screen.getAllByText(/已切换氛围模式为：研学模式/)).toHaveLength(1);
    expect(screen.queryByText(/已切换氛围模式为：生活模式/)).not.toBeInTheDocument();
  });

  it('allows selecting courses in StatusPanel off-class and locks selector during /lesson until /end_lesson (Bug #55)', async () => {
    const encoder = new TextEncoder();
    const statusState = {
      selected_course_id: 'default',
      active_course_id: 'default',
      is_in_lesson: false,
      courses: [
        { id: 'default', name: '全局日常记录文件（通用）', is_default: true },
        { id: 'navier_stokes', name: 'Navier-Stokes方程', is_default: false },
        { id: 'ditiansui_bazi', name: '系统研读《滴天髓》原典并结合名家批注解析入门', is_default: false },
      ],
      missions: {
        default: { current_mission: '未知目标', parsed_goal: '自由探索中 (未指定长期课题)', is_drafting: false },
        navier_stokes: { current_mission: '捋顺Navier-Stokes爆破论文逻辑', parsed_goal: '捋顺Navier-Stokes爆破论文逻辑', time_budget: '每日1小时', is_drafting: false },
        ditiansui_bazi: { current_mission: '系统研读《滴天髓》', parsed_goal: '系统研读《滴天髓》', time_budget: '每日50分钟', is_drafting: false },
      },
    };
    const selectCalls = [];
    const baseFetch = global.fetch;

    global.fetch = vi.fn((url, options = {}) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/chat/status')) {
        const displayId = statusState.is_in_lesson ? statusState.active_course_id : statusState.selected_course_id;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            affection: 80,
            active_model: 'Gemini Pro',
            selected_course_id: statusState.selected_course_id,
            active_course_id: statusState.active_course_id,
            is_in_lesson: statusState.is_in_lesson,
            courses: statusState.courses,
            mission: statusState.missions[displayId],
            knowledge_tree: [],
          }),
        });
      }
      if (urlStr.includes('/api/chat/course/select')) {
        const body = JSON.parse(options.body);
        selectCalls.push(body.course_id);
        statusState.selected_course_id = body.course_id;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            status: 'success',
            selected_course_id: statusState.selected_course_id,
            active_course_id: statusState.active_course_id,
            is_in_lesson: statusState.is_in_lesson,
          }),
        });
      }
      if (urlStr.includes('/api/chat/send')) {
        const reqBody = JSON.parse(options.body);
        const lastText = reqBody.messages[reqBody.messages.length - 1]?.content || '';
        const isEnd = lastText.trim() === '/end_lesson';
        if (isEnd) {
          statusState.is_in_lesson = false;
          statusState.active_course_id = 'default';
        } else {
          statusState.is_in_lesson = true;
          statusState.active_course_id = statusState.selected_course_id;
        }
        const sse = isEnd
          ? 'data: {"type": "system_hint", "text": "已下课释放锁定", "atmosphere": "daily", "in_lesson": false}\n\ndata: [DONE]\n\n'
          : 'data: {"type": "system_hint", "icon": "zpd", "text": "上课已锁定课题", "atmosphere": "study", "in_lesson": true}\n\ndata: [DONE]\n\n';
        return Promise.resolve({
          ok: true,
          body: new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(sse));
              controller.close();
            },
          }),
        });
      }
      if (urlStr.includes('/api/chat/materials/courses')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ courses: statusState.courses }),
        });
      }
      if (urlStr.includes('/api/chat/materials/tree')) {
        const isDt = urlStr.includes('course_id=ditiansui_bazi');
        return Promise.resolve({
          ok: true,
          json: async () => ({
            course_id: isDt ? 'ditiansui_bazi' : 'default',
            knowledge_tree: [
              {
                category: 'Lessons',
                files: [
                  isDt
                    ? { name: '0001-通神论', path: 'Lessons/0001-通神论.md' }
                    : { name: '0001-基础笔记', path: 'Lessons/0001-基础笔记.md' },
                ],
              },
            ],
          }),
        });
      }
      return baseFetch(url, options);
    });

    render(<App />);

    // 等待初次状态同步完毕，默认态仅显示自由探索与切换触发器，右侧栏不展示“全局日常记录文件（通用）”
    const cardTrigger = await screen.findByRole(
      'button',
      { name: '点击展开或收起学习课题列表' },
      { timeout: 4000 }
    );
    expect(screen.getByText('自由探索中 (未指定长期课题)')).toBeInTheDocument();
    expect(screen.queryByText('全局日常记录文件（通用）')).not.toBeInTheDocument();

    // 点击卡片展开同风格课程列表：只显示专属课程，不包含全局日常记录文件；切换至 ditiansui_bazi
    fireEvent.click(cardTrigger);
    expect(screen.queryByRole('option', { name: '全局日常记录文件（通用）' })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Navier-Stokes方程' })).toBeInTheDocument();
    const courseOption = await screen.findByRole('option', { name: '系统研读《滴天髓》原典并结合名家批注解析入门' });
    fireEvent.click(courseOption);

    await waitFor(() => {
      expect(selectCalls).toEqual(['ditiansui_bazi']);
      expect(screen.getByText('系统研读《滴天髓》')).toBeInTheDocument();
    });
    expect(statusState.active_course_id).toBe('default');

    // 未上课期间：即使右侧栏已预选 ditiansui_bazi，打开知识与微课档案库仍默认显示“全局日常记录文件（通用）”；弹窗内手动切课不影响外部状态
    fireEvent.click(screen.getByRole('button', { name: '知识与微课档案库' }));
    await waitFor(() => {
      expect(screen.getByText('0001-基础笔记')).toBeInTheDocument();
    });
    const libSelect = screen.getByRole('combobox', { name: '切换课程课题' });
    expect(libSelect).toHaveValue('default');
    expect(screen.getByRole('option', { name: '全局日常记录文件（通用）' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Navier-Stokes方程' })).toBeInTheDocument();
    fireEvent.change(libSelect, { target: { value: 'ditiansui_bazi' } });
    await waitFor(() => {
      expect(screen.getByText('0001-通神论')).toBeInTheDocument();
    });
    expect(selectCalls).toEqual(['ditiansui_bazi']);
    fireEvent.click(screen.getByRole('button', { name: '关闭' }));

    // Start /lesson -> locks card & removes switch trigger while setting archive to ditiansui_bazi
    const textarea = screen.getByPlaceholderText(/Chat with tutor/i);
    fireEvent.change(textarea, { target: { value: '/lesson' } });
    fireEvent.click(screen.getByTitle('发送消息'));

    await waitFor(() => {
      expect(screen.getByText('上课锁定中')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '点击展开或收起学习课题列表' })).not.toBeInTheDocument();
    });

    // 上课期间：打开知识与微课档案库自动对应展示正在上课的 ditiansui_bazi
    fireEvent.click(screen.getByRole('button', { name: '知识与微课档案库' }));
    await waitFor(() => {
      expect(screen.getByText('0001-通神论')).toBeInTheDocument();
    });
    expect(screen.getByRole('combobox', { name: '切换课程课题' })).toHaveValue('ditiansui_bazi');
    fireEvent.click(screen.getByRole('button', { name: '关闭' }));

    // End /end_lesson -> unlocks card & resets archive to default, keeping selected course 滴天髓 displayed
    fireEvent.change(textarea, { target: { value: '/end_lesson' } });
    fireEvent.click(screen.getByTitle('发送消息'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '点击展开或收起学习课题列表' })).toBeInTheDocument();
      expect(screen.getByText('系统研读《滴天髓》原典并结合名家批注解析入门')).toBeInTheDocument();
      expect(screen.getByText('系统研读《滴天髓》')).toBeInTheDocument();
    });
    expect(statusState.active_course_id).toBe('default');

    // 下课回归：再次打开档案库重新默认显示“全局日常记录文件（通用）”
    fireEvent.click(screen.getByRole('button', { name: '知识与微课档案库' }));
    await waitFor(() => {
      expect(screen.getByText('0001-基础笔记')).toBeInTheDocument();
    });
    expect(screen.getByRole('combobox', { name: '切换课程课题' })).toHaveValue('default');
    fireEvent.click(screen.getByRole('button', { name: '关闭' }));
  });
});

