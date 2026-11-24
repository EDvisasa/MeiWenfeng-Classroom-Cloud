import React, { useState, useEffect, useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { API_BASE } from '../config';
import { remarkPlugins, rehypePlugins } from '../utils/markdownPlugins';

// Pure SVG Icons (Strictly Zero Emoji)
const Icons = {
  Library: () => (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor">
      <path d="M1 2.5A1.5 1.5 0 0 1 2.5 1h3A1.5 1.5 0 0 1 7 2.5v11A1.5 1.5 0 0 1 5.5 15h-3A1.5 1.5 0 0 1 1 13.5v-11zm1.5-.5a.5.5 0 0 0-.5.5v11a.5.5 0 0 0 .5.5h3a.5.5 0 0 0 .5-.5v-11a.5.5 0 0 0-.5-.5h-3zM9 2.5A1.5 1.5 0 0 1 10.5 1h3A1.5 1.5 0 0 1 15 2.5v11a1.5 1.5 0 0 1-1.5 1.5h-3A1.5 1.5 0 0 1 9 13.5v-11zm1.5-.5a.5.5 0 0 0-.5.5v11a.5.5 0 0 0 .5.5h3a.5.5 0 0 0 .5-.5v-11a.5.5 0 0 0-.5-.5h-3z" />
    </svg>
  ),
  Folder: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M.54 3.87.5 3a2 2 0 0 1 2-2h3.672a2 2 0 0 1 1.414.586l.828.828A2 2 0 0 0 9.828 3h3.672a2 2 0 0 1 2 2v1H.54zm14.92 2.13H.5v7a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-7z" />
    </svg>
  ),
  FileText: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M4 0h5.293A1 1 0 0 1 10 .293L13.707 4a1 1 0 0 1 .293.707V14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zm5.5 1.5v2a1 1 0 0 0 1 1h2l-3-3zM4.5 7a.5.5 0 0 0 0 1h7a.5.5 0 0 0 0-1h-7zm0 2.5a.5.5 0 0 0 0 1h7a.5.5 0 0 0 0-1h-7zm0 2.5a.5.5 0 0 0 0 1h4a.5.5 0 0 0 0-1h-4z" />
    </svg>
  ),
  Search: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398h-.001c.03.04.062.078.098.115l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85a1.007 1.007 0 0 0-.115-.1zM12 6.5a5.5 5.5 0 1 1-11 0 5.5 5.5 0 0 1 11 0z" />
    </svg>
  ),
  Lock: () => (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 1a2 2 0 0 0-2 2v4H5a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-1V3a2 2 0 0 0-2-2zm1 6V3a1 1 0 0 0-2 0v4h2z" />
    </svg>
  ),
  ChevronDown: () => (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor">
      <path fillRule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z" />
    </svg>
  ),
  ChevronLeft: () => (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor">
      <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z" />
    </svg>
  ),
  ChevronRight: () => (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor">
      <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z" />
    </svg>
  ),
  Plus: () => (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
      <path d="M8 2a.75.75 0 0 1 .75.75v4.5h4.5a.75.75 0 0 1 0 1.5h-4.5v4.5a.75.75 0 0 1-1.5 0v-4.5h-4.5a.75.75 0 0 1 0-1.5h4.5v-4.5A.75.75 0 0 1 8 2z" />
    </svg>
  ),
  Save: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M2 1a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4.414a1 1 0 0 0-.293-.707l-2.414-2.414A1 1 0 0 0 11.586 1H2zm10 1v3H4V2h8zM4 14V8h8v6H4z" />
    </svg>
  ),
  Eye: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8zM1.173 8a13.133 13.133 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.133 13.133 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5c-2.12 0-3.879-1.168-5.168-2.457A13.134 13.134 0 0 1 1.172 8z" />
      <path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM7 8a1 1 0 1 1 2 0 1 1 0 0 1-2 0z" />
    </svg>
  ),
  Edit: () => (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.806 2.016 2.016-.806-1.21-1.21z" />
    </svg>
  ),
  Check: () => (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
      <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z" />
    </svg>
  ),
  Close: () => (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
      <path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8 2.146 2.854z" />
    </svg>
  )
};

const categoryLabels = {
  Lessons: '理论课时',
  Sandbox: '互动沙盒',
  References: '知识引录',
  LDRs: '决策记录',
  Settings: '课题配置'
};

const KnowledgeLibraryModal = ({
  isOpen,
  onClose,
  isDrafting = false,
  initialCourseId = 'default',
  onFileSaved,
  onCourseCreated
}) => {
  const [courses, setCourses] = useState([]);
  const [currentCourseId, setCurrentCourseId] = useState(initialCourseId);
  const [treeData, setTreeData] = useState([]);
  const [selectedFilePath, setSelectedFilePath] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [editedContent, setEditedContent] = useState('');
  const [mode, setMode] = useState('preview'); // 'preview' | 'edit'
  const [collapsedCategories, setCollapsedCategories] = useState({});
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileView, setMobileView] = useState('tree'); // 'tree' | 'workbench' (responsive drill-down)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false); // Desktop floating toggle handle

  // Course creation state
  const [showCreateCourseModal, setShowCreateCourseModal] = useState(false);
  const [newCourseId, setNewCourseId] = useState('');
  const [newCourseName, setNewCourseName] = useState('');
  const [createCourseError, setCreateCourseError] = useState('');

  // Saving state
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null);
  const prevIsOpenRef = React.useRef(false);

  // Fetch available courses
  const fetchCourses = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/materials/courses`);
      if (res.ok) {
        const data = await res.json();
        setCourses(data.courses || []);
      }
    } catch (e) {
      console.error('Failed to load courses', e);
    }
  }, []);

  // Fetch knowledge tree for current course
  const fetchTree = useCallback(async (courseId) => {
    try {
      const q = courseId && courseId !== 'default' ? `?course_id=${encodeURIComponent(courseId)}` : '';
      const res = await fetch(`${API_BASE}/api/chat/materials/tree${q}`);
      if (res.ok) {
        const data = await res.json();
        setTreeData(data.knowledge_tree || []);
      }
    } catch (e) {
      console.error('Failed to load knowledge tree', e);
    }
  }, []);

  // Fetch file content
  const loadFileContent = useCallback(async (relPath, courseId) => {
    try {
      const q = new URLSearchParams({ path: relPath });
      if (courseId && courseId !== 'default') {
        q.append('course_id', courseId);
      }
      const res = await fetch(`${API_BASE}/api/chat/materials/content?${q.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content || '');
        setEditedContent(data.content || '');
        setSelectedFilePath(relPath);
        setMode('preview');
        setSaveStatus(null);
      }
    } catch (e) {
      console.error('Failed to load material content', e);
    }
  }, []);

  // Load courses & sync initial course on open; fetch tree for active modal course
  useEffect(() => {
    const justOpened = isOpen && !prevIsOpenRef.current;
    prevIsOpenRef.current = isOpen;
    if (!isOpen) return;

    if (justOpened) {
      fetchCourses();
      const targetId = initialCourseId || 'default';
      setSelectedFilePath(null);
      setFileContent('');
      setEditedContent('');
      setSaveStatus(null);
      setMobileView('tree');
      if (targetId !== currentCourseId) {
        setCurrentCourseId(targetId);
        return;
      }
    }
    fetchTree(currentCourseId);
  }, [isOpen, currentCourseId, initialCourseId, fetchCourses, fetchTree]);

  // Handle course switch inside modal (display-only, does not alter external course state)
  const handleCourseChange = (e) => {
    const nextCourseId = e.target.value;
    setCurrentCourseId(nextCourseId);
    setSelectedFilePath(null);
    setFileContent('');
    setEditedContent('');
    setSaveStatus(null);
    setMobileView('tree');
  };

  // Handle new course creation
  const handleCreateCourseSubmit = async (e) => {
    e.preventDefault();
    setCreateCourseError('');
    if (!newCourseId.trim()) {
      setCreateCourseError('课题代号不能为空 (只允许字母、数字、下划线及中划线)');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/chat/materials/courses/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          course_id: newCourseId.trim(),
          name: newCourseName.trim() || newCourseId.trim()
        })
      });
      if (res.ok) {
        const data = await res.json();
        await fetchCourses();
        setCurrentCourseId(data.course.id);
        setShowCreateCourseModal(false);
        setNewCourseId('');
        setNewCourseName('');
        setSelectedFilePath(null);
        setFileContent('');
        setEditedContent('');
        setMobileView('tree');
        fetchTree(data.course.id);
        if (onCourseCreated) {
          onCourseCreated(data.course);
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateCourseError(err.detail || '创建课程课题失败');
      }
    } catch (err) {
      setCreateCourseError(`请求失败: ${err.message}`);
    }
  };

  // Handle file saving
  const handleSave = async () => {
    if (isDrafting) return;
    if (!selectedFilePath) return;

    setIsSaving(true);
    setSaveStatus(null);
    try {
      const payload = {
        path: selectedFilePath,
        content: editedContent
      };
      if (currentCourseId && currentCourseId !== 'default') {
        payload.course_id = currentCourseId;
      }
      const res = await fetch(`${API_BASE}/api/chat/materials/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setFileContent(editedContent);
        setSaveStatus({
          type: 'success',
          message: '保存成功，RAG 向量索引后台同步已触发'
        });
        if (onFileSaved) {
          onFileSaved(selectedFilePath, editedContent, currentCourseId);
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setSaveStatus({
          type: 'error',
          message: `保存失败: ${err.detail || res.statusText}`
        });
      }
    } catch (e) {
      setSaveStatus({
        type: 'error',
        message: `网络错误: ${e.message}`
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Keyboard shortcut Ctrl+S / Cmd+S in editor
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      if (!isDrafting && mode === 'edit') {
        handleSave();
      }
    }
  };

  // Toggle category collapse
  const toggleCategory = (cat) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [cat]: !prev[cat]
    }));
  };

  // Filtered tree based on search
  const filteredTree = useMemo(() => {
    if (!searchQuery.trim()) return treeData;
    const lower = searchQuery.toLowerCase();
    return treeData.map(group => {
      const filteredFiles = (group.files || []).filter(f =>
        f.name.toLowerCase().includes(lower) || f.path.toLowerCase().includes(lower)
      );
      return {
        ...group,
        files: filteredFiles
      };
    }).filter(group => group.files && group.files.length > 0);
  }, [treeData, searchQuery]);

  if (!isOpen) return null;

  // Selected file details
  const activeFileName = selectedFilePath
    ? selectedFilePath.split('/').pop().replace(/\.md$/, '')
    : '';
  const activeCategory = selectedFilePath
    ? selectedFilePath.split('/')[0]
    : '';

  return (
    <div className="kl-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="kl-modal-dialog" onClick={(e) => e.stopPropagation()} onKeyDown={handleKeyDown}>
        {/* Top Header */}
        <header className="kl-modal-header">
          <div className="kl-header-title">
            <span className="kl-header-icon"><Icons.Library /></span>
            <span className="kl-title-text">知识与微课档案库</span>
          </div>

          {/* Course Project Selector */}
          <div className="kl-course-selector-wrapper">
            <span className="kl-selector-label">课程课题:</span>
            <select
              className="kl-course-select"
              value={currentCourseId}
              onChange={handleCourseChange}
              aria-label="切换课程课题"
            >
              {courses.map(course => (
                <option key={course.id} value={course.id}>
                  {course.name || course.id}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="kl-btn-subtle"
              onClick={() => setShowCreateCourseModal(true)}
              title="新建独立课程课题"
            >
              <Icons.Plus /> 新建课题
            </button>
          </div>

          <div className="kl-header-right">
            {isDrafting && (
              <div className="kl-draft-lock-badge" title="当前课程处于目标拟定期，档案库处于只读锁定保护">
                <Icons.Lock />
                <span>目标拟定期 · 只读锁定</span>
              </div>
            )}
            <button
              type="button"
              className="kl-close-btn"
              onClick={onClose}
              title="关闭档案库"
              aria-label="关闭"
            >
              <Icons.Close />
            </button>
          </div>
        </header>

        {/* Modal Body: Split Pane Studio */}
        <div className={`kl-modal-body mobile-view-${mobileView}`}>
          {/* Left Pane: Hierarchy Tree Sidebar */}
          <aside className={`kl-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
            <div className="kl-search-bar">
              <span className="kl-search-icon"><Icons.Search /></span>
              <input
                type="text"
                placeholder="搜索课程微课与文档..."
                className="kl-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  className="kl-search-clear"
                  onClick={() => setSearchQuery('')}
                  title="清空"
                >
                  <Icons.Close />
                </button>
              )}
            </div>

            <div className="kl-tree-content">
              {filteredTree.length === 0 ? (
                <div className="kl-empty-tree">
                  <span>{searchQuery ? '未找到匹配文档' : '该课题目录下暂无文件'}</span>
                </div>
              ) : (
                filteredTree.map(group => {
                  const isCollapsed = Boolean(collapsedCategories[group.category]);
                  const catLabel = categoryLabels[group.category] || group.category;
                  const fileCount = group.files ? group.files.length : 0;

                  return (
                    <div key={group.category} className="kl-category-group">
                      <div
                        className="kl-category-header"
                        onClick={() => toggleCategory(group.category)}
                      >
                        <span className="kl-collapse-arrow">
                          {isCollapsed ? <Icons.ChevronRight /> : <Icons.ChevronDown />}
                        </span>
                        <span className="kl-cat-icon"><Icons.Folder /></span>
                        <span className="kl-cat-name">{group.category}</span>
                        <span className="kl-cat-label">({catLabel})</span>
                        <span className="kl-count-pill">{fileCount}</span>
                      </div>

                      {!isCollapsed && (
                        <div className="kl-files-list">
                          {fileCount === 0 ? (
                            <div className="kl-file-item empty">暂无文档</div>
                          ) : (
                            group.files.map(file => {
                              const isSelected = selectedFilePath === file.path;
                              return (
                                <div
                                  key={file.path}
                                  className={`kl-file-item ${isSelected ? 'active' : ''}`}
                                  onClick={() => {
                                    loadFileContent(file.path, currentCourseId);
                                    setMobileView('workbench');
                                  }}
                                  title={file.path}
                                >
                                  <span className="kl-file-icon"><Icons.FileText /></span>
                                  <span className="kl-file-name">{file.name}</span>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </aside>

          {/* 桌面端边框居中半圆折叠手柄 */}
          <button
            type="button"
            className={`kl-sidebar-border-handle ${isSidebarCollapsed ? 'collapsed' : ''}`}
            onClick={() => setIsSidebarCollapsed(prev => !prev)}
            title={isSidebarCollapsed ? "展开课程目录" : "收起课程目录"}
            aria-label={isSidebarCollapsed ? "展开课程目录" : "收起课程目录"}
          >
            <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
              {isSidebarCollapsed ? (
                <path fillRule="evenodd" d="M4.646 1.646a.5.5 0 0 1 .708 0l6 6a.5.5 0 0 1 0 .708l-6 6a.5.5 0 0 1-.708-.708L10.293 8 4.646 2.354a.5.5 0 0 1 0-.708z"/>
              ) : (
                <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
              )}
            </svg>
          </button>

          {/* Right Pane: Workbench */}
          <main className="kl-workbench">
            {selectedFilePath ? (
              <>
                {/* Workbench Toolbar */}
                <div className="kl-workbench-toolbar">
                  <div className="kl-toolbar-left-group">
                    <button
                      type="button"
                      className="kl-back-tree-btn"
                      onClick={() => setMobileView('tree')}
                      title="返回目录大纲"
                      aria-label="返回目录大纲"
                    >
                      <Icons.ChevronLeft />
                      <span>返回大纲</span>
                    </button>
                    <div className="kl-breadcrumb">
                      <span className="kl-bc-course">
                        {courses.find(c => c.id === currentCourseId)?.name || currentCourseId}
                      </span>
                      <span className="kl-bc-sep">/</span>
                      <span className="kl-bc-cat">{activeCategory}</span>
                      <span className="kl-bc-sep">/</span>
                      <span className="kl-bc-file">{activeFileName}.md</span>
                    </div>
                  </div>

                  <div className="kl-toolbar-actions">
                    {/* Mode Toggle Segment */}
                    <div className="kl-mode-segment">
                      <button
                        type="button"
                        className={`kl-seg-btn ${mode === 'preview' ? 'active' : ''}`}
                        onClick={() => setMode('preview')}
                      >
                        <Icons.Eye /> 预览
                      </button>
                      <button
                        type="button"
                        className={`kl-seg-btn ${mode === 'edit' ? 'active' : ''}`}
                        onClick={() => {
                          if (!isDrafting) setMode('edit');
                        }}
                        disabled={isDrafting}
                        title={isDrafting ? '目标拟定期禁止编辑' : '切换到编辑模式'}
                      >
                        <Icons.Edit /> 编辑
                      </button>
                    </div>

                    {/* Action Buttons */}
                    {mode === 'edit' && (
                      <button
                        type="button"
                        className="kl-btn-primary"
                        onClick={handleSave}
                        disabled={isSaving || isDrafting}
                      >
                        <Icons.Save /> {isSaving ? '正在保存与同步...' : '保存并同步 RAG'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Status Notice Banner */}
                {isDrafting && (
                  <div className="kl-alert-banner warning">
                    <Icons.Lock />
                    <span>当前课程正处于目标拟定期，档案库处于只读防漂移锁定状态，禁止保存修改。</span>
                  </div>
                )}

                {saveStatus && (
                  <div className={`kl-alert-banner ${saveStatus.type}`}>
                    {saveStatus.type === 'success' ? <Icons.Check /> : <Icons.Lock />}
                    <span>{saveStatus.message}</span>
                  </div>
                )}

                {/* Content View Area */}
                <div className="kl-content-container">
                  {mode === 'preview' ? (
                    <article className="kl-markdown-preview">
                      <ReactMarkdown
                        remarkPlugins={remarkPlugins}
                        rehypePlugins={rehypePlugins}
                        components={{
                          h1: ({ children, ...props }) => <h1 className="kl-md-h1" {...props}>{children}</h1>,
                          h2: ({ children, ...props }) => <h2 className="kl-md-h2" {...props}>{children}</h2>,
                          h3: ({ children, ...props }) => <h3 className="kl-md-h3" {...props}>{children}</h3>,
                          p: ({ children, ...props }) => <p className="kl-md-p" {...props}>{children}</p>,
                          ul: ({ children, ...props }) => <ul className="kl-md-ul" {...props}>{children}</ul>,
                          ol: ({ children, ...props }) => <ol className="kl-md-ol" {...props}>{children}</ol>,
                          blockquote: ({ children, ...props }) => (
                            <blockquote className="kl-md-blockquote" {...props}>{children}</blockquote>
                          ),
                          code({ node, inline, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '');
                            return !inline && match ? (
                              <div className="kl-code-block-wrapper">
                                <SyntaxHighlighter
                                  style={vscDarkPlus}
                                  language={match[1]}
                                  PreTag="div"
                                  customStyle={{
                                    margin: 0,
                                    padding: '16px',
                                    background: '#15171e',
                                    fontSize: '13px',
                                    lineHeight: '1.6',
                                    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace"
                                  }}
                                  {...props}
                                >
                                  {String(children).replace(/\n$/, '')}
                                </SyntaxHighlighter>
                              </div>
                            ) : (
                              <code className="kl-inline-code" {...props}>
                                {children}
                              </code>
                            );
                          },
                          table: ({ node, ...props }) => (
                            <div className="kl-table-wrapper">
                              <table className="kl-markdown-table" {...props} />
                            </div>
                          )
                        }}
                      >
                        {editedContent || '*(该文档暂无内容)*'}
                      </ReactMarkdown>
                    </article>
                  ) : (
                    <div className="kl-editor-wrapper">
                      <textarea
                        className="kl-markdown-editor"
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        placeholder="在此键入 Markdown 文档内容... (支持 Ctrl+S 快速保存)"
                        spellCheck={false}
                      />
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="kl-empty-workbench">
                <button
                  type="button"
                  className="kl-back-tree-btn kl-empty-back-btn"
                  onClick={() => setMobileView('tree')}
                  title="返回目录大纲"
                >
                  <Icons.ChevronLeft />
                  <span>返回目录大纲</span>
                </button>
                <div className="kl-empty-icon"><Icons.Library /></div>
                <h3>知识与微课档案工作台</h3>
                <p>请在左侧目录树中挑选微课课时、沙盒演练或引录文档。</p>
                <div className="kl-empty-tips">
                  <span>支持实时 LaTeX 数学公式渲染</span>
                  <span className="kl-dot">·</span>
                  <span>分课程目录严格物理隔离</span>
                  <span className="kl-dot">·</span>
                  <span>一键保存实时向量化索引</span>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Inline Modal: Create Course Project */}
      {showCreateCourseModal && (
        <div className="kl-submodal-overlay" onClick={() => setShowCreateCourseModal(false)}>
          <div className="kl-submodal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="kl-submodal-header">
              <h4>新建独立课程课题</h4>
              <button
                type="button"
                className="kl-close-btn"
                onClick={() => setShowCreateCourseModal(false)}
              >
                <Icons.Close />
              </button>
            </div>
            <form onSubmit={handleCreateCourseSubmit} className="kl-submodal-form">
              <div className="kl-form-group">
                <label>课题代号 (ID / Slug):</label>
                <input
                  type="text"
                  placeholder="例如: navier-stokes 或 quantum-computing"
                  value={newCourseId}
                  onChange={(e) => setNewCourseId(e.target.value)}
                  autoFocus
                />
                <span className="kl-form-tip">只允许字母、数字、下划线与中划线，用于物理隔离目录</span>
              </div>
              <div className="kl-form-group">
                <label>课题显示名称 (Name):</label>
                <input
                  type="text"
                  placeholder="例如: Navier-Stokes 有限时间爆破课题"
                  value={newCourseName}
                  onChange={(e) => setNewCourseName(e.target.value)}
                />
              </div>

              {createCourseError && (
                <div className="kl-form-error">{createCourseError}</div>
              )}

              <div className="kl-form-actions">
                <button
                  type="button"
                  className="kl-btn-subtle"
                  onClick={() => setShowCreateCourseModal(false)}
                >
                  取消
                </button>
                <button type="submit" className="kl-btn-primary">
                  创建课程空间
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default KnowledgeLibraryModal;

