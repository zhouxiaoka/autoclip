"use strict";
"use client";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _rcTable = require("rc-table");
/**
 * Same as `rc-table` but we modify trigger children update logic instead.
 */
const RcVirtualTable = (0, _rcTable.genVirtualTable)((prev, next) => {
  const {
    _renderTimes: prevRenderTimes
  } = prev;
  const {
    _renderTimes: nextRenderTimes
  } = next;
  return prevRenderTimes !== nextRenderTimes;
});
var _default = exports.default = RcVirtualTable;