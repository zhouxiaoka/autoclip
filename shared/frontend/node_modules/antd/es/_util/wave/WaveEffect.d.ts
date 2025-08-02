import type { UnmountType } from '../../config-provider/UnstableContext';
import type { ShowWaveEffect } from './interface';
export interface WaveEffectProps {
    className: string;
    target: HTMLElement;
    component?: string;
    registerUnmount: () => UnmountType | null;
}
declare const showWaveEffect: ShowWaveEffect;
export default showWaveEffect;
