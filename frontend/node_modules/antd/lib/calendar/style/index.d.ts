import type { CSSObject } from '@ant-design/cssinjs';
import type { PanelComponentToken, PickerPanelToken } from '../../date-picker/style';
import type { FullToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 年选择器宽度
     * @descEN Width of year select
     */
    yearControlWidth: number | string;
    /**
     * @desc 月选择器宽度
     * @descEN Width of month select
     */
    monthControlWidth: number | string;
    /**
     * @desc 迷你日历内容高度
     * @descEN Height of mini calendar content
     */
    miniContentHeight: number | string;
    /**
     * @desc 完整日历背景色
     * @descEN Background color of full calendar
     */
    fullBg: string;
    /**
     * @desc 完整日历面板背景色
     * @descEN Background color of full calendar panel
     */
    fullPanelBg: string;
    /**
     * @desc 日期项选中背景色
     * @descEN Background color of selected date item
     */
    itemActiveBg: string;
}
interface CalendarToken extends FullToken<'Calendar'>, PickerPanelToken, PanelComponentToken {
    /**
     * @desc 日历类名
     * @descEN Calendar class name
     */
    calendarCls: string;
    /**
     * @desc 日期值高度
     * @descEN Date value height
     */
    dateValueHeight: number | string;
    /**
     * @desc 周高度
     * @descEN Week height
     */
    weekHeight: number | string;
    /**
     * @desc 日期内容高度
     * @descEN Date content height
     */
    dateContentHeight: number | string;
}
export declare const genCalendarStyles: (token: CalendarToken) => CSSObject;
export declare const prepareComponentToken: GetDefaultToken<'Calendar'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
