"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _rcUtil = require("rc-util");
const EMPTY_KEYS = [];
function filterKeys(keys, dataKeys) {
  const filteredKeys = keys.filter(key => dataKeys.has(key));
  return keys.length === filteredKeys.length ? keys : filteredKeys;
}
function flattenKeys(keys) {
  return Array.from(keys).join(';');
}
function useSelection(leftDataSource, rightDataSource, selectedKeys) {
  // Prepare `dataSource` keys
  const [leftKeys, rightKeys] = React.useMemo(() => [new Set(leftDataSource.map(src => src === null || src === void 0 ? void 0 : src.key)), new Set(rightDataSource.map(src => src === null || src === void 0 ? void 0 : src.key))], [leftDataSource, rightDataSource]);
  // Selected Keys
  const [mergedSelectedKeys, setMergedSelectedKeys] = (0, _rcUtil.useMergedState)(EMPTY_KEYS, {
    value: selectedKeys
  });
  const sourceSelectedKeys = React.useMemo(() => filterKeys(mergedSelectedKeys, leftKeys), [mergedSelectedKeys, leftKeys]);
  const targetSelectedKeys = React.useMemo(() => filterKeys(mergedSelectedKeys, rightKeys), [mergedSelectedKeys, rightKeys]);
  // // Reset when data changed
  React.useEffect(() => {
    setMergedSelectedKeys([].concat((0, _toConsumableArray2.default)(filterKeys(mergedSelectedKeys, leftKeys)), (0, _toConsumableArray2.default)(filterKeys(mergedSelectedKeys, rightKeys))));
  }, [flattenKeys(leftKeys), flattenKeys(rightKeys)]);
  // Update keys
  const setSourceSelectedKeys = (0, _rcUtil.useEvent)(nextSrcKeys => {
    setMergedSelectedKeys([].concat((0, _toConsumableArray2.default)(nextSrcKeys), (0, _toConsumableArray2.default)(targetSelectedKeys)));
  });
  const setTargetSelectedKeys = (0, _rcUtil.useEvent)(nextTargetKeys => {
    setMergedSelectedKeys([].concat((0, _toConsumableArray2.default)(sourceSelectedKeys), (0, _toConsumableArray2.default)(nextTargetKeys)));
  });
  return [
  // Keys
  sourceSelectedKeys, targetSelectedKeys,
  // Updater
  setSourceSelectedKeys, setTargetSelectedKeys];
}
var _default = exports.default = useSelection;