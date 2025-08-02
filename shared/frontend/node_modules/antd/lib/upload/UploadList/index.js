"use strict";
"use client";

var _interopRequireWildcard = require("@babel/runtime/helpers/interopRequireWildcard").default;
var _interopRequireDefault = require("@babel/runtime/helpers/interopRequireDefault").default;
Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.default = void 0;
var _toConsumableArray2 = _interopRequireDefault(require("@babel/runtime/helpers/toConsumableArray"));
var React = _interopRequireWildcard(require("react"));
var _FileTwoTone = _interopRequireDefault(require("@ant-design/icons/FileTwoTone"));
var _LoadingOutlined = _interopRequireDefault(require("@ant-design/icons/LoadingOutlined"));
var _PaperClipOutlined = _interopRequireDefault(require("@ant-design/icons/PaperClipOutlined"));
var _PictureTwoTone = _interopRequireDefault(require("@ant-design/icons/PictureTwoTone"));
var _classnames = _interopRequireDefault(require("classnames"));
var _rcMotion = _interopRequireWildcard(require("rc-motion"));
var _omit = _interopRequireDefault(require("rc-util/lib/omit"));
var _useForceUpdate = _interopRequireDefault(require("../../_util/hooks/useForceUpdate"));
var _motion = _interopRequireDefault(require("../../_util/motion"));
var _reactNode = require("../../_util/reactNode");
var _button = _interopRequireDefault(require("../../button"));
var _configProvider = require("../../config-provider");
var _utils = require("../utils");
var _ListItem = _interopRequireDefault(require("./ListItem"));
const InternalUploadList = (props, ref) => {
  const {
    listType = 'text',
    previewFile = _utils.previewImage,
    onPreview,
    onDownload,
    onRemove,
    locale,
    iconRender,
    isImageUrl: isImgUrl = _utils.isImageUrl,
    prefixCls: customizePrefixCls,
    items = [],
    showPreviewIcon = true,
    showRemoveIcon = true,
    showDownloadIcon = false,
    removeIcon,
    previewIcon,
    downloadIcon,
    extra,
    progress = {
      size: [-1, 2],
      showInfo: false
    },
    appendAction,
    appendActionVisible = true,
    itemRender,
    disabled
  } = props;
  const forceUpdate = (0, _useForceUpdate.default)();
  const [motionAppear, setMotionAppear] = React.useState(false);
  const isPictureCardOrCirle = ['picture-card', 'picture-circle'].includes(listType);
  // ============================= Effect =============================
  React.useEffect(() => {
    if (!listType.startsWith('picture')) {
      return;
    }
    (items || []).forEach(file => {
      if (!(file.originFileObj instanceof File || file.originFileObj instanceof Blob) || file.thumbUrl !== undefined) {
        return;
      }
      file.thumbUrl = '';
      previewFile === null || previewFile === void 0 ? void 0 : previewFile(file.originFileObj).then(previewDataUrl => {
        // Need append '' to avoid dead loop
        file.thumbUrl = previewDataUrl || '';
        forceUpdate();
      });
    });
  }, [listType, items, previewFile]);
  React.useEffect(() => {
    setMotionAppear(true);
  }, []);
  // ============================= Events =============================
  const onInternalPreview = (file, e) => {
    if (!onPreview) {
      return;
    }
    e === null || e === void 0 ? void 0 : e.preventDefault();
    return onPreview(file);
  };
  const onInternalDownload = file => {
    if (typeof onDownload === 'function') {
      onDownload(file);
    } else if (file.url) {
      window.open(file.url);
    }
  };
  const onInternalClose = file => {
    onRemove === null || onRemove === void 0 ? void 0 : onRemove(file);
  };
  const internalIconRender = file => {
    if (iconRender) {
      return iconRender(file, listType);
    }
    const isLoading = file.status === 'uploading';
    if (listType.startsWith('picture')) {
      const loadingIcon = listType === 'picture' ? /*#__PURE__*/React.createElement(_LoadingOutlined.default, null) : locale.uploading;
      const fileIcon = (isImgUrl === null || isImgUrl === void 0 ? void 0 : isImgUrl(file)) ? /*#__PURE__*/React.createElement(_PictureTwoTone.default, null) : /*#__PURE__*/React.createElement(_FileTwoTone.default, null);
      return isLoading ? loadingIcon : fileIcon;
    }
    return isLoading ? /*#__PURE__*/React.createElement(_LoadingOutlined.default, null) : /*#__PURE__*/React.createElement(_PaperClipOutlined.default, null);
  };
  const actionIconRender = (customIcon, callback, prefixCls, title, acceptUploadDisabled) => {
    const btnProps = {
      type: 'text',
      size: 'small',
      title,
      onClick: e => {
        var _a, _b;
        callback();
        if (/*#__PURE__*/React.isValidElement(customIcon)) {
          (_b = (_a = customIcon.props).onClick) === null || _b === void 0 ? void 0 : _b.call(_a, e);
        }
      },
      className: `${prefixCls}-list-item-action`,
      disabled: acceptUploadDisabled ? disabled : false
    };
    return /*#__PURE__*/React.isValidElement(customIcon) ? (/*#__PURE__*/React.createElement(_button.default, Object.assign({}, btnProps, {
      icon: (0, _reactNode.cloneElement)(customIcon, Object.assign(Object.assign({}, customIcon.props), {
        onClick: () => {}
      }))
    }))) : (/*#__PURE__*/React.createElement(_button.default, Object.assign({}, btnProps), /*#__PURE__*/React.createElement("span", null, customIcon)));
  };
  // ============================== Ref ===============================
  // Test needs
  React.useImperativeHandle(ref, () => ({
    handlePreview: onInternalPreview,
    handleDownload: onInternalDownload
  }));
  const {
    getPrefixCls
  } = React.useContext(_configProvider.ConfigContext);
  // ============================= Render =============================
  const prefixCls = getPrefixCls('upload', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  const listClassNames = (0, _classnames.default)(`${prefixCls}-list`, `${prefixCls}-list-${listType}`);
  const listItemMotion = React.useMemo(() => (0, _omit.default)((0, _motion.default)(rootPrefixCls), ['onAppearEnd', 'onEnterEnd', 'onLeaveEnd']), [rootPrefixCls]);
  const motionConfig = Object.assign(Object.assign({}, isPictureCardOrCirle ? {} : listItemMotion), {
    motionDeadline: 2000,
    motionName: `${prefixCls}-${isPictureCardOrCirle ? 'animate-inline' : 'animate'}`,
    keys: (0, _toConsumableArray2.default)(items.map(file => ({
      key: file.uid,
      file
    }))),
    motionAppear
  });
  return /*#__PURE__*/React.createElement("div", {
    className: listClassNames
  }, /*#__PURE__*/React.createElement(_rcMotion.CSSMotionList, Object.assign({}, motionConfig, {
    component: false
  }), ({
    key,
    file,
    className: motionClassName,
    style: motionStyle
  }) => (/*#__PURE__*/React.createElement(_ListItem.default, {
    key: key,
    locale: locale,
    prefixCls: prefixCls,
    className: motionClassName,
    style: motionStyle,
    file: file,
    items: items,
    progress: progress,
    listType: listType,
    isImgUrl: isImgUrl,
    showPreviewIcon: showPreviewIcon,
    showRemoveIcon: showRemoveIcon,
    showDownloadIcon: showDownloadIcon,
    removeIcon: removeIcon,
    previewIcon: previewIcon,
    downloadIcon: downloadIcon,
    extra: extra,
    iconRender: internalIconRender,
    actionIconRender: actionIconRender,
    itemRender: itemRender,
    onPreview: onInternalPreview,
    onDownload: onInternalDownload,
    onClose: onInternalClose
  }))), appendAction && (/*#__PURE__*/React.createElement(_rcMotion.default, Object.assign({}, motionConfig, {
    visible: appendActionVisible,
    forceRender: true
  }), ({
    className: motionClassName,
    style: motionStyle
  }) => (0, _reactNode.cloneElement)(appendAction, oriProps => ({
    className: (0, _classnames.default)(oriProps.className, motionClassName),
    style: Object.assign(Object.assign(Object.assign({}, motionStyle), {
      // prevent the element has hover css pseudo-class that may cause animation to end prematurely.
      pointerEvents: motionClassName ? 'none' : undefined
    }), oriProps.style)
  })))));
};
const UploadList = /*#__PURE__*/React.forwardRef(InternalUploadList);
if (process.env.NODE_ENV !== 'production') {
  UploadList.displayName = 'UploadList';
}
var _default = exports.default = UploadList;