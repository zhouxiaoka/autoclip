/**
 * 浏览器「翻译此页」（Chrome / Edge / Safari）会把文本节点替换成 <font> 包裹的译文。
 * React 之后对这些节点做 removeChild / insertBefore 时，节点已不在它记录的父节点下，
 * 浏览器抛 NotFoundError，整棵树被 ErrorBoundary 卸载（issue #100：Docker Web 模式下
 * 海外用户开着翻译切换 LLM 提供商即崩）。
 *
 * 这里把这两个 DOM 操作降级为「节点已被外部脚本移动 → 跳过 / 追加到末尾」，
 * 代价是译文可能残留旧文案，但页面不会整体崩掉。做法同 facebook/react#11538 的官方建议。
 */

const GUARD_FLAG = '__autoclipDomTranslationGuard'

export function isPageTranslated(): boolean {
  if (typeof document === 'undefined') return false
  const html = document.documentElement
  return (
    html.classList.contains('translated-ltr') ||
    html.classList.contains('translated-rtl') ||
    // Safari / 部分 Chrome 版本不加 class，只能靠翻译注入的 <font> 结构判断
    !!document.querySelector('font[style*="vertical-align: inherit"] > font')
  )
}

export function isDomDisplacementError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    /removeChild|insertBefore/.test(message) &&
    /not a child of this node|NotFoundError/i.test(message)
  )
}

export function installDomTranslationGuard(): void {
  if (typeof Node === 'undefined') return
  const proto = Node.prototype as Node & Record<string, unknown>
  if (proto[GUARD_FLAG]) return
  proto[GUARD_FLAG] = true

  const originalRemoveChild = Node.prototype.removeChild
  Node.prototype.removeChild = function removeChild<T extends Node>(this: Node, child: T): T {
    if (child.parentNode !== this) {
      if (import.meta.env.DEV) {
        console.warn('[dom-guard] removeChild 跳过：节点已被页面翻译等外部脚本移动', child)
      }
      return child
    }
    return originalRemoveChild.call(this, child) as T
  }

  const originalInsertBefore = Node.prototype.insertBefore
  Node.prototype.insertBefore = function insertBefore<T extends Node>(
    this: Node,
    newNode: T,
    referenceNode: Node | null,
  ): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      if (import.meta.env.DEV) {
        console.warn('[dom-guard] insertBefore 参考节点已被移动，改为追加到末尾', referenceNode)
      }
      return originalInsertBefore.call(this, newNode, null) as T
    }
    return originalInsertBefore.call(this, newNode, referenceNode) as T
  }
}
