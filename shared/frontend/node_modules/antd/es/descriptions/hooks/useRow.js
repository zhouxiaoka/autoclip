var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import { useMemo } from 'react';
import { devUseWarning } from '../../_util/warning';
// Calculate the sum of span in a row
function getCalcRows(rowItems, mergedColumn) {
  let rows = [];
  let tmpRow = [];
  let exceed = false;
  let count = 0;
  rowItems.filter(n => n).forEach(rowItem => {
    const {
        filled
      } = rowItem,
      restItem = __rest(rowItem, ["filled"]);
    if (filled) {
      tmpRow.push(restItem);
      rows.push(tmpRow);
      // reset
      tmpRow = [];
      count = 0;
      return;
    }
    const restSpan = mergedColumn - count;
    count += rowItem.span || 1;
    if (count >= mergedColumn) {
      if (count > mergedColumn) {
        exceed = true;
        tmpRow.push(Object.assign(Object.assign({}, restItem), {
          span: restSpan
        }));
      } else {
        tmpRow.push(restItem);
      }
      rows.push(tmpRow);
      // reset
      tmpRow = [];
      count = 0;
    } else {
      tmpRow.push(restItem);
    }
  });
  if (tmpRow.length > 0) {
    rows.push(tmpRow);
  }
  rows = rows.map(rows => {
    const count = rows.reduce((acc, item) => acc + (item.span || 1), 0);
    if (count < mergedColumn) {
      // If the span of the last element in the current row is less than the column, then add its span to the remaining columns
      const last = rows[rows.length - 1];
      last.span = mergedColumn - (count - (last.span || 1));
      return rows;
    }
    return rows;
  });
  return [rows, exceed];
}
const useRow = (mergedColumn, items) => {
  const [rows, exceed] = useMemo(() => getCalcRows(items, mergedColumn), [items, mergedColumn]);
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Descriptions');
    process.env.NODE_ENV !== "production" ? warning(!exceed, 'usage', 'Sum of column `span` in a line not match `column` of Descriptions.') : void 0;
  }
  return rows;
};
export default useRow;