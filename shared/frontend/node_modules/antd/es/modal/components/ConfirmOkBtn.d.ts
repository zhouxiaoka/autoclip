import type { FC } from 'react';
import React from 'react';
import type { ConfirmDialogProps } from '../ConfirmDialog';
export interface ConfirmOkBtnProps extends Pick<ConfirmDialogProps, 'close' | 'isSilent' | 'okType' | 'okButtonProps' | 'rootPrefixCls' | 'onConfirm' | 'onOk'> {
    autoFocusButton?: false | 'ok' | 'cancel' | null;
    okTextLocale?: React.ReactNode;
}
declare const ConfirmOkBtn: FC;
export default ConfirmOkBtn;
