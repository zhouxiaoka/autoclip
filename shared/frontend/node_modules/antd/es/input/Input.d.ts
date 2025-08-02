import React from 'react';
import type { InputRef, InputProps as RcInputProps } from 'rc-input';
import { InputFocusOptions, triggerFocus } from 'rc-input/lib/utils/commonUtils';
import type { InputStatus } from '../_util/statusUtils';
import type { Variant } from '../config-provider';
import type { SizeType } from '../config-provider/SizeContext';
export type { InputFocusOptions };
export type { InputRef };
export { triggerFocus };
export interface InputProps extends Omit<RcInputProps, 'wrapperClassName' | 'groupClassName' | 'inputClassName' | 'affixWrapperClassName' | 'classes'> {
    rootClassName?: string;
    size?: SizeType;
    disabled?: boolean;
    status?: InputStatus;
    /** @deprecated Use `variant="borderless"` instead. */
    bordered?: boolean;
    /**
     * @since 5.13.0
     * @default "outlined"
     */
    variant?: Variant;
    [key: `data-${string}`]: string | undefined;
}
declare const Input: React.ForwardRefExoticComponent<InputProps & React.RefAttributes<InputRef>>;
export default Input;
