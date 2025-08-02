const toList = (candidate, skipEmpty = false) => {
  if (skipEmpty && (candidate === undefined || candidate === null)) {
    return [];
  }
  return Array.isArray(candidate) ? candidate : [candidate];
};
export default toList;