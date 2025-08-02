import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 卡片头部背景色
     * @descEN Background color of card header
     */
    headerBg: string;
    /**
     * @desc 卡片头部文字大小
     * @descEN Font size of card header
     */
    headerFontSize: number | string;
    /**
     * @desc 小号卡片头部文字大小
     * @descEN Font size of small card header
     */
    headerFontSizeSM: number | string;
    /**
     * @desc 卡片头部高度
     * @descEN Height of card header
     */
    headerHeight: number | string;
    /**
     * @desc 小号卡片头部高度
     * @descEN Height of small card header
     */
    headerHeightSM: number | string;
    /**
     * @desc 小号卡片内边距
     * @descEN Padding of small card body
     */
    bodyPaddingSM: number;
    /**
     * @desc 小号卡片头部内边距
     * @descEN Padding of small card head
     */
    headerPaddingSM: number;
    /**
     * @desc 卡片内边距
     * @descEN Padding of card body
     */
    bodyPadding: number;
    /**
     * @desc 卡片头部内边距
     * @descEN Padding of card head
     */
    headerPadding: number;
    /**
     * @desc 操作区背景色
     * @descEN Background color of card actions
     */
    actionsBg: string;
    /**
     * @desc 操作区每一项的外间距
     * @descEN Margin of each item in card actions
     */
    actionsLiMargin: string;
    /**
     * @desc 内置标签页组件下间距
     * @descEN Margin bottom of tabs component
     */
    tabsMarginBottom: number;
    /**
     * @desc 额外区文字颜色
     * @descEN Text color of extra area
     */
    extraColor: string;
}
export declare const prepareComponentToken: GetDefaultToken<'Card'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
