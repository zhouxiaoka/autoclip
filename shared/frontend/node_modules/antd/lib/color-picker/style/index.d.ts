import type { FullToken } from '../../theme/internal';
export interface ComponentToken {
}
/**
 * @desc ColorPicker 组件的 Token
 * @descEN Token for ColorPicker component
 */
export interface ColorPickerToken extends FullToken<'ColorPicker'> {
    /**
     * @desc ColorPicker 宽度
     * @descEN Width of ColorPicker
     */
    colorPickerWidth: number;
    /**
     * @desc ColorPicker 内嵌阴影
     * @descEN Inset shadow of ColorPicker
     */
    colorPickerInsetShadow: string;
    /**
     * @desc ColorPicker 处理器尺寸
     * @descEN Handler size of ColorPicker
     */
    colorPickerHandlerSize: number;
    /**
     * @desc ColorPicker 小号处理器尺寸
     * @descEN Small handler size of ColorPicker
     */
    colorPickerHandlerSizeSM: number;
    /**
     * @desc ColorPicker 滑块高度
     * @descEN Slider height of ColorPicker
     */
    colorPickerSliderHeight: number;
    /**
     * @desc ColorPicker 预览尺寸
     * @descEN Preview size of ColorPicker
     */
    colorPickerPreviewSize: number;
    /**
     * @desc ColorPicker Alpha 输入宽度
     * @descEN Alpha input width of ColorPicker
     */
    colorPickerAlphaInputWidth: number;
    /**
     * @desc ColorPicker 输入数字处理器宽度
     * @descEN Input number handle width of ColorPicker
     */
    colorPickerInputNumberHandleWidth: number;
    /**
     * @desc ColorPicker 预设颜色尺寸
     * @descEN Preset color size of ColorPicker
     */
    colorPickerPresetColorSize: number;
}
export declare const genActiveStyle: (token: ColorPickerToken, borderColor: string, outlineColor: string) => {
    borderInlineEndWidth: number;
    borderColor: string;
    boxShadow: string;
    outline: number;
};
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
