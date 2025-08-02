import React from 'react';
import type { Locale } from '../locale';
import type { QRCodeProps, StatusRenderInfo } from './interface';
export type QRcodeStatusProps = {
    prefixCls: string;
    locale?: Locale['QRCode'];
    onRefresh?: QRCodeProps['onRefresh'];
    statusRender?: QRCodeProps['statusRender'];
    status: StatusRenderInfo['status'];
};
export default function QRcodeStatus({ prefixCls, locale, onRefresh, statusRender, status, }: QRcodeStatusProps): React.ReactNode;
