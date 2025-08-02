"use client";

import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import * as React from 'react';
import FileTwoTone from "@ant-design/icons/es/icons/FileTwoTone";
import LoadingOutlined from "@ant-design/icons/es/icons/LoadingOutlined";
import PaperClipOutlined from "@ant-design/icons/es/icons/PaperClipOutlined";
import PictureTwoTone from "@ant-design/icons/es/icons/PictureTwoTone";
import classNames from 'classnames';
import CSSMotion, { CSSMotionList } from 'rc-motion';
import omit from "rc-util/es/omit";
import useForceUpdate from '../../_util/hooks/useForceUpdate';
import initCollapseMotion from '../../_util/motion';
import { cloneElement } from '../../_util/reactNode';
import Button from '../../button';
import { ConfigContext } from '../../config-provider';
import { isImageUrl, previewImage } from '../utils';
import ListItem from './ListItem';
const InternalUploadList = (props, ref) => {
  const {
    listType = 'text',
    previewFile = previewImage,
    onPreview,
    onDownload,
    onRemove,
    locale,
    iconRender,
    isImageUrl: isImgUrl = isImageUrl,
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
  const forceUpdate = useForceUpdate();
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
      const loadingIcon = listType === 'picture' ? /*#__PURE__*/React.createElement(LoadingOutlined, null) : locale.uploading;
      const fileIcon = (isImgUrl === null || isImgUrl === void 0 ? void 0 : isImgUrl(file)) ? /*#__PURE__*/React.createElement(PictureTwoTone, null) : /*#__PURE__*/React.createElement(FileTwoTone, null);
      return isLoading ? loadingIcon : fileIcon;
    }
    return isLoading ? /*#__PURE__*/React.createElement(LoadingOutlined, null) : /*#__PURE__*/React.createElement(PaperClipOutlined, null);
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
    return /*#__PURE__*/React.isValidElement(customIcon) ? (/*#__PURE__*/React.createElement(Button, Object.assign({}, btnProps, {
      icon: cloneElement(customIcon, Object.assign(Object.assign({}, customIcon.props), {
        onClick: () => {}
      }))
    }))) : (/*#__PURE__*/React.createElement(Button, Object.assign({}, btnProps), /*#__PURE__*/React.createElement("span", null, customIcon)));
  };
  // ============================== Ref ===============================
  // Test needs
  React.useImperativeHandle(ref, () => ({
    handlePreview: onInternalPreview,
    handleDownload: onInternalDownload
  }));
  const {
    getPrefixCls
  } = React.useContext(ConfigContext);
  // ============================= Render =============================
  const prefixCls = getPrefixCls('upload', customizePrefixCls);
  const rootPrefixCls = getPrefixCls();
  const listClassNames = classNames(`${prefixCls}-list`, `${prefixCls}-list-${listType}`);
  const listItemMotion = React.useMemo(() => omit(initCollapseMotion(rootPrefixCls), ['onAppearEnd', 'onEnterEnd', 'onLeaveEnd']), [rootPrefixCls]);
  const motionConfig = Object.assign(Object.assign({}, isPictureCardOrCirle ? {} : listItemMotion), {
    motionDeadline: 2000,
    motionName: `${prefixCls}-${isPictureCardOrCirle ? 'animate-inline' : 'animate'}`,
    keys: _toConsumableArray(items.map(file => ({
      key: file.uid,
      file
    }))),
    motionAppear
  });
  return /*#__PURE__*/React.createElement("div", {
    className: listClassNames
  }, /*#__PURE__*/React.createElement(CSSMotionList, Object.assign({}, motionConfig, {
    component: false
  }), ({
    key,
    file,
    className: motionClassName,
    style: motionStyle
  }) => (/*#__PURE__*/React.createElement(ListItem, {
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
  }))), appendAction && (/*#__PURE__*/React.createElement(CSSMotion, Object.assign({}, motionConfig, {
    visible: appendActionVisible,
    forceRender: true
  }), ({
    className: motionClassName,
    style: motionStyle
  }) => cloneElement(appendAction, oriProps => ({
    className: classNames(oriProps.className, motionClassName),
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
export default UploadList;