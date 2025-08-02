import type { FullToken, GetDefaultToken } from '../../theme/internal';
export interface ComponentToken {
    /**
     * @desc 操作按扭颜色
     * @descEN Action button color
     */
    actionsColor: string;
}
export interface UploadToken extends FullToken<'Upload'> {
    uploadThumbnailSize: number | string;
    uploadProgressOffset: number | string;
    uploadPicCardSize: number | string;
}
export declare const prepareComponentToken: GetDefaultToken<'Upload'>;
declare const _default: (prefixCls: string, rootCls?: string) => readonly [(node: React.ReactElement) => React.ReactElement, string, string];
export default _default;
