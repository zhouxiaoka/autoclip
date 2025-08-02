import type { TransferKey } from '../interface';
declare function useSelection<T extends {
    key: TransferKey;
}>(leftDataSource: T[], rightDataSource: T[], selectedKeys?: TransferKey[]): [
    sourceSelectedKeys: TransferKey[],
    targetSelectedKeys: TransferKey[],
    setSourceSelectedKeys: (srcKeys: TransferKey[]) => void,
    setTargetSelectedKeys: (srcKeys: TransferKey[]) => void
];
export default useSelection;
