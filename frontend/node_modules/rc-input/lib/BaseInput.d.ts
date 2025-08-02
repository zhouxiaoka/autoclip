import React from 'react';
import type { BaseInputProps } from './interface';
export interface HolderRef {
    /** Provider holder ref. Will return `null` if not wrap anything */
    nativeElement: HTMLElement | null;
}
declare const BaseInput: React.ForwardRefExoticComponent<BaseInputProps & React.RefAttributes<HolderRef>>;
export default BaseInput;
