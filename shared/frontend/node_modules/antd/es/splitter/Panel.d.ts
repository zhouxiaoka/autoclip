import React from 'react';
import type { InternalPanelProps, PanelProps } from './interface';
export declare const InternalPanel: React.ForwardRefExoticComponent<InternalPanelProps & {
    children?: React.ReactNode | undefined;
} & React.RefAttributes<HTMLDivElement>>;
declare const Panel: React.FC<React.PropsWithChildren<PanelProps>>;
export default Panel;
