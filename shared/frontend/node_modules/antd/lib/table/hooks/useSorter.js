"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.getSortData = exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _CaretDownOutlined = _interopRequireDefault(require("@ant-design/icons/CaretDownOutlined"));
var _CaretUpOutlined = _interopRequireDefault(require("@ant-design/icons/CaretUpOutlined"));
var _classnames = _interopRequireDefault(require("classnames"));
var _KeyCode = _interopRequireDefault(require("rc-util/lib/KeyCode"));
var _tooltip = _interopRequireDefault(require("../../tooltip"));
var _util = require("../util");
const ASCEND = 'ascend';
const DESCEND = 'descend';
const getMultiplePriority = column => {
  if (typeof column.sorter === 'object' && typeof column.sorter.multiple === 'number') {
    return column.sorter.multiple;
  }
  return false;
};
const getSortFunction = sorter => {
  if (typeof sorter === 'function') {
    return sorter;
  }
  if (sorter && typeof sorter === 'object' && sorter.compare) {
    return sorter.compare;
  }
  return false;
};
const nextSortDirection = (sortDirections, current) => {
  if (!current) {
    return sortDirections[0];
  }
  return sortDirections[sortDirections.indexOf(current) + 1];
};
const collectSortStates = (columns, init, pos) => {
  let sortStates = [];
  const pushState = (column, columnPos) => {
    sortStates.push({
      column,
      key: (0, _util.getColumnKey)(column, columnPos),
      multiplePriority: getMultiplePriority(column),
      sortOrder: column.sortOrder
    });
  };
  (columns || []).forEach((column, index) => {
    const columnPos = (0, _util.getColumnPos)(index, pos);
    if (column.children) {
      if ('sortOrder' in column) {
        // Controlled
        pushState(column, columnPos);
      }
      sortStates = [].concat((0, _toConsumableArray2.default)(sortStates), (0, _toConsumableArray2.default)(collectSortStates(column.children, init, columnPos)));
    } else if (column.sorter) {
      if ('sortOrder' in column) {
        // Controlled
        pushState(column, columnPos);
      } else if (init && column.defaultSortOrder) {
        // Default sorter
        sortStates.push({
          column,
          key: (0, _util.getColumnKey)(column, columnPos),
          multiplePriority: getMultiplePriority(column),
          sortOrder: column.defaultSortOrder
        });
      }
    }
  });
  return sortStates;
};
const injectSorter = (prefixCls, columns, sorterStates, triggerSorter, defaultSortDirections, tableLocale, tableShowSorterTooltip, pos) => {
  const finalColumns = (columns || []).map((column, index) => {
    const columnPos = (0, _util.getColumnPos)(index, pos);
    let newColumn = column;
    if (newColumn.sorter) {
      const sortDirections = newColumn.sortDirections || defaultSortDirections;
      const showSorterTooltip = newColumn.showSorterTooltip === undefined ? tableShowSorterTooltip : newColumn.showSorterTooltip;
      const columnKey = (0, _util.getColumnKey)(newColumn, columnPos);
      const sorterState = sorterStates.find(({
        key
      }) => key === columnKey);
      const sortOrder = sorterState ? sorterState.sortOrder : null;
      const nextSortOrder = nextSortDirection(sortDirections, sortOrder);
      let sorter;
      if (column.sortIcon) {
        sorter = column.sortIcon({
          sortOrder
        });
      } else {
        const upNode = sortDirections.includes(ASCEND) && (/*#__PURE__*/React.createElement(_CaretUpOutlined.default, {
          className: (0, _classnames.default)(`${prefixCls}-column-sorter-up`, {
            active: sortOrder === ASCEND
          })
        }));
        const downNode = sortDirections.includes(DESCEND) && (/*#__PURE__*/React.createElement(_CaretDownOutlined.default, {
          className: (0, _classnames.default)(`${prefixCls}-column-sorter-down`, {
            active: sortOrder === DESCEND
          })
        }));
        sorter = /*#__PURE__*/React.createElement("span", {
          className: (0, _classnames.default)(`${prefixCls}-column-sorter`, {
            [`${prefixCls}-column-sorter-full`]: !!(upNode && downNode)
          })
        }, /*#__PURE__*/React.createElement("span", {
          className: `${prefixCls}-column-sorter-inner`,
          "aria-hidden": "true"
        }, upNode, downNode));
      }
      const {
        cancelSort,
        triggerAsc,
        triggerDesc
      } = tableLocale || {};
      let sortTip = cancelSort;
      if (nextSortOrder === DESCEND) {
        sortTip = triggerDesc;
      } else if (nextSortOrder === ASCEND) {
        sortTip = triggerAsc;
      }
      const tooltipProps = typeof showSorterTooltip === 'object' ? Object.assign({
        title: sortTip
      }, showSorterTooltip) : {
        title: sortTip
      };
      newColumn = Object.assign(Object.assign({}, newColumn), {
        className: (0, _classnames.default)(newColumn.className, {
          [`${prefixCls}-column-sort`]: sortOrder
        }),
        title: renderProps => {
          const columnSortersClass = `${prefixCls}-column-sorters`;
          const renderColumnTitleWrapper = /*#__PURE__*/React.createElement("span", {
            className: `${prefixCls}-column-title`
          }, (0, _util.renderColumnTitle)(column.title, renderProps));
          const renderSortTitle = /*#__PURE__*/React.createElement("div", {
            className: columnSortersClass
          }, renderColumnTitleWrapper, sorter);
          if (showSorterTooltip) {
            if (typeof showSorterTooltip !== 'boolean' && (showSorterTooltip === null || showSorterTooltip === void 0 ? void 0 : showSorterTooltip.target) === 'sorter-icon') {
              return /*#__PURE__*/React.createElement("div", {
                className: `${columnSortersClass} ${prefixCls}-column-sorters-tooltip-target-sorter`
              }, renderColumnTitleWrapper, /*#__PURE__*/React.createElement(_tooltip.default, Object.assign({}, tooltipProps), sorter));
            }
            return /*#__PURE__*/React.createElement(_tooltip.default, Object.assign({}, tooltipProps), renderSortTitle);
          }
          return renderSortTitle;
        },
        onHeaderCell: col => {
          var _a;
          const cell = ((_a = column.onHeaderCell) === null || _a === void 0 ? void 0 : _a.call(column, col)) || {};
          const originOnClick = cell.onClick;
          const originOKeyDown = cell.onKeyDown;
          cell.onClick = event => {
            triggerSorter({
              column,
              key: columnKey,
              sortOrder: nextSortOrder,
              multiplePriority: getMultiplePriority(column)
            });
            originOnClick === null || originOnClick === void 0 ? void 0 : originOnClick(event);
          };
          cell.onKeyDown = event => {
            if (event.keyCode === _KeyCode.default.ENTER) {
              triggerSorter({
                column,
                key: columnKey,
                sortOrder: nextSortOrder,
                multiplePriority: getMultiplePriority(column)
              });
              originOKeyDown === null || originOKeyDown === void 0 ? void 0 : originOKeyDown(event);
            }
          };
          const renderTitle = (0, _util.safeColumnTitle)(column.title, {});
          const displayTitle = renderTitle === null || renderTitle === void 0 ? void 0 : renderTitle.toString();
          // Inform the screen-reader so it can tell the visually impaired user which column is sorted
          if (sortOrder) {
            cell['aria-sort'] = sortOrder === 'ascend' ? 'ascending' : 'descending';
          }
          cell['aria-label'] = displayTitle || '';
          cell.className = (0, _classnames.default)(cell.className, `${prefixCls}-column-has-sorters`);
          cell.tabIndex = 0;
          if (column.ellipsis) {
            cell.title = (renderTitle !== null && renderTitle !== void 0 ? renderTitle : '').toString();
          }
          return cell;
        }
      });
    }
    if ('children' in newColumn) {
      newColumn = Object.assign(Object.assign({}, newColumn), {
        children: injectSorter(prefixCls, newColumn.children, sorterStates, triggerSorter, defaultSortDirections, tableLocale, tableShowSorterTooltip, columnPos)
      });
    }
    return newColumn;
  });
  return finalColumns;
};
const stateToInfo = sorterState => {
  const {
    column,
    sortOrder
  } = sorterState;
  return {
    column,
    order: sortOrder,
    field: column.dataIndex,
    columnKey: column.key
  };
};
const generateSorterInfo = sorterStates => {
  const activeSorters = sorterStates.filter(({
    sortOrder
  }) => sortOrder).map(stateToInfo);
  // =========== Legacy compatible support ===========
  // https://github.com/ant-design/ant-design/pull/19226
  if (activeSorters.length === 0 && sorterStates.length) {
    const lastIndex = sorterStates.length - 1;
    return Object.assign(Object.assign({}, stateToInfo(sorterStates[lastIndex])), {
      column: undefined,
      order: undefined,
      field: undefined,
      columnKey: undefined
    });
  }
  if (activeSorters.length <= 1) {
    return activeSorters[0] || {};
  }
  return activeSorters;
};
const getSortData = (data, sortStates, childrenColumnName) => {
  const innerSorterStates = sortStates.slice().sort((a, b) => b.multiplePriority - a.multiplePriority);
  const cloneData = data.slice();
  const runningSorters = innerSorterStates.filter(({
    column: {
      sorter
    },
    sortOrder
  }) => getSortFunction(sorter) && sortOrder);
  // Skip if no sorter needed
  if (!runningSorters.length) {
    return cloneData;
  }
  return cloneData.sort((record1, record2) => {
    for (let i = 0; i < runningSorters.length; i += 1) {
      const sorterState = runningSorters[i];
      const {
        column: {
          sorter
        },
        sortOrder
      } = sorterState;
      const compareFn = getSortFunction(sorter);
      if (compareFn && sortOrder) {
        const compareResult = compareFn(record1, record2, sortOrder);
        if (compareResult !== 0) {
          return sortOrder === ASCEND ? compareResult : -compareResult;
        }
      }
    }
    return 0;
  }).map(record => {
    const subRecords = record[childrenColumnName];
    if (subRecords) {
      return Object.assign(Object.assign({}, record), {
        [childrenColumnName]: getSortData(subRecords, sortStates, childrenColumnName)
      });
    }
    return record;
  });
};
exports.getSortData = getSortData;
const useFilterSorter = props => {
  const {
    prefixCls,
    mergedColumns,
    sortDirections,
    tableLocale,
    showSorterTooltip,
    onSorterChange
  } = props;
  const [sortStates, setSortStates] = React.useState(() => collectSortStates(mergedColumns, true));
  const getColumnKeys = (columns, pos) => {
    const newKeys = [];
    columns.forEach((item, index) => {
      const columnPos = (0, _util.getColumnPos)(index, pos);
      newKeys.push((0, _util.getColumnKey)(item, columnPos));
      if (Array.isArray(item.children)) {
        const childKeys = getColumnKeys(item.children, columnPos);
        newKeys.push.apply(newKeys, (0, _toConsumableArray2.default)(childKeys));
      }
    });
    return newKeys;
  };
  const mergedSorterStates = React.useMemo(() => {
    let validate = true;
    const collectedStates = collectSortStates(mergedColumns, false);
    // Return if not controlled
    if (!collectedStates.length) {
      const mergedColumnsKeys = getColumnKeys(mergedColumns);
      return sortStates.filter(({
        key
      }) => mergedColumnsKeys.includes(key));
    }
    const validateStates = [];
    function patchStates(state) {
      if (validate) {
        validateStates.push(state);
      } else {
        validateStates.push(Object.assign(Object.assign({}, state), {
          sortOrder: null
        }));
      }
    }
    let multipleMode = null;
    collectedStates.forEach(state => {
      if (multipleMode === null) {
        patchStates(state);
        if (state.sortOrder) {
          if (state.multiplePriority === false) {
            validate = false;
          } else {
            multipleMode = true;
          }
        }
      } else if (multipleMode && state.multiplePriority !== false) {
        patchStates(state);
      } else {
        validate = false;
        patchStates(state);
      }
    });
    return validateStates;
  }, [mergedColumns, sortStates]);
  // Get render columns title required props
  const columnTitleSorterProps = React.useMemo(() => {
    var _a, _b;
    const sortColumns = mergedSorterStates.map(({
      column,
      sortOrder
    }) => ({
      column,
      order: sortOrder
    }));
    return {
      sortColumns,
      // Legacy
      sortColumn: (_a = sortColumns[0]) === null || _a === void 0 ? void 0 : _a.column,
      sortOrder: (_b = sortColumns[0]) === null || _b === void 0 ? void 0 : _b.order
    };
  }, [mergedSorterStates]);
  const triggerSorter = sortState => {
    let newSorterStates;
    if (sortState.multiplePriority === false || !mergedSorterStates.length || mergedSorterStates[0].multiplePriority === false) {
      newSorterStates = [sortState];
    } else {
      newSorterStates = [].concat((0, _toConsumableArray2.default)(mergedSorterStates.filter(({
        key
      }) => key !== sortState.key)), [sortState]);
    }
    setSortStates(newSorterStates);
    onSorterChange(generateSorterInfo(newSorterStates), newSorterStates);
  };
  const transformColumns = innerColumns => injectSorter(prefixCls, innerColumns, mergedSorterStates, triggerSorter, sortDirections, tableLocale, showSorterTooltip);
  const getSorters = () => generateSorterInfo(mergedSorterStates);
  return [transformColumns, mergedSorterStates, columnTitleSorterProps, getSorters];
};
var _default = exports.default = useFilterSorter;