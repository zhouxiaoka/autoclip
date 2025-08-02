import type { ColorGenInput, Colors } from './interface';
export declare const toHexFormat: (value?: string, alpha?: boolean) => string;
export declare const getHex: (value?: string, alpha?: boolean) => string;
export type GradientColor = {
    color: AggregationColor;
    percent: number;
}[];
export declare class AggregationColor {
    /** Original Color object */
    private metaColor;
    private colors;
    cleared: boolean;
    constructor(color: ColorGenInput<AggregationColor> | Colors<AggregationColor>);
    toHsb(): {
        b: number;
        a: number;
        h: number;
        s: number;
    };
    toHsbString(): string;
    toHex(): string;
    toHexString(): string;
    toRgb(): import("@ant-design/fast-color").RGB;
    toRgbString(): string;
    isGradient(): boolean;
    getColors(): GradientColor;
    toCssString(): string;
    equals(color: AggregationColor | null): boolean;
}
