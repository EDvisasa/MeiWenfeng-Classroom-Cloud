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
      if (urlStr.includes('/api/models/configs')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            { id: 1, name: 'Default Model', is_active: 1, base_url: 'http://localhost', api_key: 'test' }
          ])
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
              { id: 'default', name: '全局基础课程 (通用)', is_default: true }
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
});

