export interface RGB {
    r: number;
    g: number;
    b: number;
    a: number;
}
export interface HSL {
    h: number;
    s: number;
    l: number;
    a: number;
}
export interface HSV {
    h: number;
    s: number;
    v: number;
    a: number;
}
export type OptionalA<T extends {
    a: number;
}> = Omit<T, 'a'> & {
    a?: number;
};
export type ColorInput = string | OptionalA<RGB> | OptionalA<HSL> | OptionalA<HSV>;
