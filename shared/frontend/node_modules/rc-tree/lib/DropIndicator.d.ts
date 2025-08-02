import React from 'react';
export interface DropIndicatorProps {
    dropPosition: -1 | 0 | 1;
    dropLevelOffset: number;
    indent: number;
}
declare const DropIndicator: React.FC<Readonly<DropIndicatorProps>>;
export default DropIndicator;
