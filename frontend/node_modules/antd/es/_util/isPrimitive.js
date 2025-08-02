const isPrimitive = value => typeof value !== 'object' && typeof value !== 'function' || value === null;
export default isPrimitive;