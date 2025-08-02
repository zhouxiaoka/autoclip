import _classCallCheck from "@babel/runtime/helpers/esm/classCallCheck";
import _createClass from "@babel/runtime/helpers/esm/createClass";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
// Firefox has low performance of map.
var CacheMap = /*#__PURE__*/function () {
  function CacheMap() {
    _classCallCheck(this, CacheMap);
    _defineProperty(this, "maps", void 0);
    // Used for cache key
    // `useMemo` no need to update if `id` not change
    _defineProperty(this, "id", 0);
    _defineProperty(this, "diffRecords", new Map());
    this.maps = Object.create(null);
  }
  _createClass(CacheMap, [{
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
export default CacheMap;