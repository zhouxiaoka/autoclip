import type { ColorGenInput } from '@rc-component/color-picker';
import { AggregationColor } from './color';
import type { ColorValueType } from './interface';
export declare const generateColor: (color: ColorGenInput<AggregationColor> | Exclude<ColorValueType, null>) => AggregationColor;
export declare const getRoundNumber: (value: number) => number;
export declare const getColorAlpha: (color: AggregationColor) => number;
/** Return the color whose `alpha` is 1 */
export declare const genAlphaColor: (color: AggregationColor, alpha?: number) => AggregationColor;
/**
 * Get percent position color. e.g. [10%-#fff, 20%-#000], 15% => #888
 */
export declare const getGradientPercentColor: (colors: {
    percent: number;
    color: string;
}[], percent: number) => string;
