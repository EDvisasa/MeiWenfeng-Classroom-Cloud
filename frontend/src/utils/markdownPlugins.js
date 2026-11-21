import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

const GLOSSARY_OPEN_RE = /^<glossary(?:\s+[^>]*)?>$/i;
const GLOSSARY_SELF_CLOSING_RE = /^<glossary(?:\s+[^>]*)?\/>$/i;
const GLOSSARY_CLOSE_RE = /^<\/glossary\s*>$/i;
const GLOSSARY_FULL_BLOCK_RE = /^\s*(<glossary\b[^>]*>)([\s\S]*?)<\/glossary\s*>\s*$/i;
const GLOSSARY_HEAD_BLOCK_RE = /^\s*(<glossary\b[^>]*>)([\s\S]+)$/i;
const GLOSSARY_BLOCK_CONTAINERS = new Set(['root', 'listItem', 'blockquote']);

const parseGlossaryTerm = (rawOpenTag) => {
  const match = (rawOpenTag || '').match(/\bterm=(?:"([^"]*)"|'([^']*)'|([^\s>\/]+))/i);
  return ((match && (match[1] ?? match[2] ?? match[3])) || '').trim();
};

const stripPositions = (node) => {
  if (!node || typeof node !== 'object') return;
  delete node.position;
  if (Array.isArray(node.children)) {
    node.children.forEach(stripPositions);
  }
};

const buildGlossaryBadgeNode = (term) => ({
  type: 'glossaryInlineBadge',
  data: { hName: 'span', hProperties: { className: ['glossary-inline-badge'] } },
  children: [{ type: 'text', value: term }]
});

const buildGlossaryWrapperNode = (term, innerNodes, asBlock) => ({
  type: asBlock ? 'glossaryBlock' : 'glossaryInline',
  data: {
    hName: asBlock ? 'div' : 'span',
    hProperties: {
      className: [asBlock ? 'glossary-card-inline' : 'glossary-inline'],
      ...(term ? { 'data-glossary-term': term } : {})
    }
  },
  children: [
    ...(term ? [buildGlossaryBadgeNode(term)] : []),
    {
      type: asBlock ? 'glossaryBlockDef' : 'glossaryInlineDef',
      data: {
        hName: asBlock ? 'div' : 'span',
        hProperties: { className: ['glossary-inline-def'] }
      },
      children: innerNodes
    }
  ]
});

/**
 * 把“写在句子中间”的 `$$...$$` 提升为行间公式（display math）。
 *
 * 大模型经常把行间公式直接粘在中文句子后面，例如：
 *   `连续时间傅里叶变换的定义式为：$$X(\omega)=\int x(t)e^{-i\omega t}dt$$`
 * remark-math 在段落中间遇到 `$$` 时只会产出 `inlineMath` 节点，
 * 于是公式被当成行内小字渲染，无法居中独立成行，
 * 长公式还会把整行挤到气泡外。
 *
 * 本插件在 mdast 层做最小整形：只把“原始分隔符为 `$$`”的 `inlineMath` 节点
 * 的 KaTeX 目标类名由 `math-inline` 改写为 `math-display`，
 * 交由 rehype-katex 以 display 模式渲染。
 * 句子中的单美元 `$...$` 行内公式完全不受影响。
 */
const isDoubleDollarMath = (node, source) => {
  if (node.type !== 'inlineMath') return false;
  const start = node.position?.start?.offset;
  return typeof start === 'number' && source.slice(start, start + 2) === '$$';
};

export function remarkDisplayMathFromDoubleDollar() {
  return (tree, file) => {
    const source = String(file ?? '');
    if (!source) return;

    const walk = (node) => {
      if (!node || !Array.isArray(node.children)) return;

      node.children.forEach((child) => {
        if (isDoubleDollarMath(child, source)) {
          child.data = child.data || {};
          child.data.hProperties = {
            ...(child.data.hProperties || {}),
            className: ['language-math', 'math-display']
          };
        }
        walk(child);
      });
    };

    walk(tree);
  };
}

/**
 * 在共享 Markdown AST 层渲染 `<glossary term="...">...</glossary>` 术语微卡。
 *
 * 解决 `<explainer>` 讲义卡、列表加粗句内及本地 `.md` 档案预览中直接裸露
 * XML 标签的 Bug #50：
 * - 不启用 `rehype-raw`，杜绝任意原生 HTML 注入风险；
 * - 行内/加粗/列表中的 `<glossary>` 转化为不破坏排版流的行内徽标 + 解释胶囊；
 * - 代码块与行内反引号中的 `<glossary>` 因已被解析为 `code`/`inlineCode` 而原样保留；
 * - 独立多行 `<glossary>` 块级节点在子解析后同样支持内部 Markdown 与 KaTeX 公式。
 */
export function remarkGlossaryTags() {
  const processor = this;

  const parseSubMarkdown = (rawContent) => {
    const trimmed = (rawContent || '').trim();
    if (!trimmed || !processor || typeof processor.parse !== 'function') {
      return trimmed ? [{ type: 'paragraph', children: [{ type: 'text', value: trimmed }] }] : [];
    }
    const subTree = processor.parse(trimmed);
    remarkDisplayMathFromDoubleDollar()(subTree, { toString: () => trimmed });
    stripPositions(subTree);
    if (subTree.children.length === 1 && subTree.children[0].type === 'paragraph') {
      return subTree.children[0].children;
    }
    return subTree.children;
  };

  const transformChildren = (children, parentType) => {
    if (!Array.isArray(children)) return children;
    const isBlockContainer = GLOSSARY_BLOCK_CONTAINERS.has(parentType);
    const out = [];

    for (let i = 0; i < children.length; i++) {
      const node = children[i];
      if (node.type === 'html') {
        const trimmed = (node.value || '').trim();

        const fullMatch = trimmed.match(GLOSSARY_FULL_BLOCK_RE);
        if (fullMatch && !GLOSSARY_SELF_CLOSING_RE.test(fullMatch[1])) {
          const term = parseGlossaryTerm(fullMatch[1]);
          const innerChildren = parseSubMarkdown(fullMatch[2]);
          out.push(buildGlossaryWrapperNode(term, innerChildren, isBlockContainer));
          continue;
        }

        if (GLOSSARY_SELF_CLOSING_RE.test(trimmed)) {
          const term = parseGlossaryTerm(trimmed);
          out.push(buildGlossaryWrapperNode(term, [], false));
          continue;
        }

        const headMatch = !GLOSSARY_OPEN_RE.test(trimmed) ? node.value.match(GLOSSARY_HEAD_BLOCK_RE) : null;
        if (GLOSSARY_OPEN_RE.test(trimmed) || (headMatch && !GLOSSARY_SELF_CLOSING_RE.test(headMatch[1]))) {
          const openTag = headMatch ? headMatch[1] : trimmed;
          const term = parseGlossaryTerm(openTag);
          const innerNodes = headMatch ? [...parseSubMarkdown(headMatch[2])] : [];
          let j = i + 1;
          while (j < children.length) {
            const candidate = children[j];
            if (candidate.type === 'html' && GLOSSARY_CLOSE_RE.test((candidate.value || '').trim())) {
              break;
            }
            if (candidate.children) {
              candidate.children = transformChildren(candidate.children, candidate.type);
            }
            innerNodes.push(candidate);
            j++;
          }
          out.push(buildGlossaryWrapperNode(term, innerNodes, isBlockContainer));
          i = j;
          continue;
        }

        if (GLOSSARY_CLOSE_RE.test(trimmed)) {
          continue;
        }
      }

      if (node.children) {
        node.children = transformChildren(node.children, node.type);
      }
      out.push(node);
    }

    return out;
  };

  return (tree) => {
    tree.children = transformChildren(tree.children, tree.type);
  };
}

/**
 * 全库唯一的 Markdown 渲染插件配置单一点 (SSOT)。
 *
 * - remark-gfm：GitHub Flavored Markdown (表格 / 删除线 / 自动链接)
 * - remarkGlossaryTags：把行内与块级 `<glossary>` 转成不破坏排版的术语微卡结构
 * - remark-math：将 `$...$` 与 `$$...$$` 解析为 inlineMath / math 节点
 * - remarkDisplayMathFromDoubleDollar：把句子中间被粘连的 `$$...$$` 提升为行间公式
 * - rehype-katex：将上述数学节点渲染为 KaTeX HTML
 *
 * 任何新增的 Markdown 渲染面（聊天气泡 / 讲义卡片 / 知识档案预览弹窗）
 * 都必须复用这里的插件数组，严禁各组件各自拼接插件清单。
 */
export const remarkPlugins = [remarkGfm, remarkGlossaryTags, remarkMath, remarkDisplayMathFromDoubleDollar];

export const rehypePlugins = [rehypeKatex];
