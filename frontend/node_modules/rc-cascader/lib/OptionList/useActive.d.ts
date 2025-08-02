import * as React from 'react';
/**
 * Control the active open options path.
 */
declare const useActive: (multiple?: boolean, open?: boolean) => [React.Key[], (activeValueCells: React.Key[]) => void];
export default useActive;
