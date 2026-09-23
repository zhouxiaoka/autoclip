import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import VideoCategoryPicker from '../src/components/VideoCategoryPicker'

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

const undefinedHtml = renderToStaticMarkup(
  <VideoCategoryPicker categories={undefined} selectedCategory="default" onSelect={() => {}} />
)
assert(undefinedHtml.includes('Default') || undefinedHtml.includes('默认'), `undefined categories did not render defaults: ${undefinedHtml}`)
assert(undefinedHtml.includes('Education') || undefinedHtml.includes('知识科普'), `missing knowledge chip: ${undefinedHtml}`)

const nullHtml = renderToStaticMarkup(
  <VideoCategoryPicker categories={null} selectedCategory="" onSelect={() => {}} />
)
assert(nullHtml.includes('Default') || nullHtml.includes('默认'), `null categories did not render defaults: ${nullHtml}`)

const emptyHtml = renderToStaticMarkup(
  <VideoCategoryPicker categories={[]} selectedCategory="" onSelect={() => {}} />
)
assert(!emptyHtml.includes('默认') && !emptyHtml.includes('Default'), `empty list should stay empty: ${emptyHtml}`)

const apiHtml = renderToStaticMarkup(
  <VideoCategoryPicker
    categories={[{ value: 'knowledge', name: '知识科普', description: '', icon: '📚', color: '#52c41a' }]}
    selectedCategory="knowledge"
    onSelect={() => {}}
  />
)
assert(apiHtml.includes('Education') || apiHtml.includes('知识科普'), `api list not rendered: ${apiHtml}`)
assert(!apiHtml.includes('Default') && !apiHtml.includes('>默认<'), `api list should not add defaults: ${apiHtml}`)

console.log('category picker rendered with undefined, null, empty, and api categories')
