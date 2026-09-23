import assert from 'node:assert/strict'
import test from 'node:test'
import {
  applyCategoryResponse,
  categoryOptions,
  DEFAULT_VIDEO_CATEGORIES,
} from '../src/utils/videoCategories.ts'

const apiList = [
  {
    value: 'knowledge',
    name: '知识科普',
    description: 'from api',
    icon: '📚',
    color: '#52c41a',
  },
]

test('missing categories fall back to the built-in list', () => {
  for (const response of [undefined, null, {}, { categories: null }, { categories: undefined }, { categories: { en: [] } }]) {
    const resolved = applyCategoryResponse(response)
    assert.deepEqual(resolved.categories, DEFAULT_VIDEO_CATEGORIES)
    assert.equal(resolved.selectedCategory, 'default')
    assert.equal(typeof resolved.categories.map, 'function')
  }
})

test('a real category array is preserved, including an empty list', () => {
  const withDefault = applyCategoryResponse({ categories: apiList, default_category: 'knowledge' })
  assert.deepEqual(withDefault.categories, apiList)
  assert.equal(withDefault.selectedCategory, 'knowledge')

  const empty = applyCategoryResponse({ categories: [] })
  assert.deepEqual(empty.categories, [])
  assert.equal(empty.selectedCategory, undefined)
  assert.deepEqual(categoryOptions([]), [])
})

test('categoryOptions never returns a non-array', () => {
  assert.equal(categoryOptions(null), DEFAULT_VIDEO_CATEGORIES)
  assert.equal(categoryOptions(undefined), DEFAULT_VIDEO_CATEGORIES)
  assert.equal(typeof categoryOptions(null).map, 'function')
  assert.deepEqual(categoryOptions(apiList), apiList)
})
