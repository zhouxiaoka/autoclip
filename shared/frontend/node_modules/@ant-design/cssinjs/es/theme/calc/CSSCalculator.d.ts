import AbstractCalculator from './calculator';
export default class CSSCalculator extends AbstractCalculator {
    result: string;
    unitlessCssVar: Set<string>;
    lowPriority?: boolean;
    constructor(num: number | string | AbstractCalculator, unitlessCssVar: Set<string>);
    add(num: number | string | AbstractCalculator): this;
    sub(num: number | string | AbstractCalculator): this;
    mul(num: number | string | AbstractCalculator): this;
    div(num: number | string | AbstractCalculator): this;
    getResult(force?: boolean): string;
    equal(options?: {
        unit?: boolean;
    }): string;
}
