"use strict";
"use client";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useClosable;
exports.pickClosable = pickClosable;
var _react = _interopRequireDefault(require("react"));
var _CloseOutlined = _interopRequireDefault(require("@ant-design/icons/CloseOutlined"));
var _pickAttrs = _interopRequireDefault(require("rc-util/lib/pickAttrs"));
var _locale = require("../../locale");
var _en_US = _interopRequireDefault(require("../../locale/en_US"));
var _extendsObject = _interopRequireDefault(require("../extendsObject"));
function pickClosable(context) {
  if (!context) {
    return undefined;
  }
  return {
    closable: context.closable,
    closeIcon: context.closeIcon
  };
}
/** Convert `closable` and `closeIcon` to config object */
function useClosableConfig(closableCollection) {
  const {
    closable,
    closeIcon
  } = closableCollection || {};
  return _react.default.useMemo(() => {
    if (
    // If `closable`, whatever rest be should be true
    !closable && (closable === false || closeIcon === false || closeIcon === null)) {
      return false;
    }
    if (closable === undefined && closeIcon === undefined) {
      return null;
    }
    let closableConfig = {
      closeIcon: typeof closeIcon !== 'boolean' && closeIcon !== null ? closeIcon : undefined
    };
    if (closable && typeof closable === 'object') {
      closableConfig = Object.assign(Object.assign({}, closableConfig), closable);
    }
    return closableConfig;
  }, [closable, closeIcon]);
}
/** Use same object to support `useMemo` optimization */
const EmptyFallbackCloseCollection = {};
function useClosable(propCloseCollection, contextCloseCollection, fallbackCloseCollection = EmptyFallbackCloseCollection) {
  // Align the `props`, `context` `fallback` to config object first
  const propCloseConfig = useClosableConfig(propCloseCollection);
  const contextCloseConfig = useClosableConfig(contextCloseCollection);
  const [contextLocale] = (0, _locale.useLocale)('global', _en_US.default.global);
  const closeBtnIsDisabled = typeof propCloseConfig !== 'boolean' ? !!(propCloseConfig === null || propCloseConfig === void 0 ? void 0 : propCloseConfig.disabled) : false;
  const mergedFallbackCloseCollection = _react.default.useMemo(() => Object.assign({
    closeIcon: /*#__PURE__*/_react.default.createElement(_CloseOutlined.default, null)
  }, fallbackCloseCollection), [fallbackCloseCollection]);
  // Use fallback logic to fill the config
  const mergedClosableConfig = _react.default.useMemo(() => {
    // ================ Props First ================
    // Skip if prop is disabled
    if (propCloseConfig === false) {
      return false;
    }
    if (propCloseConfig) {
      return (0, _extendsObject.default)(mergedFallbackCloseCollection, contextCloseConfig, propCloseConfig);
    }
    // =============== Context Second ==============
    // Skip if context is disabled
    if (contextCloseConfig === false) {
      return false;
    }
    if (contextCloseConfig) {
      return (0, _extendsObject.default)(mergedFallbackCloseCollection, contextCloseConfig);
    }
    // ============= Fallback Default ==============
    return !mergedFallbackCloseCollection.closable ? false : mergedFallbackCloseCollection;
  }, [propCloseConfig, contextCloseConfig, mergedFallbackCloseCollection]);
  // Calculate the final closeIcon
  return _react.default.useMemo(() => {
    if (mergedClosableConfig === false) {
      return [false, null, closeBtnIsDisabled, {}];
    }
    const {
      closeIconRender
    } = mergedFallbackCloseCollection;
    const {
      closeIcon
    } = mergedClosableConfig;
    let mergedCloseIcon = closeIcon;
    // Wrap the closeIcon with aria props
    const ariaOrDataProps = (0, _pickAttrs.default)(mergedClosableConfig, true);
    if (mergedCloseIcon !== null && mergedCloseIcon !== undefined) {
      // Wrap the closeIcon if needed
      if (closeIconRender) {
        mergedCloseIcon = closeIconRender(closeIcon);
      }
      mergedCloseIcon = /*#__PURE__*/_react.default.isValidElement(mergedCloseIcon) ? (/*#__PURE__*/_react.default.cloneElement(mergedCloseIcon, Object.assign({
        'aria-label': contextLocale.close
      }, ariaOrDataProps))) : (/*#__PURE__*/_react.default.createElement("span", Object.assign({
        "aria-label": contextLocale.close
      }, ariaOrDataProps), mergedCloseIcon));
    }
    return [true, mergedCloseIcon, closeBtnIsDisabled, ariaOrDataProps];
  }, [mergedClosableConfig, mergedFallbackCloseCollection]);
}