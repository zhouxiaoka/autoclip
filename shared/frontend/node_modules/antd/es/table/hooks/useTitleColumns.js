import * as React from 'react';
import { renderColumnTitle } from '../util';
const fillTitle = (columns, columnTitleProps) => {
  const finalColumns = columns.map(column => {
    const cloneColumn = Object.assign({}, column);
    cloneColumn.title = renderColumnTitle(column.title, columnTitleProps);
    if ('children' in cloneColumn) {
      cloneColumn.children = fillTitle(cloneColumn.children, columnTitleProps);
    }
    return cloneColumn;
  });
  return finalColumns;
};
const useTitleColumns = columnTitleProps => {
  const filledColumns = React.useCallback(columns => fillTitle(columns, columnTitleProps), [columnTitleProps]);
  return [filledColumns];
};
export default useTitleColumns;