import { merge as mergeToken } from "./statistic";
function getDefaultComponentToken(component, token, getDefaultToken) {
  if (typeof getDefaultToken === 'function') {
    var _token$component;
    return getDefaultToken(mergeToken(token, (_token$component = token[component]) !== null && _token$component !== void 0 ? _token$component : {}));
  }
  return getDefaultToken !== null && getDefaultToken !== void 0 ? getDefaultToken : {};
}
export default getDefaultComponentToken;