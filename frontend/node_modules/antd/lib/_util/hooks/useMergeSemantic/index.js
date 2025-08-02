"use strict";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = useMergeSemantic;
exports.mergeClassNames = mergeClassNames;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _classnames = _interopRequireDefault(require("classnames"));
// ========================= ClassNames =========================
function mergeClassNames(schema, ...classNames) {
  const mergedSchema = schema || {};
  return classNames.reduce((acc, cur) => {
    // Loop keys of the current classNames
    Object.keys(cur || {}).forEach(key => {
      const keySchema = mergedSchema[key];
      const curVal = cur[key];
      if (keySchema && typeof keySchema === 'object') {
        if (curVal && typeof curVal === 'object') {
          // Loop fill
          acc[key] = mergeClassNames(keySchema, acc[key], curVal);
        } else {
          // Covert string to object structure
          const {
            _default: defaultField
          } = keySchema;
          acc[key] = acc[key] || {};
          acc[key][defaultField] = (0, _classnames.default)(acc[key][defaultField], curVal);
        }
      } else {
        // Flatten fill
        acc[key] = (0, _classnames.default)(acc[key], curVal);
      }
    });
    return acc;
  }, {});
}
function useSemanticClassNames(schema, ...classNames) {
  return React.useMemo(() => mergeClassNames.apply(void 0, [schema].concat(classNames)), [classNames]);
}
// =========================== Styles ===========================
function useSemanticStyles(...styles) {
  return React.useMemo(() => {
    return styles.reduce((acc, cur = {}) => {
      Object.keys(cur).forEach(key => {
        acc[key] = Object.assign(Object.assign({}, acc[key]), cur[key]);
      });
      return acc;
    }, {});
  }, [styles]);
}
// =========================== Export ===========================
function fillObjectBySchema(obj, schema) {
  const newObj = Object.assign({}, obj);
  Object.keys(schema).forEach(key => {
    if (key !== '_default') {
      const nestSchema = schema[key];
      const nextValue = newObj[key] || {};
      newObj[key] = nestSchema ? fillObjectBySchema(nextValue, nestSchema) : nextValue;
    }
  });
  return newObj;
}
/**
 * Merge classNames and styles from multiple sources.
 * When `schema` is provided, it will **must** provide the nest object structure.
 */
function useMergeSemantic(classNamesList, stylesList, schema) {
  const mergedClassNames = useSemanticClassNames.apply(void 0, [schema].concat((0, _toConsumableArray2.default)(classNamesList)));
  const mergedStyles = useSemanticStyles.apply(void 0, (0, _toConsumableArray2.default)(stylesList));
  return React.useMemo(() => {
    return [fillObjectBySchema(mergedClassNames, schema), fillObjectBySchema(mergedStyles, schema)];
  }, [mergedClassNames, mergedStyles]);
}