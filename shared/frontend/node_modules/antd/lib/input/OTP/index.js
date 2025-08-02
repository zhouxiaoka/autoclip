"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
var _useEvent = _interopRequireDefault(require("rc-util/lib/hooks/useEvent"));
var _pickAttrs = _interopRequireDefault(require("rc-util/lib/pickAttrs"));
var _statusUtils = require("../../_util/statusUtils");
var _warning = require("../../_util/warning");
var _configProvider = require("../../config-provider");
var _useSize = _interopRequireDefault(require("../../config-provider/hooks/useSize"));
var _context = require("../../form/context");
var _otp = _interopRequireDefault(require("../style/otp"));
var _OTPInput = _interopRequireDefault(require("./OTPInput"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function strToArr(str) {
  return (str || '').split('');
}
const Separator = props => {
  const {
    index,
    prefixCls,
    separator
  } = props;
  const separatorNode = typeof separator === 'function' ? separator(index) : separator;
  if (!separatorNode) {
    return null;
  }
  return /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-separator`
  }, separatorNode);
};
const OTP = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      prefixCls: customizePrefixCls,
      length = 6,
      size: customSize,
      defaultValue,
      value,
      onChange,
      formatter,
      separator,
      variant,
      disabled,
      status: customStatus,
      autoFocus,
      mask,
      type,
      onInput,
      inputMode
    } = props,
    restProps = __rest(props, ["prefixCls", "length", "size", "defaultValue", "value", "onChange", "formatter", "separator", "variant", "disabled", "status", "autoFocus", "mask", "type", "onInput", "inputMode"]);
  if (process.env.NODE_ENV !== 'production') {
    const warning = (0, _warning.devUseWarning)('Input.OTP');
    process.env.NODE_ENV !== "production" ? warning(!(typeof mask === 'string' && mask.length > 1), 'usage', '`mask` prop should be a single character.') : void 0;
  }
  const {
    getPrefixCls,
    direction
  } = React.useContext(_configProvider.ConfigContext);
  const prefixCls = getPrefixCls('otp', customizePrefixCls);
  const domAttrs = (0, _pickAttrs.default)(restProps, {
    aria: true,
    data: true,
    attr: true
  });
  // ========================= Root =========================
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = (0, _otp.default)(prefixCls);
  // ========================= Size =========================
  const mergedSize = (0, _useSize.default)(ctx => customSize !== null && customSize !== void 0 ? customSize : ctx);
  // ======================== Status ========================
  const formContext = React.useContext(_context.FormItemInputContext);
  const mergedStatus = (0, _statusUtils.getMergedStatus)(formContext.status, customStatus);
  const proxyFormContext = React.useMemo(() => Object.assign(Object.assign({}, formContext), {
    status: mergedStatus,
    hasFeedback: false,
    feedbackIcon: null
  }), [formContext, mergedStatus]);
  // ========================= Refs =========================
  const containerRef = React.useRef(null);
  const refs = React.useRef({});
  React.useImperativeHandle(ref, () => ({
    focus: () => {
      var _a;
      (_a = refs.current[0]) === null || _a === void 0 ? void 0 : _a.focus();
    },
    blur: () => {
      var _a;
      for (let i = 0; i < length; i += 1) {
        (_a = refs.current[i]) === null || _a === void 0 ? void 0 : _a.blur();
      }
    },
    nativeElement: containerRef.current
  }));
  // ======================= Formatter ======================
  const internalFormatter = txt => formatter ? formatter(txt) : txt;
  // ======================== Values ========================
  const [valueCells, setValueCells] = React.useState(() => strToArr(internalFormatter(defaultValue || '')));
  React.useEffect(() => {
    if (value !== undefined) {
      setValueCells(strToArr(value));
    }
  }, [value]);
  const triggerValueCellsChange = (0, _useEvent.default)(nextValueCells => {
    setValueCells(nextValueCells);
    if (onInput) {
      onInput(nextValueCells);
    }
    // Trigger if all cells are filled
    if (onChange && nextValueCells.length === length && nextValueCells.every(c => c) && nextValueCells.some((c, index) => valueCells[index] !== c)) {
      onChange(nextValueCells.join(''));
    }
  });
  const patchValue = (0, _useEvent.default)((index, txt) => {
    let nextCells = (0, _toConsumableArray2.default)(valueCells);
    // Fill cells till index
    for (let i = 0; i < index; i += 1) {
      if (!nextCells[i]) {
        nextCells[i] = '';
      }
    }
    if (txt.length <= 1) {
      nextCells[index] = txt;
    } else {
      nextCells = nextCells.slice(0, index).concat(strToArr(txt));
    }
    nextCells = nextCells.slice(0, length);
    // Clean the last empty cell
    for (let i = nextCells.length - 1; i >= 0; i -= 1) {
      if (nextCells[i]) {
        break;
      }
      nextCells.pop();
    }
    // Format if needed
    const formattedValue = internalFormatter(nextCells.map(c => c || ' ').join(''));
    nextCells = strToArr(formattedValue).map((c, i) => {
      if (c === ' ' && !nextCells[i]) {
        return nextCells[i];
      }
      return c;
    });
    return nextCells;
  });
  // ======================== Change ========================
  const onInputChange = (index, txt) => {
    var _a;
    const nextCells = patchValue(index, txt);
    const nextIndex = Math.min(index + txt.length, length - 1);
    if (nextIndex !== index && nextCells[index] !== undefined) {
      (_a = refs.current[nextIndex]) === null || _a === void 0 ? void 0 : _a.focus();
    }
    triggerValueCellsChange(nextCells);
  };
  const onInputActiveChange = nextIndex => {
    var _a;
    (_a = refs.current[nextIndex]) === null || _a === void 0 ? void 0 : _a.focus();
  };
  // ======================== Render ========================
  const inputSharedProps = {
    variant,
    disabled,
    status: mergedStatus,
    mask,
    type,
    inputMode
  };
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({}, domAttrs, {
    ref: containerRef,
    className: (0, _classnames.default)(prefixCls, {
      [`${prefixCls}-sm`]: mergedSize === 'small',
      [`${prefixCls}-lg`]: mergedSize === 'large',
      [`${prefixCls}-rtl`]: direction === 'rtl'
    }, cssVarCls, hashId),
    role: "group"
  }), /*#__PURE__*/React.createElement(_context.FormItemInputContext.Provider, {
    value: proxyFormContext
  }, Array.from({
    length
  }).map((_, index) => {
    const key = `otp-${index}`;
    const singleValue = valueCells[index] || '';
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement(_OTPInput.default, Object.assign({
      ref: inputEle => {
        refs.current[index] = inputEle;
      },
      index: index,
      size: mergedSize,
      htmlSize: 1,
      className: `${prefixCls}-input`,
      onChange: onInputChange,
      value: singleValue,
      onActiveChange: onInputActiveChange,
      autoFocus: index === 0 && autoFocus
    }, inputSharedProps)), index < length - 1 && (/*#__PURE__*/React.createElement(Separator, {
      separator: separator,
      index: index,
      prefixCls: prefixCls
    })));
  }))));
});
var _default = exports.default = OTP;