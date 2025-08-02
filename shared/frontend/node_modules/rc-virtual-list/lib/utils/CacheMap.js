"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _classCallCheck2 = _interopRequireDefault(require("@babel/runtime/helpers/classCallCheck"));
var _createClass2 = _interopRequireDefault(require("@babel/runtime/helpers/createClass"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
// Firefox has low performance of map.
var CacheMap = /*#__PURE__*/function () {
  function CacheMap() {
    (0, _classCallCheck2.default)(this, CacheMap);
    (0, _defineProperty2.default)(this, "maps", void 0);
    // Used for cache key
    // `useMemo` no need to update if `id` not change
    (0, _defineProperty2.default)(this, "id", 0);
    (0, _defineProperty2.default)(this, "diffRecords", new Map());
    this.maps = Object.create(null);
  }
  (0, _createClass2.default)(CacheMap, [{
    key: "set",
    value: function set(key, value) {
      // Record prev value
      this.diffRecords.set(key, this.maps[key]);
      this.maps[key] = value;
      this.id += 1;
    }
  }, {
    key: "get",
    value: function get(key) {
      return this.maps[key];
    }

    /**
     * CacheMap will record the key changed.
     * To help to know what's update in the next render.
     */
  }, {
    key: "resetRecord",
    value: function resetRecord() {
      this.diffRecords.clear();
    }
  }, {
    key: "getRecord",
    value: function getRecord() {
      return this.diffRecords;
    }
  }]);
  return CacheMap;
}();
var _default = exports.default = CacheMap;