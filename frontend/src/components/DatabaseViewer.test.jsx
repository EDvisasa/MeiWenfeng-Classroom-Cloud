import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import DatabaseViewer from './DatabaseViewer';

describe('DatabaseViewer In-place Cell Scaling & Expansion Tests (ISSUE-39)', () => {
  const longContent = '这是一段非常长的测试对话记录与系统日志文本。'.repeat(15);

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url) => {
      if (url.includes('/api/chat/db/tables/chat_messages')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            table: 'chat_messages',
            columns: ['id', 'role', 'content'],
            data: [
              { id: 1, role: 'assistant', content: longContent }
            ]
          })
        });
      }
      if (url.includes('/api/chat/db/tables')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ tables: ['chat_messages'] })
        });
      }
      return Promise.reject(new Error(`Unhandled mock url: ${url}`));
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders table data and truncates long text in compact preview without icons', async () => {
    await act(async () => {
      render(<DatabaseViewer onClose={vi.fn()} />);
    });

    await waitFor(() => {
      expect(screen.getAllByText('chat_messages').length).toBeGreaterThan(0);
    });

    // Content should initially be truncated with hint
    const compactCell = await screen.findByText((content) => content.includes('点击缩放展开'));
    expect(compactCell).toBeDefined();
    expect(compactCell.className).toContain('db-cell-compact');
    expect(compactCell.textContent).not.toBe(longContent);
  });

  it('clicking a cell toggles in-place scaling/expansion to show full text and collapses on second click', async () => {
    await act(async () => {
      render(<DatabaseViewer onClose={vi.fn()} />);
    });

    const compactCell = await screen.findByText((content) => content.includes('点击缩放展开'));

    // First click: expand cell to reveal full un-truncated text
    await act(async () => {
      fireEvent.click(compactCell);
    });

    const expandedCell = await screen.findByText(longContent);
    expect(expandedCell).toBeDefined();
    expect(expandedCell.className).toContain('db-cell-expanded');
    expect(expandedCell.getAttribute('title')).toContain('点击缩回');

    // Second click: collapse back to compact preview
    await act(async () => {
      fireEvent.click(expandedCell);
    });

    const collapsedCell = await screen.findByText((content) => content.includes('点击缩放展开'));
    expect(collapsedCell).toBeDefined();
    expect(collapsedCell.className).toContain('db-cell-compact');
  });

  it('pressing Escape key collapses the expanded cell', async () => {
    const handleClose = vi.fn();
    await act(async () => {
      render(<DatabaseViewer onClose={handleClose} />);
    });

    const compactCell = await screen.findByText((content) => content.includes('点击缩放展开'));

    // Expand
    await act(async () => {
      fireEvent.click(compactCell);
    });

    expect(await screen.findByText(longContent)).toBeDefined();

    // Press Escape
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });

    // Should collapse, modal should NOT close
    expect(await screen.findByText((content) => content.includes('点击缩放展开'))).toBeDefined();
    expect(handleClose).not.toHaveBeenCalled();

    // Press Escape again when no cell expanded -> should trigger modal onClose
    await act(async () => {
      fireEvent.keyDown(window, { key: 'Escape' });
    });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('supports resizing drag without collapsing and provides explicit collapse button', async () => {
    await act(async () => {
      render(<DatabaseViewer onClose={vi.fn()} />);
    });

    const compactCell = await screen.findByText((content) => content.includes('点击缩放展开'));

    await act(async () => {
      fireEvent.click(compactCell);
    });

    // Verify resize handle support
    const expandedDiv = document.querySelector('.db-cell-expanded');
    expect(expandedDiv.style.resize).toBe('both');
    expect(expandedDiv.style.minWidth).toBe('360px');

    // Simulate drag (mouse move dx = 50px)
    await act(async () => {
      fireEvent.mouseDown(expandedDiv, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(expandedDiv, { clientX: 150, clientY: 100 });
      fireEvent.click(expandedDiv, { clientX: 150, clientY: 100 });
    });

    // Should NOT collapse because it was a drag
    expect(document.querySelector('.db-cell-expanded')).not.toBeNull();

    // Click the expanded cell without drag to collapse
    await act(async () => {
      fireEvent.mouseDown(expandedDiv, { clientX: 100, clientY: 100 });
      fireEvent.mouseUp(expandedDiv, { clientX: 100, clientY: 100 });
      fireEvent.click(expandedDiv, { clientX: 100, clientY: 100 });
    });

    // Should now be collapsed
    expect(document.querySelector('.db-cell-expanded')).toBeNull();
  });
});

