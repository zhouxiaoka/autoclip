"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import * as React from 'react';
import classNames from 'classnames';
import useEvent from "rc-util/es/hooks/useEvent";
import pickAttrs from "rc-util/es/pickAttrs";
import { getMergedStatus } from '../../_util/statusUtils';
import { devUseWarning } from '../../_util/warning';
import { ConfigContext } from '../../config-provider';
import useSize from '../../config-provider/hooks/useSize';
import { FormItemInputContext } from '../../form/context';
import useStyle from '../style/otp';
import OTPInput from './OTPInput';
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
    const warning = devUseWarning('Input.OTP');
    process.env.NODE_ENV !== "production" ? warning(!(typeof mask === 'string' && mask.length > 1), 'usage', '`mask` prop should be a single character.') : void 0;
  }
  const {
    getPrefixCls,
    direction
  } = React.useContext(ConfigContext);
  const prefixCls = getPrefixCls('otp', customizePrefixCls);
  const domAttrs = pickAttrs(restProps, {
    aria: true,
    data: true,
    attr: true
  });
  // ========================= Root =========================
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  // ========================= Size =========================
  const mergedSize = useSize(ctx => customSize !== null && customSize !== void 0 ? customSize : ctx);
  // ======================== Status ========================
  const formContext = React.useContext(FormItemInputContext);
  const mergedStatus = getMergedStatus(formContext.status, customStatus);
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
  const triggerValueCellsChange = useEvent(nextValueCells => {
    setValueCells(nextValueCells);
    if (onInput) {
      onInput(nextValueCells);
    }
    // Trigger if all cells are filled
    if (onChange && nextValueCells.length === length && nextValueCells.every(c => c) && nextValueCells.some((c, index) => valueCells[index] !== c)) {
      onChange(nextValueCells.join(''));
    }
  });
  const patchValue = useEvent((index, txt) => {
    let nextCells = _toConsumableArray(valueCells);
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
    className: classNames(prefixCls, {
      [`${prefixCls}-sm`]: mergedSize === 'small',
      [`${prefixCls}-lg`]: mergedSize === 'large',
      [`${prefixCls}-rtl`]: direction === 'rtl'
    }, cssVarCls, hashId),
    role: "group"
  }), /*#__PURE__*/React.createElement(FormItemInputContext.Provider, {
    value: proxyFormContext
  }, Array.from({
    length
  }).map((_, index) => {
    const key = `otp-${index}`;
    const singleValue = valueCells[index] || '';
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement(OTPInput, Object.assign({
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
export default OTP;