import type * as React from 'react';
import type { CSSMotionProps } from 'rc-motion';
import type { NotificationConfig, NotificationPlacement } from './interface';
import type { NotificationConfig as CPNotificationConfig } from '../config-provider/context';
export declare function getPlacementStyle(placement: NotificationPlacement, top: number, bottom: number): React.CSSProperties;
export declare function getMotion(prefixCls: string): CSSMotionProps;
export declare function getCloseIconConfig(closeIcon: React.ReactNode, notificationConfig?: NotificationConfig, notification?: CPNotificationConfig): React.ReactNode;
