"use strict";

var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _classCallCheck2 = _interopRequireDefault(require("@babel/runtime/helpers/classCallCheck"));
var _createClass2 = _interopRequireDefault(require("@babel/runtime/helpers/createClass"));
var _assertThisInitialized2 = _interopRequireDefault(require("@babel/runtime/helpers/assertThisInitialized"));
var _inherits2 = _interopRequireDefault(require("@babel/runtime/helpers/inherits"));
var _createSuper2 = _interopRequireDefault(require("@babel/runtime/helpers/createSuper"));
var _defineProperty2 = _interopRequireDefault(require("@babel/runtime/helpers/defineProperty"));
var _calculator = _interopRequireDefault(require("./calculator"));
var NumCalculator = /*#__PURE__*/function (_AbstractCalculator) {
  (0, _inherits2.default)(NumCalculator, _AbstractCalculator);
  var _super = (0, _createSuper2.default)(NumCalculator);
  function NumCalculator(num) {
    var _this;
    (0, _classCallCheck2.default)(this, NumCalculator);
    _this = _super.call(this);
    (0, _defineProperty2.default)((0, _assertThisInitialized2.default)(_this), "result", 0);
    if (num instanceof NumCalculator) {
      _this.result = num.result;
    } else if (typeof num === 'number') {
      _this.result = num;
    }
    return _this;
  }
  (0, _createClass2.default)(NumCalculator, [{
    key: "add",
    value: function add(num) {
      if (num instanceof NumCalculator) {
        this.result += num.result;
      } else if (typeof num === 'number') {
        this.result += num;
      }
      return this;
    }
  }, {
    key: "sub",
    value: function sub(num) {
      if (num instanceof NumCalculator) {
        this.result -= num.result;
      } else if (typeof num === 'number') {
        this.result -= num;
      }
      return this;
    }
  }, {
    key: "mul",
    value: function mul(num) {
      if (num instanceof NumCalculator) {
        this.result *= num.result;
      } else if (typeof num === 'number') {
        this.result *= num;
      }
      return this;
    }
  }, {
    key: "div",
    value: function div(num) {
      if (num instanceof NumCalculator) {
        this.result /= num.result;
      } else if (typeof num === 'number') {
        this.result /= num;
      }
      return this;
    }
  }, {
    key: "equal",
    value: function equal() {
      return this.result;
    }
  }]);
  return NumCalculator;
}(_calculator.default);
var _default = exports.default = NumCalculator;