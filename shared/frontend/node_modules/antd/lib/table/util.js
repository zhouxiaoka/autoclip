"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getColumnKey = void 0;
exports.getColumnPos = getColumnPos;
exports.safeColumnTitle = exports.renderColumnTitle = void 0;
const getColumnKey = (column, defaultKey) => {
  if ('key' in column && column.key !== undefined && column.key !== null) {
    return column.key;
  }
  if (column.dataIndex) {
    return Array.isArray(column.dataIndex) ? column.dataIndex.join('.') : column.dataIndex;
  }
  return defaultKey;
};
exports.getColumnKey = getColumnKey;
function getColumnPos(index, pos) {
  return pos ? `${pos}-${index}` : `${index}`;
}
const renderColumnTitle = (title, props) => {
  if (typeof title === 'function') {
    return title(props);
  }
  return title;
};
/**
 * Safe get column title
 *
 * Should filter [object Object]
 *
 * @param title
 */
exports.renderColumnTitle = renderColumnTitle;
const safeColumnTitle = (title, props) => {
  const res = renderColumnTitle(title, props);
  if (Object.prototype.toString.call(res) === '[object Object]') {
    return '';
  }
  return res;
};
exports.safeColumnTitle = safeColumnTitle;