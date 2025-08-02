import * as React from 'react';
import type { BaseSliderProps } from '../components/Slider';
export interface Components {
    slider?: React.ComponentType<BaseSliderProps>;
}
type RequiredComponents = Required<Components>;
export default function useComponent(components?: Components): [Slider: RequiredComponents['slider']];
export {};
