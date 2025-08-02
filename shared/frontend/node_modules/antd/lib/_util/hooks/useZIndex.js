"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.useZIndex = exports.containerBaseZIndexOffset = exports.consumerBaseZIndexOffset = exports.CONTAINER_MAX_OFFSET = void 0;
var _react = _interopRequireDefault(require("react"));
var _useToken = _interopRequireDefault(require("../../theme/useToken"));
var _warning = require("../warning");
var _zindexContext = _interopRequireDefault(require("../zindexContext"));
// Z-Index control range
// Container: 1000 + offset 100 (max base + 10 * offset = 2000)
// Popover: offset 50
// Notification: Container Max zIndex + componentOffset
const CONTAINER_OFFSET = 100;
const CONTAINER_OFFSET_MAX_COUNT = 10;
const CONTAINER_MAX_OFFSET = exports.CONTAINER_MAX_OFFSET = CONTAINER_OFFSET * CONTAINER_OFFSET_MAX_COUNT;
/**
 * Static function will default be the `CONTAINER_MAX_OFFSET`.
 * But it still may have children component like Select, Dropdown.
 * So the warning zIndex should exceed the `CONTAINER_MAX_OFFSET`.
 */
const CONTAINER_MAX_OFFSET_WITH_CHILDREN = CONTAINER_MAX_OFFSET + CONTAINER_OFFSET;
const containerBaseZIndexOffset = exports.containerBaseZIndexOffset = {
  Modal: CONTAINER_OFFSET,
  Drawer: CONTAINER_OFFSET,
  Popover: CONTAINER_OFFSET,
  Popconfirm: CONTAINER_OFFSET,
  Tooltip: CONTAINER_OFFSET,
  Tour: CONTAINER_OFFSET,
  FloatButton: CONTAINER_OFFSET
};
const consumerBaseZIndexOffset = exports.consumerBaseZIndexOffset = {
  SelectLike: 50,
  Dropdown: 50,
  DatePicker: 50,
  Menu: 50,
  ImagePreview: 1
};
function isContainerType(type) {
  return type in containerBaseZIndexOffset;
}
const useZIndex = (componentType, customZIndex) => {
  const [, token] = (0, _useToken.default)();
  const parentZIndex = _react.default.useContext(_zindexContext.default);
  const isContainer = isContainerType(componentType);
  let result;
  if (customZIndex !== undefined) {
    result = [customZIndex, customZIndex];
  } else {
    let zIndex = parentZIndex !== null && parentZIndex !== void 0 ? parentZIndex : 0;
    if (isContainer) {
      zIndex +=
      // Use preset token zIndex by default but not stack when has parent container
      (parentZIndex ? 0 : token.zIndexPopupBase) +
      // Container offset
      containerBaseZIndexOffset[componentType];
    } else {
      zIndex += consumerBaseZIndexOffset[componentType];
    }
    result = [parentZIndex === undefined ? customZIndex : zIndex, zIndex];
  }
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)(componentType);
    const maxZIndex = token.zIndexPopupBase + CONTAINER_MAX_OFFSET_WITH_CHILDREN;
    const currentZIndex = result[0] || 0;
    process.env.NODE_ENV !== "production" ? warning(customZIndex !== undefined || currentZIndex <= maxZIndex, 'usage', '`zIndex` is over design token `zIndexPopupBase` too much. It may cause unexpected override.') : void 0;
  }
  return result;
};
exports.useZIndex = useZIndex;