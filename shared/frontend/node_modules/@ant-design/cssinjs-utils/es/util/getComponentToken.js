import _slicedToArray from "@babel/runtime/helpers/esm/slicedToArray";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import { warning } from 'rc-util';
function getComponentToken(component, token, defaultToken, options) {
  var customToken = _objectSpread({}, token[component]);
  if (options !== null && options !== void 0 && options.deprecatedTokens) {
    var deprecatedTokens = options.deprecatedTokens;
    deprecatedTokens.forEach(function (_ref) {
      var _ref2 = _slicedToArray(_ref, 2),
        oldTokenKey = _ref2[0],
        newTokenKey = _ref2[1];
      if (process.env.NODE_ENV !== 'production') {
        warning(!(customToken !== null && customToken !== void 0 && customToken[oldTokenKey]), "Component Token `".concat(String(oldTokenKey), "` of ").concat(String(component), " is deprecated. Please use `").concat(String(newTokenKey), "` instead."));
      }

      // Should wrap with `if` clause, or there will be `undefined` in object.
      if (customToken !== null && customToken !== void 0 && customToken[oldTokenKey] || customToken !== null && customToken !== void 0 && customToken[newTokenKey]) {
        var _customToken$newToken;
        (_customToken$newToken = customToken[newTokenKey]) !== null && _customToken$newToken !== void 0 ? _customToken$newToken : customToken[newTokenKey] = customToken === null || customToken === void 0 ? void 0 : customToken[oldTokenKey];
      }
    });
  }
  var mergedToken = _objectSpread(_objectSpread({}, defaultToken), customToken);

  // Remove same value as global token to minimize size
  Object.keys(mergedToken).forEach(function (key) {
    if (mergedToken[key] === token[key]) {
      delete mergedToken[key];
    }
  });
  return mergedToken;
}
export default getComponentToken;