import _typeof from "@babel/runtime/helpers/esm/typeof";
import _classCallCheck from "@babel/runtime/helpers/esm/classCallCheck";
import _createClass from "@babel/runtime/helpers/esm/createClass";
import _assertThisInitialized from "@babel/runtime/helpers/esm/assertThisInitialized";
import _inherits from "@babel/runtime/helpers/esm/inherits";
import _createSuper from "@babel/runtime/helpers/esm/createSuper";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
import AbstractCalculator from "./calculator";
var CALC_UNIT = 'CALC_UNIT';
var regexp = new RegExp(CALC_UNIT, 'g');
function unit(value) {
  if (typeof value === 'number') {
    return "".concat(value).concat(CALC_UNIT);
  }
  return value;
}
var CSSCalculator = /*#__PURE__*/function (_AbstractCalculator) {
  _inherits(CSSCalculator, _AbstractCalculator);
  var _super = _createSuper(CSSCalculator);
  function CSSCalculator(num, unitlessCssVar) {
    var _this;
    _classCallCheck(this, CSSCalculator);
    _this = _super.call(this);
    _defineProperty(_assertThisInitialized(_this), "result", '');
    _defineProperty(_assertThisInitialized(_this), "unitlessCssVar", void 0);
    _defineProperty(_assertThisInitialized(_this), "lowPriority", void 0);
    var numType = _typeof(num);
    _this.unitlessCssVar = unitlessCssVar;
    if (num instanceof CSSCalculator) {
      _this.result = "(".concat(num.result, ")");
    } else if (numType === 'number') {
      _this.result = unit(num);
    } else if (numType === 'string') {
      _this.result = num;
    }
    return _this;
  }
  _createClass(CSSCalculator, [{
    key: "add",
    value: function add(num) {
      if (num instanceof CSSCalculator) {
        this.result = "".concat(this.result, " + ").concat(num.getResult());
      } else if (typeof num === 'number' || typeof num === 'string') {
        this.result = "".concat(this.result, " + ").concat(unit(num));
      }
      this.lowPriority = true;
      return this;
    }
  }, {
    key: "sub",
    value: function sub(num) {
      if (num instanceof CSSCalculator) {
        this.result = "".concat(this.result, " - ").concat(num.getResult());
      } else if (typeof num === 'number' || typeof num === 'string') {
        this.result = "".concat(this.result, " - ").concat(unit(num));
      }
      this.lowPriority = true;
      return this;
    }
  }, {
    key: "mul",
    value: function mul(num) {
      if (this.lowPriority) {
        this.result = "(".concat(this.result, ")");
      }
      if (num instanceof CSSCalculator) {
        this.result = "".concat(this.result, " * ").concat(num.getResult(true));
      } else if (typeof num === 'number' || typeof num === 'string') {
        this.result = "".concat(this.result, " * ").concat(num);
      }
      this.lowPriority = false;
      return this;
    }
  }, {
    key: "div",
    value: function div(num) {
      if (this.lowPriority) {
        this.result = "(".concat(this.result, ")");
      }
      if (num instanceof CSSCalculator) {
        this.result = "".concat(this.result, " / ").concat(num.getResult(true));
      } else if (typeof num === 'number' || typeof num === 'string') {
        this.result = "".concat(this.result, " / ").concat(num);
      }
      this.lowPriority = false;
      return this;
    }
  }, {
    key: "getResult",
    value: function getResult(force) {
      return this.lowPriority || force ? "(".concat(this.result, ")") : this.result;
    }
  }, {
    key: "equal",
    value: function equal(options) {
      var _this2 = this;
      var _ref = options || {},
        cssUnit = _ref.unit;
      var mergedUnit = true;
      if (typeof cssUnit === 'boolean') {
        mergedUnit = cssUnit;
      } else if (Array.from(this.unitlessCssVar).some(function (cssVar) {
        return _this2.result.includes(cssVar);
      })) {
        mergedUnit = false;
      }
      this.result = this.result.replace(regexp, mergedUnit ? 'px' : '');
      if (typeof this.lowPriority !== 'undefined') {
        return "calc(".concat(this.result, ")");
      }
      return this.result;
    }
  }]);
  return CSSCalculator;
}(AbstractCalculator);
export { CSSCalculator as default };