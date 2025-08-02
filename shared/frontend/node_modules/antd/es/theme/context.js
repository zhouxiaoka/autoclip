import React from 'react';
import defaultSeedToken from './themes/seed';
export { default as defaultTheme } from './themes/default/theme';
// ================================ Context =================================
// To ensure snapshot stable. We disable hashed in test env.
export const defaultConfig = {
  token: defaultSeedToken,
  override: {
    override: defaultSeedToken
  },
  hashed: true
};
export const DesignTokenContext = /*#__PURE__*/React.createContext(defaultConfig);