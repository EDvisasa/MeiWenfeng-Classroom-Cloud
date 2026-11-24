import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import KnowledgeLibraryModal from './KnowledgeLibraryModal';

// Mock Prism SyntaxHighlighter to avoid canvas/DOM issues in JSDOM
vi.mock('react-syntax-highlighter', () => ({
  Prism: ({ children }) => <pre data-testid="code-block">{children}</pre>
}));
vi.mock('react-syntax-highlighter/dist/esm/styles/prism', () => ({
  vscDarkPlus: {}
}));

describe('KnowledgeLibraryModal Component (TDD - Zero Emoji & Course Isolation)', () => {
  const mockCourses = [
    { id: 'default', name: '全局日常记录文件（通用）', is_default: true },
    { id: 'navier-stokes', name: 'Navier-Stokes 方程爆破课题', is_default: false }
  ];

  const mockDefaultTree = [
    {
      category: 'Lessons',
      files: [
        { name: '0001-React基础', path: 'Lessons/0001-React基础.md' },
        { name: '0002-Hooks进阶', path: 'Lessons/0002-Hooks进阶.md' }
      ]
    },
    {
      category: 'Sandbox',
      files: [
        { name: 'exercise_01', path: 'Sandbox/exercise_01.md' }
      ]
    },
    {
      category: 'References',
      files: []
    }
  ];

  const mockNavierTree = [
    {
      category: 'Lessons',
      files: [
        { name: '0001-Navier-Stokes推导', path: 'Lessons/0001-Navier-Stokes推导.md' }
      ]
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn((url, options) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/chat/materials/courses/create')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'success',
            course: { id: 'quantum', name: '量子计算课题' }
          })
        });
      }
      if (urlStr.includes('/api/chat/materials/courses')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ courses: mockCourses })
        });
      }
      if (urlStr.includes('/api/chat/materials/tree')) {
        if (urlStr.includes('course_id=navier-stokes')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ knowledge_tree: mockNavierTree, course_id: 'navier-stokes' })
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ knowledge_tree: mockDefaultTree, course_id: 'default' })
        });
      }
      if (urlStr.includes('/api/chat/materials/content')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            content: '# React 基础微课\n\n这是 React 基础内容。包含数学公式 $E = mc^2$ 以及代码：\n\n```js\nconsole.log("hello");\n```\n',
            path: 'Lessons/0001-React基础.md'
          })
        });
      }
      if (urlStr.includes('/api/chat/materials/save')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            status: 'success',
            message: 'Material saved and RAG sync initiated'
          })
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${urlStr}`));
    });
  });

  it('1. Does not render when isOpen is false', () => {
    const { container } = render(
      <KnowledgeLibraryModal isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('2. Renders studio header, course selector, and close button when isOpen is true', async () => {
    const handleClose = vi.fn();
    const { container } = render(
      <KnowledgeLibraryModal isOpen={true} onClose={handleClose} />
    );

    expect(screen.getByText('知识与微课档案库')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: '切换课程课题' })).toBeInTheDocument();
    });

    // Verify Zero Emoji in rendered content
    const hasEmoji = /\p{Extended_Pictographic}/u.test(container.textContent);
    expect(hasEmoji).toBe(false);

    // Click close button
    const closeBtn = screen.getByRole('button', { name: '关闭' });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('3. Fetches and displays courses and knowledge tree files', async () => {
    render(<KnowledgeLibraryModal isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
      expect(screen.getByText('0002-Hooks进阶')).toBeInTheDocument();
      expect(screen.getByText('exercise_01')).toBeInTheDocument();
    });

    // Check category group labels
    expect(screen.getByText('(理论课时)')).toBeInTheDocument();
    expect(screen.getByText('(互动沙盒)')).toBeInTheDocument();
  });

  it('4. Real-time file filtering via search input', async () => {
    render(<KnowledgeLibraryModal isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('搜索课程微课与文档...');
    fireEvent.change(searchInput, { target: { value: 'Hooks' } });

    expect(screen.getByText('0002-Hooks进阶')).toBeInTheDocument();
    expect(screen.queryByText('0001-React基础')).not.toBeInTheDocument();
  });

  it('5. Switches course project and fetches isolated course directory tree', async () => {
    render(<KnowledgeLibraryModal isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    const courseSelect = screen.getByRole('combobox', { name: '切换课程课题' });
    fireEvent.change(courseSelect, { target: { value: 'navier-stokes' } });

    await waitFor(() => {
      expect(screen.getByText('0001-Navier-Stokes推导')).toBeInTheDocument();
    });

    expect(screen.queryByText('0001-React基础')).not.toBeInTheDocument();
  });

  it('6. Selects file, displays preview, and toggles to edit mode for saving with RAG sync', async () => {
    const handleSaved = vi.fn();
    render(
      <KnowledgeLibraryModal
        isOpen={true}
        onClose={vi.fn()}
        onFileSaved={handleSaved}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    // Click file item
    fireEvent.click(screen.getByText('0001-React基础'));

    // Wait for content preview
    await waitFor(() => {
      expect(screen.getByText('React 基础微课')).toBeInTheDocument();
    });

    // Switch to edit mode
    const editBtn = screen.getByRole('button', { name: /编辑/ });
    fireEvent.click(editBtn);

    const textarea = screen.getByPlaceholderText(/在此键入 Markdown 文档内容/);
    expect(textarea).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: '# Updated Content\nNew line' } });

    // Save button
    const saveBtn = screen.getByRole('button', { name: /保存并同步 RAG/ });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText(/保存成功，RAG 向量索引后台同步已触发/)).toBeInTheDocument();
    });

    expect(handleSaved).toHaveBeenCalledWith('Lessons/0001-React基础.md', '# Updated Content\nNew line', 'default');
  });

  it('7. Enforces drafting safety lock when isDrafting is true', async () => {
    const { container } = render(
      <KnowledgeLibraryModal
        isOpen={true}
        onClose={vi.fn()}
        isDrafting={true}
      />
    );

    // Lock badge in header
    expect(screen.getByText('目标拟定期 · 只读锁定')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('0001-React基础'));

    await waitFor(() => {
      expect(screen.getByText(/当前课程正处于目标拟定期，档案库处于只读防漂移锁定状态/)).toBeInTheDocument();
    });

    // Edit button is disabled
    const editBtn = screen.getByRole('button', { name: /编辑/ });
    expect(editBtn).toBeDisabled();

    // Verify Zero Emoji remains strictly enforced even with lock
    expect(/\p{Extended_Pictographic}/u.test(container.textContent)).toBe(false);
  });

  it('8. Mobile responsive drill-down: switches between tree and workbench with back button', async () => {
    const { container } = render(
      <KnowledgeLibraryModal isOpen={true} onClose={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    const modalBody = container.querySelector('.kl-modal-body');
    expect(modalBody).toHaveClass('mobile-view-tree');

    // Click file item -> transitions to workbench
    fireEvent.click(screen.getByText('0001-React基础'));

    await waitFor(() => {
      expect(modalBody).toHaveClass('mobile-view-workbench');
    });

    // Check back button exists
    const backBtn = screen.getByRole('button', { name: '返回目录大纲' });
    expect(backBtn).toBeInTheDocument();

    // Click back button -> transitions back to tree
    fireEvent.click(backBtn);
    expect(modalBody).toHaveClass('mobile-view-tree');
  });

  it('9. Desktop floating border handle: toggles sidebar collapse and expand', async () => {
    const { container } = render(
      <KnowledgeLibraryModal isOpen={true} onClose={vi.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('0001-React基础')).toBeInTheDocument();
    });

    const sidebar = container.querySelector('.kl-sidebar');
    const handleBtn = screen.getByRole('button', { name: '收起课程目录' });
    expect(sidebar).not.toHaveClass('collapsed');
    expect(handleBtn).not.toHaveClass('collapsed');

    // Click collapse
    fireEvent.click(handleBtn);
    expect(sidebar).toHaveClass('collapsed');
    expect(handleBtn).toHaveClass('collapsed');
    expect(handleBtn).toHaveAttribute('aria-label', '展开课程目录');

    // Click expand
    fireEvent.click(handleBtn);
    expect(sidebar).not.toHaveClass('collapsed');
    expect(handleBtn).not.toHaveClass('collapsed');
  });

  it('10. Syncs to initialCourseId when reopened and strips redundant suffix for 1-to-1 course names', async () => {
    const handleCourseCreated = vi.fn();
    const { rerender } = render(
      <KnowledgeLibraryModal
        isOpen={false}
        onClose={vi.fn()}
        initialCourseId="default"
        onCourseCreated={handleCourseCreated}
      />
    );

    rerender(
      <KnowledgeLibraryModal
        isOpen={true}
        onClose={vi.fn()}
        initialCourseId="navier-stokes"
        onCourseCreated={handleCourseCreated}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('0001-Navier-Stokes推导')).toBeInTheDocument();
    });

    const courseSelect = screen.getByRole('combobox', { name: '切换课程课题' });
    expect(courseSelect).toHaveValue('navier-stokes');
    expect(screen.getByRole('option', { name: '全局日常记录文件（通用）' })).toBeInTheDocument();

    // Create a new course inside modal triggers onCourseCreated sync callback
    fireEvent.click(screen.getByRole('button', { name: /新建课题/ }));
    fireEvent.change(screen.getByPlaceholderText(/navier-stokes 或 quantum-computing/i), { target: { value: 'quantum' } });
    fireEvent.change(screen.getByPlaceholderText(/Navier-Stokes 有限时间爆破课题/i), { target: { value: '量子计算课题' } });
    fireEvent.click(screen.getByRole('button', { name: '创建课程空间' }));

    await waitFor(() => {
      expect(handleCourseCreated).toHaveBeenCalledWith({ id: 'quantum', name: '量子计算课题' });
    });
  });
});
