import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 链接纵向内间距
     * @descEN Vertical padding of link
     */
    linkPaddingBlock: number;
    /**
     * @desc 链接横向内间距
     * @descEN Horizontal padding of link
     */
    linkPaddingInlineStart: number;
}
export declare const prepareComponentToken: GetDefaultToken<'Anchor'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
