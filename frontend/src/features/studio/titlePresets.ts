import type { Draft } from './types'
import comicThumbnail from '../../assets/title-presets/comic.webp'
import neonThumbnail from '../../assets/title-presets/neon.webp'
import arenaThumbnail from '../../assets/title-presets/arena.webp'
import pixelThumbnail from '../../assets/title-presets/pixel.webp'
import editorialThumbnail from '../../assets/title-presets/editorial.webp'
import frostedThumbnail from '../../assets/title-presets/frosted.webp'

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

// Design references help users identify the look; TitleArtwork renders their actual text.
export const titleDesignThumbnails: Partial<Record<NonNullable<Draft['title_style']>, string>> = {
  comic: comicThumbnail,
  neon: neonThumbnail,
  arena: arenaThumbnail,
  pixel: pixelThumbnail,
  editorial: editorialThumbnail,
  frosted: frostedThumbnail,
}
