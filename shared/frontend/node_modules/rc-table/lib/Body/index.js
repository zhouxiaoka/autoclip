"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault");
var _typeof = require("@babel/runtime/helpers/typeof");
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _context = require("@rc-component/context");
var React = _interopRequireWildcard(require("react"));
var _PerfContext = _interopRequireDefault(require("../context/PerfContext"));
var _TableContext = _interopRequireWildcard(require("../context/TableContext"));
var _useFlattenRecords = _interopRequireDefault(require("../hooks/useFlattenRecords"));
var _useRenderTimes = _interopRequireDefault(require("../hooks/useRenderTimes"));
var _valueUtil = require("../utils/valueUtil");
var _BodyRow = _interopRequireDefault(require("./BodyRow"));
var _ExpandedRow = _interopRequireDefault(require("./ExpandedRow"));
var _MeasureRow = _interopRequireDefault(require("./MeasureRow"));
function _getRequireWildcardCache(e) { if ("function" != typeof WeakMap) return null; var r = new WeakMap(), t = new WeakMap(); return (_getRequireWildcardCache = function _getRequireWildcardCache(e) { return e ? t : r; })(e); }
function _interopRequireWildcard(e, r) { if (!r && e && e.__esModule) return e; if (null === e || "object" != _typeof(e) && "function" != typeof e) return { default: e }; var t = _getRequireWildcardCache(r); if (t && t.has(e)) return t.get(e); var n = { __proto__: null }, a = Object.defineProperty && Object.getOwnPropertyDescriptor; for (var u in e) if ("default" !== u && Object.prototype.hasOwnProperty.call(e, u)) { var i = a ? Object.getOwnPropertyDescriptor(e, u) : null; i && (i.get || i.set) ? Object.defineProperty(n, u, i) : n[u] = e[u]; } return n.default = e, t && t.set(e, n), n; }
function Body(props) {
  if (process.env.NODE_ENV !== 'production') {
    (0, _useRenderTimes.default)(props);
  }
  var data = props.data,
    measureColumnWidth = props.measureColumnWidth;
  var _useContext = (0, _context.useContext)(_TableContext.default, ['prefixCls', 'getComponent', 'onColumnResize', 'flattenColumns', 'getRowKey', 'expandedKeys', 'childrenColumnName', 'emptyNode', 'expandedRowOffset', 'fixedInfoList', 'colWidths']),
    prefixCls = _useContext.prefixCls,
    getComponent = _useContext.getComponent,
    onColumnResize = _useContext.onColumnResize,
    flattenColumns = _useContext.flattenColumns,
    getRowKey = _useContext.getRowKey,
    expandedKeys = _useContext.expandedKeys,
    childrenColumnName = _useContext.childrenColumnName,
    emptyNode = _useContext.emptyNode,
    _useContext$expandedR = _useContext.expandedRowOffset,
    expandedRowOffset = _useContext$expandedR === void 0 ? 0 : _useContext$expandedR,
    colWidths = _useContext.colWidths;
  var flattenData = (0, _useFlattenRecords.default)(data, childrenColumnName, expandedKeys, getRowKey);
  var rowKeys = React.useMemo(function () {
    return flattenData.map(function (item) {
      return item.rowKey;
    });
  }, [flattenData]);

  // =================== Performance ====================
  var perfRef = React.useRef({
    renderWithProps: false
  });

  // ===================== Expanded =====================
  // `expandedRowOffset` data is same for all the rows.
  // Let's calc on Body side to save performance.
  var expandedRowInfo = React.useMemo(function () {
    var expandedColSpan = flattenColumns.length - expandedRowOffset;
    var expandedStickyStart = 0;
    for (var i = 0; i < expandedRowOffset; i += 1) {
      expandedStickyStart += colWidths[i] || 0;
    }
    return {
      offset: expandedRowOffset,
      colSpan: expandedColSpan,
      sticky: expandedStickyStart
    };
  }, [flattenColumns.length, expandedRowOffset, colWidths]);

  // ====================== Render ======================
  var WrapperComponent = getComponent(['body', 'wrapper'], 'tbody');
  var trComponent = getComponent(['body', 'row'], 'tr');
  var tdComponent = getComponent(['body', 'cell'], 'td');
  var thComponent = getComponent(['body', 'cell'], 'th');
  var rows;
  if (data.length) {
    rows = flattenData.map(function (item, idx) {
      var record = item.record,
        indent = item.indent,
        renderIndex = item.index,
        rowKey = item.rowKey;
      return /*#__PURE__*/React.createElement(_BodyRow.default, {
        key: rowKey,
        rowKey: rowKey,
        rowKeys: rowKeys,
        record: record,
        index: idx,
        renderIndex: renderIndex,
        rowComponent: trComponent,
        cellComponent: tdComponent,
        scopeCellComponent: thComponent,
        indent: indent
        // Expanded row info
        ,
        expandedRowInfo: expandedRowInfo
      });
    });
  } else {
    rows = /*#__PURE__*/React.createElement(_ExpandedRow.default, {
      expanded: true,
      className: "".concat(prefixCls, "-placeholder"),
      prefixCls: prefixCls,
      component: trComponent,
      cellComponent: tdComponent,
      colSpan: flattenColumns.length,
      isEmpty: true
    }, emptyNode);
  }
  var columnsKey = (0, _valueUtil.getColumnsKey)(flattenColumns);
  return /*#__PURE__*/React.createElement(_PerfContext.default.Provider, {
    value: perfRef.current
  }, /*#__PURE__*/React.createElement(WrapperComponent, {
    className: "".concat(prefixCls, "-tbody")
  }, measureColumnWidth && /*#__PURE__*/React.createElement(_MeasureRow.default, {
    prefixCls: prefixCls,
    columnsKey: columnsKey,
    onColumnResize: onColumnResize
  }), rows));
}
if (process.env.NODE_ENV !== 'production') {
  Body.displayName = 'Body';
}
var _default = exports.default = (0, _TableContext.responseImmutable)(Body);