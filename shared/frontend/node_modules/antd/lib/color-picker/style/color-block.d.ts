import type { CSSObject } from '@ant-design/cssinjs';
import type { ColorPickerToken } from './index';
/**
 * @private Internal usage only
 * see: https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/conic-gradient#checkerboard
 */
export declare const getTransBg: (size: string, colorFill: string) => CSSObject;
declare const genColorBlockStyle: (token: ColorPickerToken, size: number) => CSSObject;
export default genColorBlockStyle;
