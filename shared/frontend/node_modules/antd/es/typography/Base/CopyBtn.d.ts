import * as React from 'react';
import type { CopyConfig } from '.';
import type { Locale } from '../../locale';
export interface CopyBtnProps extends Omit<CopyConfig, 'onCopy'> {
    prefixCls: string;
    copied: boolean;
    locale: Locale['Text'];
    onCopy: React.MouseEventHandler<HTMLButtonElement>;
    iconOnly: boolean;
    loading: boolean;
}
declare const CopyBtn: React.FC<CopyBtnProps>;
export default CopyBtn;
