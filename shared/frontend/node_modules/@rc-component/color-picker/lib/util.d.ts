import { Color } from './color';
import type { ColorGenInput, HsbaColorType, TransformOffset } from './interface';
export declare const ColorPickerPrefixCls = "rc-color-picker";
export declare const generateColor: (color: ColorGenInput) => Color;
export declare const defaultColor: Color;
export declare const calculateColor: (props: {
    offset: TransformOffset;
    containerRef: React.RefObject<HTMLDivElement>;
    targetRef: React.RefObject<HTMLDivElement>;
    color?: Color;
    type?: HsbaColorType;
}) => Color;
export declare const calcOffset: (color: Color, type?: HsbaColorType) => {
    x: number;
    y: number;
};
