export const groupKeysMap = keys => {
  const map = new Map();
  keys.forEach((key, index) => {
    map.set(key, index);
  });
  return map;
};
export const groupDisabledKeysMap = dataSource => {
  const map = new Map();
  dataSource.forEach(({
    disabled,
    key
  }, index) => {
    if (disabled) {
      map.set(key, index);
    }
  });
  return map;
};