"use client";

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
import raf from "rc-util/es/raf";
import { ConfigContext } from '../../config-provider';
import Input from '../Input';
const OTPInput = /*#__PURE__*/React.forwardRef((props, ref) => {
  const {
      className,
      value,
      onChange,
      onActiveChange,
      index,
      mask
    } = props,
    restProps = __rest(props, ["className", "value", "onChange", "onActiveChange", "index", "mask"]);
  const {
    getPrefixCls
  } = React.useContext(ConfigContext);
  const prefixCls = getPrefixCls('otp');
  const maskValue = typeof mask === 'string' ? mask : value;
  // ========================== Ref ===========================
  const inputRef = React.useRef(null);
  React.useImperativeHandle(ref, () => inputRef.current);
  // ========================= Input ==========================
  const onInternalChange = e => {
    onChange(index, e.target.value);
  };
  // ========================= Focus ==========================
  const syncSelection = () => {
    raf(() => {
      var _a;
      const inputEle = (_a = inputRef.current) === null || _a === void 0 ? void 0 : _a.input;
      if (document.activeElement === inputEle && inputEle) {
        inputEle.select();
      }
    });
  };
  // ======================== Keyboard ========================
  const onInternalKeyDown = event => {
    const {
      key,
      ctrlKey,
      metaKey
    } = event;
    if (key === 'ArrowLeft') {
      onActiveChange(index - 1);
    } else if (key === 'ArrowRight') {
      onActiveChange(index + 1);
    } else if (key === 'z' && (ctrlKey || metaKey)) {
      event.preventDefault();
    }
    syncSelection();
  };
  const onInternalKeyUp = e => {
    if (e.key === 'Backspace' && !value) {
      onActiveChange(index - 1);
    }
    syncSelection();
  };
  // ========================= Render =========================
  return /*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-input-wrapper`,
    role: "presentation"
  }, mask && value !== '' && value !== undefined && (/*#__PURE__*/React.createElement("span", {
    className: `${prefixCls}-mask-icon`,
    "aria-hidden": "true"
  }, maskValue)), /*#__PURE__*/React.createElement(Input, Object.assign({
    "aria-label": `OTP Input ${index + 1}`,
    type: mask === true ? 'password' : 'text'
  }, restProps, {
    ref: inputRef,
    value: value,
    onInput: onInternalChange,
    onFocus: syncSelection,
    onKeyDown: onInternalKeyDown,
    onKeyUp: onInternalKeyUp,
    onMouseDown: syncSelection,
    onMouseUp: syncSelection,
    className: classNames(className, {
      [`${prefixCls}-mask-input`]: mask
    })
  })));
});
export default OTPInput;