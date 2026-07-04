import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PreviewEditModal from './PreviewEditModal';

describe('PreviewEditModal Component Tests (TDD)', () => {
  const mockFileData = {
    path: 'Lessons/0001-React基础.md',
    content: '# React 基础教程\n\n这是一篇自动归档的教程。'
  };

  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    fileData: mockFileData,
    onSaveSuccess: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('TDD 1: 默认渲染效果预览态 (Renders preview mode by default)', () => {
    render(<PreviewEditModal {...defaultProps} />);

    // 验证模态框标题和路径
    expect(screen.getByText(/0001-React基础.md/)).toBeInTheDocument();
    // 验证预览内容渲染
    expect(screen.getByText('React 基础教程')).toBeInTheDocument();
    expect(screen.getByText('这是一篇自动归档的教程。')).toBeInTheDocument();
  });

  it('TDD 2: 无缝切换到源码编辑态 (Switches to source edit mode)', () => {
    render(<PreviewEditModal {...defaultProps} />);

    // 点击切换到编辑态
    const editTab = screen.getByText(/源码编辑/);
    fireEvent.click(editTab);

    // 验证 textarea 存在且包含初始内容
    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();
    expect(textarea.value).toBe(mockFileData.content);
  });

  it('TDD 3: 修改内容并保存触发 POST /api/chat/materials/save (Edits and saves content)', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'success', path: mockFileData.path })
    });

    render(<PreviewEditModal {...defaultProps} />);

    // 切换到源码编辑态
    fireEvent.click(screen.getByText(/源码编辑/));

    // 修改内容
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: '# 新标题\n\n修改后的内容' } });

    // 点击保存按钮
    const saveButton = screen.getByText(/保存修改/);
    fireEvent.click(saveButton);

    // 验证 API 请求发送
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    const [url, options] = global.fetch.mock.calls[0];
    expect(url).toContain('/api/chat/materials/save');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({
      path: mockFileData.path,
      content: '# 新标题\n\n修改后的内容'
    });

    // 验证回调成功触发
    await waitFor(() => {
      expect(defaultProps.onSaveSuccess).toHaveBeenCalledWith('# 新标题\n\n修改后的内容');
    });
  });

  it('TDD 4: 点击关闭按钮触发 onClose (Closes modal when close button clicked)', () => {
    render(<PreviewEditModal {...defaultProps} />);

    const closeBtn = screen.getByTitle('关闭窗口');
    fireEvent.click(closeBtn);

    expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
  });
});
