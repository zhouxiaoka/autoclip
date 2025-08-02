import React from 'react';
export declare function isDOM(node: any): node is HTMLElement | SVGElement;
/**
 * Retrieves a DOM node via a ref, and does not invoke `findDOMNode`.
 */
export declare function getDOM(node: any): HTMLElement | SVGElement | null;
/**
 * Return if a node is a DOM node. Else will return by `findDOMNode`
 */
export default function findDOMNode<T = Element | Text>(node: React.ReactInstance | HTMLElement | SVGElement | {
    nativeElement: T;
}): T;
