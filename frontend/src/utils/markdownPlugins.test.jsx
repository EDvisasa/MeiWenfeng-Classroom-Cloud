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

describe('markdownPlugins inline <glossary> rendering (Bug #50)', () => {
  it('将加粗列表括号内的 <glossary> 渲染为行内术语徽标与定义而不破坏列表结构', () => {
    const { container } = renderMarkdown(
      '- **巧思机制（<glossary term="Looped Transformer">循环层架构：将中间若干层神经网络的权重重复运行多次，用较小的磁盘体积换取更深的等效推理深度。</glossary>）**：物理上只有 24 层。'
    );

    expect(container.querySelectorAll('li')).toHaveLength(1);
    expect(container.querySelector('.glossary-inline')).toBeInTheDocument();
    expect(container.querySelector('.glossary-inline-badge')).toHaveTextContent('Looped Transformer');
    expect(container.querySelector('.glossary-inline-def')).toHaveTextContent('循环层架构：将中间若干层神经网络的权重重复运行多次');
    expect(container.textContent).not.toContain('<glossary');
    expect(container.textContent).not.toContain('</glossary>');
    expect(container.textContent).toContain('物理上只有 24 层');
  });

  it('行内 <glossary> 内部包含 KaTeX 公式与同段多个词条时全部正常渲染', () => {
    const { container } = renderMarkdown(
      '对比 <glossary term="Attention">注意力机制 $Q K^T$</glossary> 与 <glossary term="MoE">混合专家架构</glossary>。'
    );

    const badges = container.querySelectorAll('.glossary-inline-badge');
    expect(badges).toHaveLength(2);
    expect(badges[0]).toHaveTextContent('Attention');
    expect(badges[1]).toHaveTextContent('MoE');
    expect(container.querySelector('.katex')).toBeInTheDocument();
    expect(container.textContent).not.toContain('<glossary');
  });

  it('流式输出尚未闭合 <glossary> 时不外泄裸标签', () => {
    const { container } = renderMarkdown(
      '- **巧思机制（<glossary term="StreamTerm">正在流式生成的术语定义'
    );

    expect(container.querySelector('.glossary-inline-badge')).toHaveTextContent('StreamTerm');
    expect(container.querySelector('.glossary-inline-def')).toHaveTextContent('正在流式生成的术语定义');
    expect(container.textContent).not.toContain('<glossary');
  });

  it('反引号行内代码中的 <glossary> 原样作为代码保留，不被误转换', () => {
    const { container } = renderMarkdown('语法示例：`<glossary term="Literal">示例</glossary>`。');

    expect(container.querySelector('.glossary-inline')).not.toBeInTheDocument();
    expect(container.querySelector('code')).toHaveTextContent('<glossary term="Literal">示例</glossary>');
  });

  it('档案预览等独立块级 <glossary> 自动渲染为术语卡片并解析内部 Markdown 与公式', () => {
    const { container } = renderMarkdown(
      '<glossary term="MoE">\n**混合专家** 激活公式 $y=W x$\n</glossary>'
    );

    expect(container.querySelector('.glossary-card-inline')).toBeInTheDocument();
    expect(container.querySelector('.glossary-inline-badge')).toHaveTextContent('MoE');
    expect(container.querySelector('.katex')).toBeInTheDocument();
    expect(container.textContent).toContain('混合专家');
    expect(container.textContent).not.toContain('<glossary');
  });
});
