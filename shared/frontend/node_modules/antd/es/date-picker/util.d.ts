import * as React from 'react';
import type { PickerMode } from 'rc-picker/lib/interface';
import type { PickerLocale, PickerProps } from './generatePicker';
export declare function getPlaceholder(locale: PickerLocale, picker?: PickerMode, customizePlaceholder?: string): string;
export declare function getRangePlaceholder(locale: PickerLocale, picker?: PickerMode, customizePlaceholder?: [string, string]): [string, string] | undefined;
export declare function useIcons(props: Pick<PickerProps, 'allowClear' | 'removeIcon'>, prefixCls: string): readonly [false | {
    clearIcon: React.ReactNode;
}, string | number | bigint | boolean | Iterable<React.ReactNode> | Promise<string | number | bigint | boolean | React.ReactPortal | React.ReactElement<unknown, string | React.JSXElementConstructor<any>> | Iterable<React.ReactNode> | null | undefined> | React.JSX.Element | ((props: any) => React.ReactNode) | null];
