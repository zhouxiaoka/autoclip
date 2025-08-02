import type { FC } from 'react';
import React from 'react';
import type { ModalProps } from '../interface';
export interface NormalCancelBtnProps extends Pick<ModalProps, 'cancelButtonProps' | 'onCancel'> {
    cancelTextLocale?: React.ReactNode;
}
declare const NormalCancelBtn: FC;
export default NormalCancelBtn;
