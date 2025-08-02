import type { ReactNode } from 'react';
import React from 'react';
import type { DialogProps } from 'rc-dialog';
import type { HTMLAriaDataAttributes } from '../aria-data-attrs';
export type ClosableType = DialogProps['closable'];
export type BaseContextClosable = {
    closable?: ClosableType;
    closeIcon?: ReactNode;
};
export type ContextClosable<T extends BaseContextClosable = any> = Partial<Pick<T, 'closable' | 'closeIcon'>>;
export declare function pickClosable<T extends BaseContextClosable>(context?: ContextClosable<T>): ContextClosable<T> | undefined;
export type UseClosableParams = {
    closable?: ClosableType;
    closeIcon?: ReactNode;
    defaultClosable?: boolean;
    defaultCloseIcon?: ReactNode;
    customCloseIconRender?: (closeIcon: ReactNode) => ReactNode;
    context?: ContextClosable;
};
/** Collection contains the all the props related with closable. e.g. `closable`, `closeIcon` */
interface ClosableCollection {
    closable?: ClosableType;
    closeIcon?: ReactNode;
}
interface FallbackCloseCollection extends ClosableCollection {
    /**
     * Some components need to wrap CloseIcon twice,
     * this method will be executed once after the final CloseIcon is calculated
     */
    closeIconRender?: (closeIcon: ReactNode) => ReactNode;
}
export default function useClosable(propCloseCollection?: ClosableCollection, contextCloseCollection?: ClosableCollection | null, fallbackCloseCollection?: FallbackCloseCollection): [
    closable: boolean,
    closeIcon: React.ReactNode,
    closeBtnIsDisabled: boolean,
    ariaOrDataProps?: HTMLAriaDataAttributes
];
export {};
