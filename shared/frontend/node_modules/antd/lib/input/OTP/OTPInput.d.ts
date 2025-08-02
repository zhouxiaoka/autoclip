import * as React from 'react';
import type { InputProps, InputRef } from '../Input';
export interface OTPInputProps extends Omit<InputProps, 'onChange'> {
    index: number;
    onChange: (index: number, value: string) => void;
    /** Tell parent to do active offset */
    onActiveChange: (nextIndex: number) => void;
    mask?: boolean | string;
}
declare const OTPInput: React.ForwardRefExoticComponent<OTPInputProps & React.RefAttributes<InputRef>>;
export default OTPInput;
