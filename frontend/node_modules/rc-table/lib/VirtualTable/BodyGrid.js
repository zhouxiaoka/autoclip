"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof3 = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _slicedToArray2 = _interopRequireDefault(require("@babel/runtime/helpers/slicedToArray"));
var _context = require("@rc-component/context");
var _rcVirtualList = _interopRequireDefault(require("rc-virtual-list"));
var React = _interopRequireWildcard(require("react"));
var _TableContext = _interopRequireWildcard(require("../context/TableContext"));
var _useFlattenRecords = _interopRequireDefault(require("../hooks/useFlattenRecords"));
var _BodyLine = _interopRequireDefault(require("./BodyLine"));
var _context2 = require("./context");
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof3(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
var Grid = /*#__PURE__*/React.forwardRef(function (props, ref) {
  var data = props.data,
    onScroll = props.onScroll;
  var _useContext = (0, _context.useContext)(_TableContext.default, ['flattenColumns', 'onColumnResize', 'getRowKey', 'prefixCls', 'expandedKeys', 'childrenColumnName', 'scrollX', 'direction']),
    flattenColumns = _useContext.flattenColumns,
    onColumnResize = _useContext.onColumnResize,
    getRowKey = _useContext.getRowKey,
    expandedKeys = _useContext.expandedKeys,
    prefixCls = _useContext.prefixCls,
    childrenColumnName = _useContext.childrenColumnName,
    scrollX = _useContext.scrollX,
    direction = _useContext.direction;
  var _useContext2 = (0, _context.useContext)(_context2.StaticContext),
    sticky = _useContext2.sticky,
    scrollY = _useContext2.scrollY,
    listItemHeight = _useContext2.listItemHeight,
    getComponent = _useContext2.getComponent,
    onTablePropScroll = _useContext2.onScroll;

  // =========================== Ref ============================
  var listRef = React.useRef();

  // =========================== Data ===========================
  var flattenData = (0, _useFlattenRecords.default)(data, childrenColumnName, expandedKeys, getRowKey);

  // ========================== Column ==========================
  var columnsWidth = React.useMemo(function () {
    var total = 0;
    return flattenColumns.map(function (_ref) {
      var width = _ref.width,
        key = _ref.key;
      total += width;
      return [key, width, total];
    });
  }, [flattenColumns]);
  var columnsOffset = React.useMemo(function () {
    return columnsWidth.map(function (colWidth) {
      return colWidth[2];
    });
  }, [columnsWidth]);
  React.useEffect(function () {
    columnsWidth.forEach(function (_ref2) {
      var _ref3 = (0, _slicedToArray2.default)(_ref2, 2),
        key = _ref3[0],
        width = _ref3[1];
      onColumnResize(key, width);
    });
  }, [columnsWidth]);

  // =========================== Ref ============================
  React.useImperativeHandle(ref, function () {
    var _listRef$current2;
    var obj = {
      scrollTo: function scrollTo(config) {
        var _listRef$current;
        (_listRef$current = listRef.current) === null || _listRef$current === void 0 || _listRef$current.scrollTo(config);
      },
      nativeElement: (_listRef$current2 = listRef.current) === null || _listRef$current2 === void 0 ? void 0 : _listRef$current2.nativeElement
    };
    Object.defineProperty(obj, 'scrollLeft', {
      get: function get() {
        var _listRef$current3;
        return ((_listRef$current3 = listRef.current) === null || _listRef$current3 === void 0 ? void 0 : _listRef$current3.getScrollInfo().x) || 0;
      },
      set: function set(value) {
        var _listRef$current4;
        (_listRef$current4 = listRef.current) === null || _listRef$current4 === void 0 || _listRef$current4.scrollTo({
          left: value
        });
      }
    });
    return obj;
  });

  // ======================= Col/Row Span =======================
  var getRowSpan = function getRowSpan(column, index) {
    var _flattenData$index;
    var record = (_flattenData$index = flattenData[index]) === null || _flattenData$index === void 0 ? void 0 : _flattenData$index.record;
    var onCell = column.onCell;
    if (onCell) {
      var _cellProps$rowSpan;
      var cellProps = onCell(record, index);
      return (_cellProps$rowSpan = cellProps === null || cellProps === void 0 ? void 0 : cellProps.rowSpan) !== null && _cellProps$rowSpan !== void 0 ? _cellProps$rowSpan : 1;
    }
    return 1;
  };
  var extraRender = function extraRender(info) {
    var start = info.start,
      end = info.end,
      getSize = info.getSize,
      offsetY = info.offsetY;

    // Do nothing if no data
    if (end < 0) {
      return null;
    }

    // Find first rowSpan column
    var firstRowSpanColumns = flattenColumns.filter(
    // rowSpan is 0
    function (column) {
      return getRowSpan(column, start) === 0;
    });
    var startIndex = start;
    var _loop = function _loop(i) {
      firstRowSpanColumns = firstRowSpanColumns.filter(function (column) {
        return getRowSpan(column, i) === 0;
      });
      if (!firstRowSpanColumns.length) {
        startIndex = i;
        return 1; // break
      }
    };
    for (var i = start; i >= 0; i -= 1) {
      if (_loop(i)) break;
    }

    // Find last rowSpan column
    var lastRowSpanColumns = flattenColumns.filter(
    // rowSpan is not 1
    function (column) {
      return getRowSpan(column, end) !== 1;
    });
    var endIndex = end;
    var _loop2 = function _loop2(_i) {
      lastRowSpanColumns = lastRowSpanColumns.filter(function (column) {
        return getRowSpan(column, _i) !== 1;
      });
      if (!lastRowSpanColumns.length) {
        endIndex = Math.max(_i - 1, end);
        return 1; // break
      }
    };
    for (var _i = end; _i < flattenData.length; _i += 1) {
      if (_loop2(_i)) break;
    }

    // Collect the line who has rowSpan
    var spanLines = [];
    var _loop3 = function _loop3(_i2) {
      var item = flattenData[_i2];

      // This code will never reach, just incase
      if (!item) {
        return 1; // continue
      }
      if (flattenColumns.some(function (column) {
        return getRowSpan(column, _i2) > 1;
      })) {
        spanLines.push(_i2);
      }
    };
    for (var _i2 = startIndex; _i2 <= endIndex; _i2 += 1) {
      if (_loop3(_i2)) continue;
    }

    // Patch extra line on the page
    var nodes = spanLines.map(function (index) {
      var item = flattenData[index];
      var rowKey = getRowKey(item.record, index);
      var getHeight = function getHeight(rowSpan) {
        var endItemIndex = index + rowSpan - 1;
        var endItemKey = getRowKey(flattenData[endItemIndex].record, endItemIndex);
        var sizeInfo = getSize(rowKey, endItemKey);
        return sizeInfo.bottom - sizeInfo.top;
      };
      var sizeInfo = getSize(rowKey);
      return /*#__PURE__*/React.createElement(_BodyLine.default, {
        key: index,
        data: item,
        rowKey: rowKey,
        index: index,
        style: {
          top: -offsetY + sizeInfo.top
        },
        extra: true,
        getHeight: getHeight
      });
    });
    return nodes;
  };

  // ========================= Context ==========================
  var gridContext = React.useMemo(function () {
    return {
      columnsOffset: columnsOffset
    };
  }, [columnsOffset]);

  // ========================== Render ==========================
  var tblPrefixCls = "".concat(prefixCls, "-tbody");

  // default 'div' in rc-virtual-list
  var wrapperComponent = getComponent(['body', 'wrapper']);

  // ========================== Sticky Scroll Bar ==========================
  var horizontalScrollBarStyle = {};
  if (sticky) {
    horizontalScrollBarStyle.position = 'sticky';
    horizontalScrollBarStyle.bottom = 0;
    if ((0, _typeof2.default)(sticky) === 'object' && sticky.offsetScroll) {
      horizontalScrollBarStyle.bottom = sticky.offsetScroll;
    }
  }
  return /*#__PURE__*/React.createElement(_context2.GridContext.Provider, {
    value: gridContext
  }, /*#__PURE__*/React.createElement(_rcVirtualList.default, {
    fullHeight: false,
    ref: listRef,
    prefixCls: "".concat(tblPrefixCls, "-virtual"),
    styles: {
      horizontalScrollBar: horizontalScrollBarStyle
    },
    className: tblPrefixCls,
    height: scrollY,
    itemHeight: listItemHeight || 24,
    data: flattenData,
    itemKey: function itemKey(item) {
      return getRowKey(item.record);
    },
    component: wrapperComponent,
    scrollWidth: scrollX,
    direction: direction,
    onVirtualScroll: function onVirtualScroll(_ref4) {
      var _listRef$current5;
      var x = _ref4.x;
      onScroll({
        currentTarget: (_listRef$current5 = listRef.current) === null || _listRef$current5 === void 0 ? void 0 : _listRef$current5.nativeElement,
        scrollLeft: x
      });
    },
    onScroll: onTablePropScroll,
    extraRender: extraRender
  }, function (item, index, itemProps) {
    var rowKey = getRowKey(item.record, index);
    return /*#__PURE__*/React.createElement(_BodyLine.default, {
      data: item,
      rowKey: rowKey,
      index: index,
      style: itemProps.style
    });
  }));
});
var ResponseGrid = (0, _TableContext.responseImmutable)(Grid);
if (process.env.NODE_ENV !== 'production') {
  ResponseGrid.displayName = 'ResponseGrid';
}
var _default = exports.default = ResponseGrid;