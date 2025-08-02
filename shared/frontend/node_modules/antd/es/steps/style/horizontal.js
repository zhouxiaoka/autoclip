const genHorizontalStyle = token => {
  const {
    componentCls
  } = token;
  const stepsItemCls = `${componentCls}-item`; // .ant-steps-item
  return {
    [`${componentCls}-horizontal`]: {
      [`${stepsItemCls}-tail`]: {
        transform: 'translateY(-50%)'
      }
    }
  };
};
export default genHorizontalStyle;