import CSSCalculator from "./CSSCalculator";
import NumCalculator from "./NumCalculator";
var genCalc = function genCalc(type, unitlessCssVar) {
  var Calculator = type === 'css' ? CSSCalculator : NumCalculator;
  return function (num) {
    return new Calculator(num, unitlessCssVar);
  };
};
export default genCalc;