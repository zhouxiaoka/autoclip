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
var _extendsObject = _interopRequireDefault(require("../_util/extendsObject"));
var _responsiveObserver = require("../_util/responsiveObserver");
var _configProvider = require("../config-provider");
var _context = require("../config-provider/context");
var _defaultRenderEmpty = _interopRequireDefault(require("../config-provider/defaultRenderEmpty"));
var _useSize = _interopRequireDefault(require("../config-provider/hooks/useSize"));
var _grid = require("../grid");
var _useBreakpoint = _interopRequireDefault(require("../grid/hooks/useBreakpoint"));
var _pagination = _interopRequireDefault(require("../pagination"));
var _spin = _interopRequireDefault(require("../spin"));
var _context2 = require("./context");
var _Item = _interopRequireDefault(require("./Item"));
var _style = _interopRequireDefault(require("./style"));
var __rest = void 0 && (void 0).__rest || function (s, e) {
  var t = {};
  for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0) t[p] = s[p];
  if (s != null && typeof Object.getOwnPropertySymbols === "function") for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
    if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i])) t[p[i]] = s[p[i]];
  }
  return t;
};
function InternalList(props, ref) {
  const {
      pagination = false,
      prefixCls: customizePrefixCls,
      bordered = false,
      split = true,
      className,
      rootClassName,
      style,
      children,
      itemLayout,
      loadMore,
      grid,
      dataSource = [],
      size: customizeSize,
      header,
      footer,
      loading = false,
      rowKey,
      renderItem,
      locale
    } = props,
    rest = __rest(props, ["pagination", "prefixCls", "bordered", "split", "className", "rootClassName", "style", "children", "itemLayout", "loadMore", "grid", "dataSource", "size", "header", "footer", "loading", "rowKey", "renderItem", "locale"]);
  const paginationObj = pagination && typeof pagination === 'object' ? pagination : {};
  const [paginationCurrent, setPaginationCurrent] = React.useState(paginationObj.defaultCurrent || 1);
  const [paginationSize, setPaginationSize] = React.useState(paginationObj.defaultPageSize || 10);
  const {
    getPrefixCls,
    direction,
    className: contextClassName,
    style: contextStyle
  } = (0, _context.useComponentConfig)('list');
  const {
    renderEmpty
  } = React.useContext(_configProvider.ConfigContext);
  const defaultPaginationProps = {
    current: 1,
    total: 0,
    position: 'bottom'
  };
  const triggerPaginationEvent = eventName => (page, pageSize) => {
    var _a;
    setPaginationCurrent(page);
    setPaginationSize(pageSize);
    if (pagination) {
      (_a = pagination === null || pagination === void 0 ? void 0 : pagination[eventName]) === null || _a === void 0 ? void 0 : _a.call(pagination, page, pageSize);
    }
  };
  const onPaginationChange = triggerPaginationEvent('onChange');
  const onPaginationShowSizeChange = triggerPaginationEvent('onShowSizeChange');
  const renderInternalItem = (item, index) => {
    if (!renderItem) {
      return null;
    }
    let key;
    if (typeof rowKey === 'function') {
      key = rowKey(item);
    } else if (rowKey) {
      key = item[rowKey];
    } else {
      key = item.key;
    }
    if (!key) {
      key = `list-item-${index}`;
    }
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, renderItem(item, index));
  };
  const isSomethingAfterLastItem = !!(loadMore || pagination || footer);
  const prefixCls = getPrefixCls('list', customizePrefixCls);
  // Style
  const [wrapCSSVar, hashId, cssVarCls] = (0, _style.default)(prefixCls);
  let loadingProp = loading;
  if (typeof loadingProp === 'boolean') {
    loadingProp = {
      spinning: loadingProp
    };
  }
  const isLoading = !!(loadingProp === null || loadingProp === void 0 ? void 0 : loadingProp.spinning);
  const mergedSize = (0, _useSize.default)(customizeSize);
  // large => lg
  // small => sm
  let sizeCls = '';
  switch (mergedSize) {
    case 'large':
      sizeCls = 'lg';
      break;
    case 'small':
      sizeCls = 'sm';
      break;
    default:
      break;
  }
  const classString = (0, _classnames.default)(prefixCls, {
    [`${prefixCls}-vertical`]: itemLayout === 'vertical',
    [`${prefixCls}-${sizeCls}`]: sizeCls,
    [`${prefixCls}-split`]: split,
    [`${prefixCls}-bordered`]: bordered,
    [`${prefixCls}-loading`]: isLoading,
    [`${prefixCls}-grid`]: !!grid,
    [`${prefixCls}-something-after-last-item`]: isSomethingAfterLastItem,
    [`${prefixCls}-rtl`]: direction === 'rtl'
  }, contextClassName, className, rootClassName, hashId, cssVarCls);
  const paginationProps = (0, _extendsObject.default)(defaultPaginationProps, {
    total: dataSource.length,
    current: paginationCurrent,
    pageSize: paginationSize
  }, pagination || {});
  const largestPage = Math.ceil(paginationProps.total / paginationProps.pageSize);
  paginationProps.current = Math.min(paginationProps.current, largestPage);
  const paginationContent = pagination && (/*#__PURE__*/React.createElement("div", {
    className: (0, _classnames.default)(`${prefixCls}-pagination`)
  }, /*#__PURE__*/React.createElement(_pagination.default, Object.assign({
    align: "end"
  }, paginationProps, {
    onChange: onPaginationChange,
    onShowSizeChange: onPaginationShowSizeChange
  }))));
  let splitDataSource = (0, _toConsumableArray2.default)(dataSource);
  if (pagination) {
    if (dataSource.length > (paginationProps.current - 1) * paginationProps.pageSize) {
      splitDataSource = (0, _toConsumableArray2.default)(dataSource).splice((paginationProps.current - 1) * paginationProps.pageSize, paginationProps.pageSize);
    }
  }
  const needResponsive = Object.keys(grid || {}).some(key => ['xs', 'sm', 'md', 'lg', 'xl', 'xxl'].includes(key));
  const screens = (0, _useBreakpoint.default)(needResponsive);
  const currentBreakpoint = React.useMemo(() => {
    for (let i = 0; i < _responsiveObserver.responsiveArray.length; i += 1) {
      const breakpoint = _responsiveObserver.responsiveArray[i];
      if (screens[breakpoint]) {
        return breakpoint;
      }
    }
    return undefined;
  }, [screens]);
  const colStyle = React.useMemo(() => {
    if (!grid) {
      return undefined;
    }
    const columnCount = currentBreakpoint && grid[currentBreakpoint] ? grid[currentBreakpoint] : grid.column;
    if (columnCount) {
      return {
        width: `${100 / columnCount}%`,
        maxWidth: `${100 / columnCount}%`
      };
    }
  }, [JSON.stringify(grid), currentBreakpoint]);
  let childrenContent = isLoading && /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: 53
    }
  });
  if (splitDataSource.length > 0) {
    const items = splitDataSource.map(renderInternalItem);
    childrenContent = grid ? (/*#__PURE__*/React.createElement(_grid.Row, {
      gutter: grid.gutter
    }, React.Children.map(items, child => (/*#__PURE__*/React.createElement("div", {
      key: child === null || child === void 0 ? void 0 : child.key,
      style: colStyle
    }, child))))) : (/*#__PURE__*/React.createElement("ul", {
      className: `${prefixCls}-items`
    }, items));
  } else if (!children && !isLoading) {
    childrenContent = /*#__PURE__*/React.createElement("div", {
      className: `${prefixCls}-empty-text`
    }, (locale === null || locale === void 0 ? void 0 : locale.emptyText) || (renderEmpty === null || renderEmpty === void 0 ? void 0 : renderEmpty('List')) || /*#__PURE__*/React.createElement(_defaultRenderEmpty.default, {
      componentName: "List"
    }));
  }
  const paginationPosition = paginationProps.position;
  const contextValue = React.useMemo(() => ({
    grid,
    itemLayout
  }), [JSON.stringify(grid), itemLayout]);
  return wrapCSSVar(/*#__PURE__*/React.createElement(_context2.ListContext.Provider, {
    value: contextValue
  }, /*#__PURE__*/React.createElement("div", Object.assign({
    ref: ref,
    style: Object.assign(Object.assign({}, contextStyle), style),
    className: classString
  }, rest), (paginationPosition === 'top' || paginationPosition === 'both') && paginationContent, header && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-header`
  }, header), /*#__PURE__*/React.createElement(_spin.default, Object.assign({}, loadingProp), childrenContent, children), footer && /*#__PURE__*/React.createElement("div", {
    className: `${prefixCls}-footer`
  }, footer), loadMore || (paginationPosition === 'bottom' || paginationPosition === 'both') && paginationContent)));
}
const ListWithForwardRef = /*#__PURE__*/React.forwardRef(InternalList);
if (process.env.NODE_ENV !== 'production') {
  ListWithForwardRef.displayName = 'List';
}
const List = ListWithForwardRef;
List.Item = _Item.default;
var _default = exports.default = List;