"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _typeof2 = _interopRequireDefault(require("@babel/runtime/helpers/typeof"));
var _classCallCheck2 = _interopRequireDefault(require("@babel/runtime/helpers/classCallCheck"));
var _createClass2 = _interopRequireDefault(require("@babel/runtime/helpers/createClass"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _react = _interopRequireDefault(require("react"));
var BEAT_LIMIT = 1000 * 60 * 10;

/**
 * A helper class to map keys to values.
 * It supports both primitive keys and object keys.
 */
var ArrayKeyMap = /*#__PURE__*/function () {
  function ArrayKeyMap() {
    (0, _classCallCheck2.default)(this, ArrayKeyMap);
    (0, _defineProperty2.default)(this, "map", new Map());
    // Use WeakMap to avoid memory leak
    (0, _defineProperty2.default)(this, "objectIDMap", new WeakMap());
    (0, _defineProperty2.default)(this, "nextID", 0);
    (0, _defineProperty2.default)(this, "lastAccessBeat", new Map());
    // We will clean up the cache when reach the limit
    (0, _defineProperty2.default)(this, "accessBeat", 0);
  }
  (0, _createClass2.default)(ArrayKeyMap, [{
    key: "set",
    value: function set(keys, value) {
      // New set will trigger clear
      this.clear();

      // Set logic
      var compositeKey = this.getCompositeKey(keys);
      this.map.set(compositeKey, value);
      this.lastAccessBeat.set(compositeKey, Date.now());
    }
  }, {
    key: "get",
    value: function get(keys) {
      var compositeKey = this.getCompositeKey(keys);
      var cache = this.map.get(compositeKey);
      this.lastAccessBeat.set(compositeKey, Date.now());
      this.accessBeat += 1;
      return cache;
    }
  }, {
    key: "getCompositeKey",
    value: function getCompositeKey(keys) {
      var _this = this;
      var ids = keys.map(function (key) {
        if (key && (0, _typeof2.default)(key) === 'object') {
          return "obj_".concat(_this.getObjectID(key));
        }
        return "".concat((0, _typeof2.default)(key), "_").concat(key);
      });
      return ids.join('|');
    }
  }, {
    key: "getObjectID",
    value: function getObjectID(obj) {
      if (this.objectIDMap.has(obj)) {
        return this.objectIDMap.get(obj);
      }
      var id = this.nextID;
      this.objectIDMap.set(obj, id);
      this.nextID += 1;
      return id;
    }
  }, {
    key: "clear",
    value: function clear() {
      var _this2 = this;
      if (this.accessBeat > 10000) {
        var now = Date.now();
        this.lastAccessBeat.forEach(function (beat, key) {
          if (now - beat > BEAT_LIMIT) {
            _this2.map.delete(key);
            _this2.lastAccessBeat.delete(key);
          }
        });
        this.accessBeat = 0;
      }
    }
  }]);
  return ArrayKeyMap;
}();
var uniqueMap = new ArrayKeyMap();

/**
 * Like `useMemo`, but this hook result will be shared across all instances.
 */
function useUniqueMemo(memoFn, deps) {
  return _react.default.useMemo(function () {
    var cachedValue = uniqueMap.get(deps);
    if (cachedValue) {
      return cachedValue;
    }
    var newValue = memoFn();
    uniqueMap.set(deps, newValue);
    return newValue;
  }, deps);
}
var _default = exports.default = useUniqueMemo;