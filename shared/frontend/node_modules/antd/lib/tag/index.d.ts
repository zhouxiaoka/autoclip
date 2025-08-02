import * as React from 'react';
import type { PresetColorType, PresetStatusColorType } from '../_util/colors';
import type { ClosableType } from '../_util/hooks/useClosable';
import type { LiteralUnion } from '../_util/type';
import CheckableTag from './CheckableTag';
export type { CheckableTagProps } from './CheckableTag';
export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
    prefixCls?: string;
    className?: string;
    rootClassName?: string;
    color?: LiteralUnion<PresetColorType | PresetStatusColorType>;
    /** Advised to use closeIcon instead. */
    closable?: ClosableType;
    closeIcon?: React.ReactNode;
    /** @deprecated `visible` will be removed in next major version. */
    visible?: boolean;
    onClose?: (e: React.MouseEvent<HTMLElement>) => void;
    style?: React.CSSProperties;
    icon?: React.ReactNode;
    bordered?: boolean;
}
declare const InternalTag: React.ForwardRefExoticComponent<TagProps & React.RefAttributes<HTMLSpanElement>>;
export type TagType = typeof InternalTag & {
    CheckableTag: typeof CheckableTag;
};
declare const Tag: TagType;
export default Tag;
