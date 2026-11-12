import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { describe, it, expect } from 'vitest';
import ReactMarkdown from 'react-markdown';
import { remarkPlugins, rehypePlugins } from './markdownPlugins';

/**
 * ISSUE-54：公式（KaTeX）渲染回归看护。
 * 断言共享插件单一点确实把 $...$ / $$...$$ 转成 KaTeX 结构，
 * 而不是把原始美元符号当纯文本漏到气泡里。
 */
const renderMarkdown = (text) =>
  render(
    <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
      {text}
    </ReactMarkdown>
  );

describe('markdownPlugins math rendering (ISSUE-54)', () => {
  it('行间公式 $$...$$ 渲染为 katex-display 块', () => {
    const { container } = renderMarkdown(
      '连续时间傅里叶变换的定义式为：$$X(\\omega) = \\int_{-\\infty}^{+\\infty} x(t) e^{-i\\omega t} \\, dt$$'
    );

    expect(container.querySelector('.katex-display')).toBeInTheDocument();
    expect(container.textContent).not.toContain('$$');
    // 公式本体进入 KaTeX 的 TeX 语义层（MathML annotation），而非作为原始美元符文本外泄
    expect(container.querySelector('.katex-mathml annotation')).toHaveTextContent('\\omega');
  });

  it('行内公式 $...$ 渲染为 katex 行内节点', () => {
    const { container } = renderMarkdown(
      '很多初学者容易被负指数 $e^{-i\\omega t}$ 吓退，其实只要代入欧拉公式。'
    );

    expect(container.querySelector('.katex')).toBeInTheDocument();
    expect(container.querySelector('.katex-display')).not.toBeInTheDocument();
    expect(container.textContent).not.toContain('$e^');
    expect(container.textContent).toContain('吓退');
  });

  it('同一段落内的多个行内公式与行间公式共存时全部渲染', () => {
    const { container } = renderMarkdown(
      '1. $e^{-i\\omega t}$ 的本质：是以角速度 $\\omega$ 匀速旋转。\n\n$$F(\\omega) = \\int f(t) e^{-i\\omega t} dt$$'
    );

    const inline = container.querySelectorAll('.katex');
    expect(inline.length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector('.katex-display')).toBeInTheDocument();
    expect(container.textContent).not.toContain('$');
  });

  it('含 \\text{ Hz} 的单位标注公式不产生渲染错误，也不外泄源码', () => {
    const { container } = renderMarkdown('在 $100\\text{ Hz}$ 上放了多少能量。');

    expect(container.querySelector('.katex')).toBeInTheDocument();
    // katex-error 表示 KaTeX 解析失败并退化为红色原文
    expect(container.querySelector('.katex-error')).not.toBeInTheDocument();
    expect(container.textContent).toContain('Hz');
  });

  it('GFM 表格能力未被插件调整破坏', () => {
    const { container } = renderMarkdown('| 列1 | 列2 |\n| --- | --- |\n| A | B |');

    expect(container.querySelector('table')).toBeInTheDocument();
    expect(container.querySelectorAll('th')).toHaveLength(2);
  });

  it('无公式的普通文本保持原样渲染', () => {
    const { container } = renderMarkdown('今天的天气很适合读书。');

    expect(container.querySelector('.katex')).not.toBeInTheDocument();
    expect(container.textContent).toContain('今天的天气很适合读书。');
  });
});
