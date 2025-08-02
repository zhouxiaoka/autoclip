import type { GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 标题字体大小
     * @descEN Title font size
     */
    titleFontSize: number;
    /**
     * @desc 内容字体大小
     * @descEN Content font size
     */
    contentFontSize: number;
}
export declare const prepareComponentToken: GetDefaultToken<'Statistic'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
