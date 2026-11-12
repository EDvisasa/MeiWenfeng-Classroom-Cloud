import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

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
 * 全库唯一的 Markdown 渲染插件配置单一点 (SSOT)。
 *
 * - remark-gfm：GitHub Flavored Markdown (表格 / 删除线 / 自动链接)
 * - remark-math：将 `$...$` 与 `$$...$$` 解析为 inlineMath / math 节点
 * - remarkDisplayMathFromDoubleDollar：把句子中间被粘连的 `$$...$$` 提升为行间公式
 * - rehype-katex：将上述数学节点渲染为 KaTeX HTML
 *
 * 任何新增的 Markdown 渲染面（聊天气泡 / 讲义卡片 / 知识档案预览弹窗）
 * 都必须复用这里的插件数组，严禁各组件各自拼接插件清单。
 */
export const remarkPlugins = [remarkGfm, remarkMath, remarkDisplayMathFromDoubleDollar];

export const rehypePlugins = [rehypeKatex];
