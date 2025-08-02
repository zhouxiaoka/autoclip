import type AbstractCalculator from './calculator';
import CSSCalculator from './CSSCalculator';
import NumCalculator from './NumCalculator';
declare const genCalc: (type: 'css' | 'js', unitlessCssVar: Set<string>) => (num: number | string | AbstractCalculator) => CSSCalculator | NumCalculator;
export default genCalc;
