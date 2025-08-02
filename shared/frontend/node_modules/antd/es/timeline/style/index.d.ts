import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 轨迹颜色
     * @descEN Line color
     */
    tailColor: string;
    /**
     * @desc 轨迹宽度
     * @descEN Line width
     */
    tailWidth: number | string;
    /**
     * @desc 节点边框宽度
     * @descEN Border width of node
     */
    dotBorderWidth: number | string;
    /**
     * @desc 节点背景色
     * @descEN Background color of node
     */
    dotBg: string;
    /**
     * @desc 时间项下间距
     * @descEN Bottom padding of item
     */
    itemPaddingBottom: number;
}
export declare const prepareComponentToken: GetDefaultToken<'Timeline'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
