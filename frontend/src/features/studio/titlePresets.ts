import type { Draft } from './types'

export const titlePresets = [
  {value:'comic',label:'漫画冲击'}, {value:'neon',label:'荧光挑战'},
  {value:'arena',label:'竞技斜切'}, {value:'pixel',label:'像素街机'},
  {value:'editorial',label:'极简大字'}, {value:'frosted',label:'磨砂字幕卡'},
  {value:'impact',label:'高能大字'}, {value:'card',label:'简洁标题卡'},
  {value:'plain',label:'基础文字'},
] as const

export function isArtworkStyle(style: Draft['title_style']) {
  return ['comic','neon','arena','editorial','pixel','frosted'].includes(style || '')
}

export function titleVersions(style: Draft['title_style']) {
  const labels = {1:'原版',2:'加强版',3:'光泽版',4:'设计校准版',5:'冲击加强版',6:'首期优化版'} as const
  const versions: (keyof typeof labels)[] = style==='comic' ? [6,5,4,3,2,1]
    : style==='pixel'||style==='frosted' ? [6,3]
    : style==='editorial' ? [6,3,2] : [6,3,2,1]
  return versions.map(value=>({value,label:labels[value]}))
}
