import type { CSSObject } from '@ant-design/cssinjs';
import type { AliasToken, FullToken, GenStyleFn } from '../../theme/internal';
/** Component only token. Which will handle additional calculation of alias token */
export interface ComponentToken {
    /**
     * @desc 提醒框 z-index
     * @descEN z-index of Notification
     */
    zIndexPopup: number;
    /**
     * @desc 提醒框宽度
     * @descEN Width of Notification
     */
    width: number | string;
}
/**
 * @desc Notification 组件的 Token
 * @descEN Token for Notification component
 */
export interface NotificationToken extends FullToken<'Notification'> {
    /**
     * @desc 动画最大高度
     * @descEN Maximum height of animation
     */
    animationMaxHeight: number | string;
    /**
     * @desc 提醒框背景色
     * @descEN Background color of Notification
     */
    notificationBg: string;
    /**
     * @desc 提醒框内边距
     * @descEN Padding of Notification
     */
    notificationPadding: string;
    /**
     * @desc 提醒框垂直内边距
     * @descEN Vertical padding of Notification
     */
    notificationPaddingVertical: number;
    /**
     * @desc 提醒框水平内边距
     * @descEN Horizontal padding of Notification
     */
    notificationPaddingHorizontal: number;
    /**
     * @desc 提醒框图标尺寸
     * @descEN Icon size of Notification
     */
    notificationIconSize: number | string;
    /**
     * @desc 提醒框关闭按钮尺寸
     * @descEN Close button size of Notification
     */
    notificationCloseButtonSize: number | string;
    /**
     * @desc 提醒框底部外边距
     * @descEN Bottom margin of Notification
     */
    notificationMarginBottom: number;
    /**
     * @desc 提醒框边缘外边距
     * @descEN Edge margin of Notification
     */
    notificationMarginEdge: number;
    /**
     * @desc 提醒框堆叠层数
     * @descEN Stack layer of Notification
     */
    notificationStackLayer: number;
    /**
     * @desc 提醒框进度条背景色
     * @descEN Background color of Notification progress bar
     */
    notificationProgressBg: string;
    /**
     * @desc 提醒框进度条高度
     * @descEN Height of Notification progress bar
     */
    notificationProgressHeight: number;
}
export declare const genNoticeStyle: (token: NotificationToken) => CSSObject;
export declare const prepareComponentToken: (token: AliasToken) => {
    zIndexPopup: number;
    width: number;
};
export declare const prepareNotificationToken: (token: Parameters<GenStyleFn<'Notification'>>[0]) => NotificationToken;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
