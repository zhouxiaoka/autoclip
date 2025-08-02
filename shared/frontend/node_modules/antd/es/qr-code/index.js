"use client";

var __rest = this && this.__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
import React, { useContext } from 'react';
import { QRCodeCanvas, QRCodeSVG } from '@rc-component/qrcode';
import classNames from 'classnames';
import omit from "rc-util/es/omit";
import pickAttrs from "rc-util/es/pickAttrs";
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider';
import { useLocale } from '../locale';
import { useToken } from '../theme/internal';
import QRcodeStatus from './QrcodeStatus';
import useStyle from './style/index';
const QRCode = props => {
  var _a, _b, _c, _d;
  const [, token] = useToken();
  const {
      value,
      type = 'canvas',
      icon = '',
      size = 160,
      iconSize,
      color = token.colorText,
      errorLevel = 'M',
      status = 'active',
      bordered = true,
      onRefresh,
      style,
      className,
      rootClassName,
      prefixCls: customizePrefixCls,
      bgColor = 'transparent',
      statusRender
    } = props,
    rest = __rest(props, ["value", "type", "icon", "size", "iconSize", "color", "errorLevel", "status", "bordered", "onRefresh", "style", "className", "rootClassName", "prefixCls", "bgColor", "statusRender"]);
  const {
    getPrefixCls
  } = useContext(ConfigContext);
  const prefixCls = getPrefixCls('qrcode', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const imageSettings = {
    src: icon,
    x: undefined,
    y: undefined,
    height: typeof iconSize === 'number' ? iconSize : (_a = iconSize === null || iconSize === void 0 ? void 0 : iconSize.height) !== null && _a !== void 0 ? _a : 40,
    width: typeof iconSize === 'number' ? iconSize : (_b = iconSize === null || iconSize === void 0 ? void 0 : iconSize.width) !== null && _b !== void 0 ? _b : 40,
    excavate: true,
    crossOrigin: 'anonymous'
  };
  const a11yProps = pickAttrs(rest, true);
  const restProps = omit(rest, Object.keys(a11yProps));
  const qrCodeProps = Object.assign({
    value,
    size,
    level: errorLevel,
    bgColor,
    fgColor: color,
    style: {
      width: style === null || style === void 0 ? void 0 : style.width,
      height: style === null || style === void 0 ? void 0 : style.height
    },
    imageSettings: icon ? imageSettings : undefined
  }, a11yProps);
  const [locale] = useLocale('QRCode');
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('QRCode');
    process.env.NODE_ENV !== "production" ? warning(!!value, 'usage', 'need to receive `value` props') : void 0;
    process.env.NODE_ENV !== "production" ? warning(!(icon && errorLevel === 'L'), 'usage', 'ErrorLevel `L` is not recommended to be used with `icon`, for scanning result would be affected by low level.') : void 0;
  }
  if (!value) {
    return null;
  }
  const mergedCls = classNames(prefixCls, className, rootClassName, hashId, cssVarCls, {
    [`${prefixCls}-borderless`]: !bordered
  });
  const mergedStyle = Object.assign(Object.assign({
    backgroundColor: bgColor
  }, style), {
    width: (_c = style === null || style === void 0 ? void 0 : style.width) !== null && _c !== void 0 ? _c : size,
    height: (_d = style === null || style === void 0 ? void 0 : style.height) !== null && _d !== void 0 ? _d : size
  });
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({}, restProps, {
    className: mergedCls,
    style: mergedStyle
  }), status !== 'active' && (/*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-mask`
  }, /*#__PURE__*/React.createElement(QRcodeStatus, {
    prefixCls: prefixCls,
    locale: locale,
    status: status,
    onRefresh: onRefresh,
    statusRender: statusRender
  }))), type === 'canvas' ? /*#__PURE__*/React.createElement(QRCodeCanvas, Object.assign({}, qrCodeProps)) : /*#__PURE__*/React.createElement(QRCodeSVG, Object.assign({}, qrCodeProps))));
};
if (process.env.NODE_ENV !== 'production') {
  QRCode.displayName = 'QRCode';
}
export default QRCode;