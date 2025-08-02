export interface RowContextState {
    gutter?: [number, number];
    wrap?: boolean;
}
declare const RowContext: React.Context<RowContextState>;
export default RowContext;
