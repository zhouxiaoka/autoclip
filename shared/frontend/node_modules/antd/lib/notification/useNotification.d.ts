import React from 'react';
import type { NotificationConfig, NotificationInstance } from './interface';
type HolderProps = NotificationConfig & {
    onAllRemoved?: VoidFunction;
};
export declare function useInternalNotification(notificationConfig?: HolderProps): readonly [NotificationInstance, React.ReactElement];
export default function useNotification(notificationConfig?: NotificationConfig): readonly [NotificationInstance, React.ReactElement<unknown, string | React.JSXElementConstructor<any>>];
export {};
