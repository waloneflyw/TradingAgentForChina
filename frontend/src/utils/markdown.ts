import { marked } from 'marked'
import DOMPurify from 'dompurify'

/** Markdown → 消毒后的安全 HTML（marked 解析 + DOMPurify 清洗）。 */
export function renderMarkdown(md: string): string {
  if (!md) return ''
  const raw = marked.parse(md, { async: false, gfm: true, breaks: true }) as string
  return DOMPurify.sanitize(raw)
}

// —— 分析师报告专用：关键字高亮 + 多空/评级语义着色 ——

/** 关键词 → 语义类别（红涨绿跌 + 评级色）。长词在前，避免「看多」截胡「强烈看多」。 */
const TERM_CLASS: Record<string, string> = {
  强烈看多: 'bull', 看多: 'bull', 增持: 'bull', 买入: 'bull', 看涨: 'bull',
  利多: 'bull', 利好: 'bull', 净流入: 'bull', 放量: 'bull', 突破: 'bull',
  涨停: 'bull', 机会: 'bull', 走强: 'bull', 上攻: 'bull', 反弹: 'bull',
  强烈看空: 'bear', 看空: 'bear', 减持: 'bear', 卖出: 'bear', 看跌: 'bear',
  利空: 'bear', 净流出: 'bear', 缩量: 'bear', 跌破: 'bear', 跌停: 'bear',
  走弱: 'bear', 下探: 'bear', 承压: 'bear', 回调: 'bear', 风险: 'warn',
  持有: 'mid', 中性: 'mid', 观望: 'mid', 震荡: 'mid',
}

const KEYWORD_RE = new RegExp(
  `(${Object.keys(TERM_CLASS)
    .sort((a, b) => b.length - a.length)
    .join('|')})`,
  'g',
)

/** 递归遍历 DOM 文本节点，把关键词包成 <span class="kw kw-xxx">（不碰标签/代码块）。 */
function highlightTextNodes(node: Node): void {
  if (node.nodeType === 3) {
    const text = node.nodeValue || ''
    KEYWORD_RE.lastIndex = 0
    if (!KEYWORD_RE.test(text)) return
    KEYWORD_RE.lastIndex = 0

    const frag = document.createDocumentFragment()
    let last = 0
    let m: RegExpExecArray | null
    while ((m = KEYWORD_RE.exec(text))) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)))
      const span = document.createElement('span')
      span.className = `kw kw-${TERM_CLASS[m[1]]}`
      span.textContent = m[1]
      frag.appendChild(span)
      last = m.index + m[1].length
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)))
    node.parentNode?.replaceChild(frag, node)
  } else if (node.nodeType === 1 && !/^(SCRIPT|STYLE|CODE|PRE)$/i.test((node as Element).tagName)) {
    Array.from(node.childNodes).forEach(highlightTextNodes)
  }
}

/** 分析师报告专用渲染：markdown → 消毒 → 关键字高亮着色。 */
export function renderReportMarkdown(md: string): string {
  if (!md) return ''
  try {
    const raw = marked.parse(md, { async: false, gfm: true, breaks: true }) as string
    const dom = DOMPurify.sanitize(raw, {
      RETURN_DOM: true,
      RETURN_DOM_FRAGMENT: true,
    }) as unknown as DocumentFragment
    highlightTextNodes(dom)
    const tmp = document.createElement('div')
    tmp.appendChild(dom)
    return tmp.innerHTML
  } catch {
    return renderMarkdown(md)
  }
}

/** 从报告正文抽一句话摘要（去 markdown 语法，取首个句段，超长截断），作折叠标题下的副标题。 */
export function reportGist(md: string, maxLen = 64): string {
  if (!md) return ''
  const text = md
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_>`~|]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  const first = text.split(/[。；;！!？?]/)[0]
  return first.length > maxLen ? `${first.slice(0, maxLen)}…` : first
}
