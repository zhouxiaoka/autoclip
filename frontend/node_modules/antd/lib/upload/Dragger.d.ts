import * as React from 'react';
import type { UploadProps } from './interface';
import type { UploadRef } from './Upload';
export type DraggerProps<T = any> = UploadProps<T> & {
    height?: number;
};
declare const Dragger: React.ForwardRefExoticComponent<UploadProps<any> & {
    height?: number;
} & React.RefAttributes<UploadRef<any>>>;
export default Dragger;
