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
import { devUseWarning } from '../_util/warning';
import { useLocale } from '../locale';
import DefaultEmptyImg from './empty';
import SimpleEmptyImg from './simple';
import useStyle from './style';
import { useComponentConfig } from '../config-provider/context';
const defaultEmptyImg = /*#__PURE__*/React.createElement(DefaultEmptyImg, null);
const simpleEmptyImg = /*#__PURE__*/React.createElement(SimpleEmptyImg, null);
const Empty = props => {
  const {
      className,
      rootClassName,
      prefixCls: customizePrefixCls,
      image = defaultEmptyImg,
      description,
      children,
      imageStyle,
      style,
      classNames: emptyClassNames,
      styles
    } = props,
    restProps = __rest(props, ["className", "rootClassName", "prefixCls", "image", "description", "children", "imageStyle", "style", "classNames", "styles"]);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle,
    classNames: contextClassNames,
    styles: contextStyles
  } = useComponentConfig('empty');
  const prefixCls = getPrefixCls('empty', customizePrefixCls);
  const [wrapCSSVar, hashId, cssVarCls] = useStyle(prefixCls);
  const [locale] = useLocale('Empty');
  const des = typeof description !== 'undefined' ? description : locale === null || locale === void 0 ? void 0 : locale.description;
  const alt = typeof des === 'string' ? des : 'empty';
  let imageNode = null;
  if (typeof image === 'string') {
    imageNode = /*#__PURE__*/React.createElement("img", {
      alt: alt,
      src: image
    });
  } else {
    imageNode = image;
  }
  // ============================= Warning ==============================
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Empty');
    [['imageStyle', 'styles: { image: {} }']].forEach(([deprecatedName, newName]) => {
      warning.deprecated(!(deprecatedName in props), deprecatedName, newName);
    });
  }
  return wrapCSSVar(/*#__PURE__*/React.createElement("div", Object.assign({
    className: classNames(hashId, cssVarCls, prefixCls, contextClassName, {
      [`${prefixCls}-normal`]: image === simpleEmptyImg,
      [`${prefixCls}-rtl`]: direction === 'rtl'
    }, className, rootClassName, contextClassNames.root, emptyClassNames === null || emptyClassNames === void 0 ? void 0 : emptyClassNames.root),
    style: Object.assign(Object.assign(Object.assign(Object.assign({}, contextStyles.root), contextStyle), styles === null || styles === void 0 ? void 0 : styles.root), style)
  }, restProps), /*#__PURE__*/React.createElement("div", {
    className: classNames(`${prefixCls}-image`, contextClassNames.image, emptyClassNames === null || emptyClassNames === void 0 ? void 0 : emptyClassNames.image),
    style: Object.assign(Object.assign(Object.assign({}, imageStyle), contextStyles.image), styles === null || styles === void 0 ? void 0 : styles.image)
  }, imageNode), des && (/*#__PURE__*/React.createElement("div", {
    className: classNames(`${prefixCls}-description`, contextClassNames.description, emptyClassNames === null || emptyClassNames === void 0 ? void 0 : emptyClassNames.description),
    style: Object.assign(Object.assign({}, contextStyles.description), styles === null || styles === void 0 ? void 0 : styles.description)
  }, des)), children && (/*#__PURE__*/React.createElement("div", {
    className: classNames(`${prefixCls}-footer`, contextClassNames.footer, emptyClassNames === null || emptyClassNames === void 0 ? void 0 : emptyClassNames.footer),
    style: Object.assign(Object.assign({}, contextStyles.footer), styles === null || styles === void 0 ? void 0 : styles.footer)
  }, children))));
};
Empty.PRESENTED_IMAGE_DEFAULT = defaultEmptyImg;
Empty.PRESENTED_IMAGE_SIMPLE = simpleEmptyImg;
if (process.env.NODE_ENV !== 'production') {
  Empty.displayName = 'Empty';
}
export default Empty;