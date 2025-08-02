"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var React = _interopRequireWildcard(require("react"));
var _util = require("../util");
const fillTitle = (columns, columnTitleProps) => {
  const finalColumns = columns.map(column => {
    const cloneColumn = Object.assign({}, column);
    cloneColumn.title = (0, _util.renderColumnTitle)(column.title, columnTitleProps);
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
var _default = exports.default = useTitleColumns;