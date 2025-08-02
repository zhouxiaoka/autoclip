import type { FullToken, GenStyleFn, GetDefaultToken } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 徽标 z-index
     * @descEN z-index of badge
     */
    indicatorZIndex: number | string;
    /**
     * @desc 徽标高度
     * @descEN Height of badge
     */
    indicatorHeight: number | string;
    /**
     * @desc 小号徽标高度
     * @descEN Height of small badge
     */
    indicatorHeightSM: number | string;
    /**
     * @desc 点状徽标尺寸
     * @descEN Size of dot badge
     */
    dotSize: number;
    /**
     * @desc 徽标文本尺寸
     * @descEN Font size of badge text
     */
    textFontSize: number;
    /**
     * @desc 小号徽标文本尺寸
     * @descEN Font size of small badge text
     */
    textFontSizeSM: number;
    /**
     * @desc 徽标文本粗细
     * @descEN Font weight of badge text
     */
    textFontWeight: number | string;
    /**
     * @desc 状态徽标尺寸
     * @descEN Size of status badge
     */
    statusSize: number;
}
/**
 * @desc Badge 组件的 Token
 * @descEN Token for Badge component
 */
export interface BadgeToken extends FullToken<'Badge'> {
    /**
     * @desc 徽标字体高度
     * @descEN Font height of badge
     */
    badgeFontHeight: number;
    /**
     * @desc 徽标文本颜色
     * @descEN Text color of badge
     */
    badgeTextColor: string;
    /**
     * @desc 徽标颜色
     * @descEN Color of badge
     */
    badgeColor: string;
    /**
     * @desc 徽标悬停颜色
     * @descEN Hover color of badge
     */
    badgeColorHover: string;
    /**
     * @desc 徽标阴影尺寸
     * @descEN Shadow size of badge
     */
    badgeShadowSize: number;
    /**
     * @desc 徽标阴影颜色
     * @descEN Shadow color of badge
     */
    badgeShadowColor: string;
    /**
     * @desc 徽标处理持续时间
     * @descEN Processing duration of badge
     */
    badgeProcessingDuration: string;
    /**
     * @desc 徽标丝带偏移量
     * @descEN Ribbon offset of badge
     */
    badgeRibbonOffset: number;
    /**
     * @desc 徽标丝带角变换
     * @descEN Ribbon corner transform of badge
     */
    badgeRibbonCornerTransform: string;
    /**
     * @desc 徽标丝带角滤镜
     * @descEN Ribbon corner filter of badge
     */
    badgeRibbonCornerFilter: string;
}
export declare const prepareToken: (token: Parameters<GenStyleFn<'Badge'>>[0]) => BadgeToken;
export declare const prepareComponentToken: GetDefaultToken<'Badge'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
