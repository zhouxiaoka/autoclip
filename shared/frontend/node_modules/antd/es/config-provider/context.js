import * as React from 'react';
export const defaultPrefixCls = 'ant';
export const defaultIconPrefixCls = 'anticon';
export const Variants = ['outlined', 'borderless', 'filled', 'underlined'];
const defaultGetPrefixCls = (suffixCls, customizePrefixCls) => {
  if (customizePrefixCls) {
    return customizePrefixCls;
  }
  return suffixCls ? `${defaultPrefixCls}-${suffixCls}` : defaultPrefixCls;
};
// zombieJ: 🚨 Do not pass `defaultRenderEmpty` here since it will cause circular dependency.
export const ConfigContext = /*#__PURE__*/React.createContext({
  // We provide a default function for Context without provider
  getPrefixCls: defaultGetPrefixCls,
  iconPrefixCls: defaultIconPrefixCls
});
export const {
  Consumer: ConfigConsumer
} = ConfigContext;
const EMPTY_OBJECT = {};
/**
 * Get ConfigProvider configured component props.
 * This help to reduce bundle size for saving `?.` operator.
 * Do not use as `useMemo` deps since we do not cache the object here.
 *
 * NOTE: not refactor this with `useMemo` since memo will cost another memory space,
 * which will waste both compare calculation & memory.
 */
export function useComponentConfig(propName) {
  const context = React.useContext(ConfigContext);
  const {
    getPrefixCls,
    direction,
    getPopupContainer
  } = context;
  const propValue = context[propName];
  return Object.assign(Object.assign({
    classNames: EMPTY_OBJECT,
    styles: EMPTY_OBJECT
  }, propValue), {
    getPrefixCls,
    direction,
    getPopupContainer
  });
}