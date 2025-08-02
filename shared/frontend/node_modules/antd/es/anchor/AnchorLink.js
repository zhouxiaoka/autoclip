"use client";

import * as React from 'react';
import classNames from 'classnames';
import { devUseWarning } from '../_util/warning';
import { ConfigContext } from '../config-provider';
import AnchorContext from './context';
const AnchorLink = props => {
  const {
    href,
    title,
    prefixCls: customizePrefixCls,
    children,
    className,
    target,
    replace
  } = props;
  const context = React.useContext(AnchorContext);
  const {
    registerLink,
    unregisterLink,
    scrollTo,
    onClick,
    activeLink,
    direction
  } = context || {};
  React.useEffect(() => {
    registerLink === null || registerLink === void 0 ? void 0 : registerLink(href);
    return () => {
      unregisterLink === null || unregisterLink === void 0 ? void 0 : unregisterLink(href);
    };
  }, [href]);
  const handleClick = e => {
    onClick === null || onClick === void 0 ? void 0 : onClick(e, {
      title,
      href
    });
    scrollTo === null || scrollTo === void 0 ? void 0 : scrollTo(href);
    // Support clicking on an anchor does not record history.
    if (e.defaultPrevented) {
      return;
    }
    const isExternalLink = href.startsWith('http://') || href.startsWith('https://');
    // Support external link
    if (isExternalLink) {
      if (replace) {
        e.preventDefault();
        window.location.replace(href);
      }
      return;
    }
    // Handling internal anchor link
    e.preventDefault();
    const historyMethod = replace ? 'replaceState' : 'pushState';
    window.history[historyMethod](null, '', href);
  };
  // =================== Warning =====================
  if (process.env.NODE_ENV !== 'production') {
    const warning = devUseWarning('Anchor.Link');
    process.env.NODE_ENV !== "production" ? warning(!children || direction !== 'horizontal', 'usage', '`Anchor.Link children` is not supported when `Anchor` direction is horizontal') : void 0;
  }
  const {
    getPrefixCls
  } = React.useContext(ConfigContext);
  const prefixCls = getPrefixCls('anchor', customizePrefixCls);
  const active = activeLink === href;
  const wrapperClassName = classNames(`${prefixCls}-link`, className, {
    [`${prefixCls}-link-active`]: active
  });
  const titleClassName = classNames(`${prefixCls}-link-title`, {
    [`${prefixCls}-link-title-active`]: active
  });
  return /*#__PURE__*/React.createElement("div", {
    className: wrapperClassName
  }, /*#__PURE__*/React.createElement("a", {
    className: titleClassName,
    href: href,
    title: typeof title === 'string' ? title : '',
    target: target,
    onClick: handleClick
  }, title), direction !== 'horizontal' ? children : null);
};
export default AnchorLink;