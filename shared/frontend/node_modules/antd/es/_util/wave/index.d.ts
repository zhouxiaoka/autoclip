import React from 'react';
import type { WaveComponent } from './interface';
export interface WaveProps {
    disabled?: boolean;
    children?: React.ReactNode;
    component?: WaveComponent;
}
declare const Wave: React.FC<WaveProps>;
export default Wave;
