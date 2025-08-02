import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _typeof from "@babel/runtime/helpers/esm/typeof";
var enableStatistic = process.env.NODE_ENV !== 'production' || typeof CSSINJS_STATISTIC !== 'undefined';
var recording = true;

/**
 * This function will do as `Object.assign` in production. But will use Object.defineProperty:get to
 * pass all value access in development. To support statistic field usage with alias token.
 */
export function merge() {
  for (var _len = arguments.length, objs = new Array(_len), _key = 0; _key < _len; _key++) {
    objs[_key] = arguments[_key];
  }
  /* istanbul ignore next */
  if (!enableStatistic) {
    return Object.assign.apply(Object, [{}].concat(objs));
  }
  recording = false;
  var ret = {};
  objs.forEach(function (obj) {
    if (_typeof(obj) !== 'object') {
      return;
    }
    var keys = Object.keys(obj);
    keys.forEach(function (key) {
      Object.defineProperty(ret, key, {
        configurable: true,
        enumerable: true,
        get: function get() {
          return obj[key];
        }
      });
    });
  });
  recording = true;
  return ret;
}

/** @internal Internal Usage. Not use in your production. */
export var statistic = {};

/** @internal Internal Usage. Not use in your production. */
export var _statistic_build_ = {};

/* istanbul ignore next */
function noop() {}

/** Statistic token usage case. Should use `merge` function if you do not want spread record. */
var statisticToken = function statisticToken(token) {
  var tokenKeys;
  var proxy = token;
  var flush = noop;
  if (enableStatistic && typeof Proxy !== 'undefined') {
    tokenKeys = new Set();
    proxy = new Proxy(token, {
      get: function get(obj, prop) {
        if (recording) {
          var _tokenKeys;
          (_tokenKeys = tokenKeys) === null || _tokenKeys === void 0 || _tokenKeys.add(prop);
        }
        return obj[prop];
      }
    });
    flush = function flush(componentName, componentToken) {
      var _statistic$componentN;
      statistic[componentName] = {
        global: Array.from(tokenKeys),
        component: _objectSpread(_objectSpread({}, (_statistic$componentN = statistic[componentName]) === null || _statistic$componentN === void 0 ? void 0 : _statistic$componentN.component), componentToken)
      };
    };
  }
  return {
    token: proxy,
    keys: tokenKeys,
    flush: flush
  };
};
export default statisticToken;