import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 列表宽度
     * @descEN Width of list
     */
    listWidth: number | string;
    /**
     * @desc 大号列表宽度
     * @descEN Width of large list
     */
    listWidthLG: number | string;
    /**
     * @desc 列表高度
     * @descEN Height of list
     */
    listHeight: number | string;
    /**
     * @desc 列表项高度
     * @descEN Height of list item
     */
    itemHeight: number | string;
    /**
     * @desc 列表项纵向内边距
     * @descEN Vertical padding of list item
     */
    itemPaddingBlock: number | string;
    /**
     * @desc 顶部高度
     * @descEN Height of header
     */
    headerHeight: number | string;
}
export declare const prepareComponentToken: GetDefaultToken<'Transfer'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
