import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 指示点宽度
     * @descEN Width of indicator
     */
    dotWidth: number | string;
    /**
     * @desc 指示点高度
     * @descEN Height of indicator
     */
    dotHeight: number | string;
    /**
     * @desc 指示点之间的间距
     * @descEN gap between indicator
     */
    dotGap: number;
    /**
     * @desc 指示点距离边缘的距离
     * @descEN dot offset to Carousel edge
     */
    dotOffset: number;
    /** @deprecated Use `dotActiveWidth` instead. */
    dotWidthActive: number;
    /**
     * @desc 激活态指示点宽度
     * @descEN Width of active indicator
     */
    dotActiveWidth: number | string;
    /**
     * @desc 切换箭头大小
     * @descEN Size of arrows
     */
    arrowSize: number;
    /**
     * @desc 切换箭头边距
     * @descEN arrows offset to Carousel edge
     */
    arrowOffset: number;
}
export declare const DotDuration = "--dot-duration";
export declare const prepareComponentToken: GetDefaultToken<'Carousel'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
