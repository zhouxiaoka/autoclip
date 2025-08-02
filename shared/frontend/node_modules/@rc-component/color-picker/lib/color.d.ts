import { FastColor } from '@ant-design/fast-color';
import type { ColorGenInput } from './interface';
export declare const getRoundNumber: (value: number) => number;
export declare class Color extends FastColor {
    constructor(color: ColorGenInput);
    toHsbString(): string;
    toHsb(): {
        b: number;
        a: number;
        h: number;
        s: number;
    };
}
