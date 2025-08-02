import React from 'react';
/**
 * When click on the label,
 * the event will be stopped to prevent the label from being clicked twice.
 * label click -> input click -> label click again
 */
export default function useBubbleLock(onOriginInputClick?: React.MouseEventHandler<HTMLInputElement>): readonly [React.MouseEventHandler<HTMLLabelElement>, React.MouseEventHandler<HTMLInputElement>];
