import * as React from 'react';
import type { OnCustomizeScroll, ScrollConfig } from '../interface';
export interface GridProps<RecordType = any> {
    data: RecordType[];
    onScroll: OnCustomizeScroll;
}
export interface GridRef {
    scrollLeft: number;
    nativeElement: HTMLDivElement;
    scrollTo: (scrollConfig: ScrollConfig) => void;
}
declare const ResponseGrid: React.ForwardRefExoticComponent<GridProps<any> & React.RefAttributes<GridRef>>;
export default ResponseGrid;
