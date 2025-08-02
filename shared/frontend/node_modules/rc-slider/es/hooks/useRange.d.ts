import type { SliderProps } from '../Slider';
export default function useRange(range?: SliderProps['range']): [
    range: boolean,
    rangeEditable: boolean,
    rangeDraggableTrack: boolean,
    minCount: number,
    maxCount?: number
];
