import _extends from "@babel/runtime/helpers/esm/extends";
import _objectSpread from "@babel/runtime/helpers/esm/objectSpread2";
import _objectWithoutProperties from "@babel/runtime/helpers/esm/objectWithoutProperties";
import _typeof from "@babel/runtime/helpers/esm/typeof";
import _regeneratorRuntime from "@babel/runtime/helpers/esm/regeneratorRuntime";
import _asyncToGenerator from "@babel/runtime/helpers/esm/asyncToGenerator";
import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import _classCallCheck from "@babel/runtime/helpers/esm/classCallCheck";
import _createClass from "@babel/runtime/helpers/esm/createClass";
import _assertThisInitialized from "@babel/runtime/helpers/esm/assertThisInitialized";
import _inherits from "@babel/runtime/helpers/esm/inherits";
import _createSuper from "@babel/runtime/helpers/esm/createSuper";
import _defineProperty from "@babel/runtime/helpers/esm/defineProperty";
var _excluded = ["component", "prefixCls", "className", "classNames", "disabled", "id", "name", "style", "styles", "multiple", "accept", "capture", "children", "directory", "openFileDialogOnClick", "onMouseEnter", "onMouseLeave", "hasControlInside"];
/* eslint react/no-is-mounted:0,react/sort-comp:0,react/prop-types:0 */
import clsx from 'classnames';
import pickAttrs from "rc-util/es/pickAttrs";
import React, { Component } from 'react';
import attrAccept from "./attr-accept";
import defaultRequest from "./request";
import traverseFileTree from "./traverseFileTree";
import getUid from "./uid";
var AjaxUploader = /*#__PURE__*/function (_Component) {
  _inherits(AjaxUploader, _Component);
  var _super = _createSuper(AjaxUploader);
  function AjaxUploader() {
    var _this;
    _classCallCheck(this, AjaxUploader);
    for (var _len = arguments.length, args = new Array(_len), _key = 0; _key < _len; _key++) {
      args[_key] = arguments[_key];
    }
    _this = _super.call.apply(_super, [this].concat(args));
    _defineProperty(_assertThisInitialized(_this), "state", {
      uid: getUid()
    });
    _defineProperty(_assertThisInitialized(_this), "reqs", {});
    _defineProperty(_assertThisInitialized(_this), "fileInput", void 0);
    _defineProperty(_assertThisInitialized(_this), "_isMounted", void 0);
    _defineProperty(_assertThisInitialized(_this), "onChange", function (e) {
      var _this$props = _this.props,
        accept = _this$props.accept,
        directory = _this$props.directory;
      var files = e.target.files;
      var acceptedFiles = _toConsumableArray(files).filter(function (file) {
        return !directory || attrAccept(file, accept);
      });
      _this.uploadFiles(acceptedFiles);
      _this.reset();
    });
    _defineProperty(_assertThisInitialized(_this), "onClick", function (event) {
      var el = _this.fileInput;
      if (!el) {
        return;
      }
      var target = event.target;
      var onClick = _this.props.onClick;
      if (target && target.tagName === 'BUTTON') {
        var parent = el.parentNode;
        parent.focus();
        target.blur();
      }
      el.click();
      if (onClick) {
        onClick(event);
      }
    });
    _defineProperty(_assertThisInitialized(_this), "onKeyDown", function (e) {
      if (e.key === 'Enter') {
        _this.onClick(e);
      }
    });
    _defineProperty(_assertThisInitialized(_this), "onDataTransferFiles", /*#__PURE__*/function () {
      var _ref = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee(dataTransfer, existFileCallback) {
        var _this$props2, multiple, accept, directory, items, files, acceptFiles;
        return _regeneratorRuntime().wrap(function _callee$(_context) {
          while (1) switch (_context.prev = _context.next) {
            case 0:
              _this$props2 = _this.props, multiple = _this$props2.multiple, accept = _this$props2.accept, directory = _this$props2.directory;
              items = _toConsumableArray(dataTransfer.items || []);
              files = _toConsumableArray(dataTransfer.files || []);
              if (files.length > 0 || items.some(function (item) {
                return item.kind === 'file';
              })) {
                existFileCallback === null || existFileCallback === void 0 || existFileCallback();
              }
              if (!directory) {
                _context.next = 11;
                break;
              }
              _context.next = 7;
              return traverseFileTree(Array.prototype.slice.call(items), function (_file) {
                return attrAccept(_file, _this.props.accept);
              });
            case 7:
              files = _context.sent;
              _this.uploadFiles(files);
              _context.next = 14;
              break;
            case 11:
              acceptFiles = _toConsumableArray(files).filter(function (file) {
                return attrAccept(file, accept);
              });
              if (multiple === false) {
                acceptFiles = files.slice(0, 1);
              }
              _this.uploadFiles(acceptFiles);
            case 14:
            case "end":
              return _context.stop();
          }
        }, _callee);
      }));
      return function (_x, _x2) {
        return _ref.apply(this, arguments);
      };
    }());
    _defineProperty(_assertThisInitialized(_this), "onFilePaste", /*#__PURE__*/function () {
      var _ref2 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee2(e) {
        var pastable, clipboardData;
        return _regeneratorRuntime().wrap(function _callee2$(_context2) {
          while (1) switch (_context2.prev = _context2.next) {
            case 0:
              pastable = _this.props.pastable;
              if (pastable) {
                _context2.next = 3;
                break;
              }
              return _context2.abrupt("return");
            case 3:
              if (!(e.type === 'paste')) {
                _context2.next = 6;
                break;
              }
              clipboardData = e.clipboardData;
              return _context2.abrupt("return", _this.onDataTransferFiles(clipboardData, function () {
                e.preventDefault();
              }));
            case 6:
            case "end":
              return _context2.stop();
          }
        }, _callee2);
      }));
      return function (_x3) {
        return _ref2.apply(this, arguments);
      };
    }());
    _defineProperty(_assertThisInitialized(_this), "onFileDragOver", function (e) {
      e.preventDefault();
    });
    _defineProperty(_assertThisInitialized(_this), "onFileDrop", /*#__PURE__*/function () {
      var _ref3 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee3(e) {
        var dataTransfer;
        return _regeneratorRuntime().wrap(function _callee3$(_context3) {
          while (1) switch (_context3.prev = _context3.next) {
            case 0:
              e.preventDefault();
              if (!(e.type === 'drop')) {
                _context3.next = 4;
                break;
              }
              dataTransfer = e.dataTransfer;
              return _context3.abrupt("return", _this.onDataTransferFiles(dataTransfer));
            case 4:
            case "end":
              return _context3.stop();
          }
        }, _callee3);
      }));
      return function (_x4) {
        return _ref3.apply(this, arguments);
      };
    }());
    _defineProperty(_assertThisInitialized(_this), "uploadFiles", function (files) {
      var originFiles = _toConsumableArray(files);
      var postFiles = originFiles.map(function (file) {
        // eslint-disable-next-line no-param-reassign
        file.uid = getUid();
        return _this.processFile(file, originFiles);
      });

      // Batch upload files
      Promise.all(postFiles).then(function (fileList) {
        var onBatchStart = _this.props.onBatchStart;
        onBatchStart === null || onBatchStart === void 0 || onBatchStart(fileList.map(function (_ref4) {
          var origin = _ref4.origin,
            parsedFile = _ref4.parsedFile;
          return {
            file: origin,
            parsedFile: parsedFile
          };
        }));
        fileList.filter(function (file) {
          return file.parsedFile !== null;
        }).forEach(function (file) {
          _this.post(file);
        });
      });
    });
    /**
     * Process file before upload. When all the file is ready, we start upload.
     */
    _defineProperty(_assertThisInitialized(_this), "processFile", /*#__PURE__*/function () {
      var _ref5 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee4(file, fileList) {
        var beforeUpload, transformedFile, action, mergedAction, data, mergedData, parsedData, parsedFile, mergedParsedFile;
        return _regeneratorRuntime().wrap(function _callee4$(_context4) {
          while (1) switch (_context4.prev = _context4.next) {
            case 0:
              beforeUpload = _this.props.beforeUpload;
              transformedFile = file;
              if (!beforeUpload) {
                _context4.next = 14;
                break;
              }
              _context4.prev = 3;
              _context4.next = 6;
              return beforeUpload(file, fileList);
            case 6:
              transformedFile = _context4.sent;
              _context4.next = 12;
              break;
            case 9:
              _context4.prev = 9;
              _context4.t0 = _context4["catch"](3);
              // Rejection will also trade as false
              transformedFile = false;
            case 12:
              if (!(transformedFile === false)) {
                _context4.next = 14;
                break;
              }
              return _context4.abrupt("return", {
                origin: file,
                parsedFile: null,
                action: null,
                data: null
              });
            case 14:
              // Get latest action
              action = _this.props.action;
              if (!(typeof action === 'function')) {
                _context4.next = 21;
                break;
              }
              _context4.next = 18;
              return action(file);
            case 18:
              mergedAction = _context4.sent;
              _context4.next = 22;
              break;
            case 21:
              mergedAction = action;
            case 22:
              // Get latest data
              data = _this.props.data;
              if (!(typeof data === 'function')) {
                _context4.next = 29;
                break;
              }
              _context4.next = 26;
              return data(file);
            case 26:
              mergedData = _context4.sent;
              _context4.next = 30;
              break;
            case 29:
              mergedData = data;
            case 30:
              parsedData =
              // string type is from legacy `transformFile`.
              // Not sure if this will work since no related test case works with it
              (_typeof(transformedFile) === 'object' || typeof transformedFile === 'string') && transformedFile ? transformedFile : file;
              if (parsedData instanceof File) {
                parsedFile = parsedData;
              } else {
                parsedFile = new File([parsedData], file.name, {
                  type: file.type
                });
              }
              mergedParsedFile = parsedFile;
              mergedParsedFile.uid = file.uid;
              return _context4.abrupt("return", {
                origin: file,
                data: mergedData,
                parsedFile: mergedParsedFile,
                action: mergedAction
              });
            case 35:
            case "end":
              return _context4.stop();
          }
        }, _callee4, null, [[3, 9]]);
      }));
      return function (_x5, _x6) {
        return _ref5.apply(this, arguments);
      };
    }());
    _defineProperty(_assertThisInitialized(_this), "saveFileInput", function (node) {
      _this.fileInput = node;
    });
    return _this;
  }
  _createClass(AjaxUploader, [{
    key: "componentDidMount",
    value: function componentDidMount() {
      this._isMounted = true;
      var pastable = this.props.pastable;
      if (pastable) {
        document.addEventListener('paste', this.onFilePaste);
      }
    }
  }, {
    key: "componentWillUnmount",
    value: function componentWillUnmount() {
      this._isMounted = false;
      this.abort();
      document.removeEventListener('paste', this.onFilePaste);
    }
  }, {
    key: "componentDidUpdate",
    value: function componentDidUpdate(prevProps) {
      var pastable = this.props.pastable;
      if (pastable && !prevProps.pastable) {
        document.addEventListener('paste', this.onFilePaste);
      } else if (!pastable && prevProps.pastable) {
        document.removeEventListener('paste', this.onFilePaste);
      }
    }
  }, {
    key: "post",
    value: function post(_ref6) {
      var _this2 = this;
      var data = _ref6.data,
        origin = _ref6.origin,
        action = _ref6.action,
        parsedFile = _ref6.parsedFile;
      if (!this._isMounted) {
        return;
      }
      var _this$props3 = this.props,
        onStart = _this$props3.onStart,
        customRequest = _this$props3.customRequest,
        name = _this$props3.name,
        headers = _this$props3.headers,
        withCredentials = _this$props3.withCredentials,
        method = _this$props3.method;
      var uid = origin.uid;
      var request = customRequest || defaultRequest;
      var requestOption = {
        action: action,
        filename: name,
        data: data,
        file: parsedFile,
        headers: headers,
        withCredentials: withCredentials,
        method: method || 'post',
        onProgress: function onProgress(e) {
          var onProgress = _this2.props.onProgress;
          onProgress === null || onProgress === void 0 || onProgress(e, parsedFile);
        },
        onSuccess: function onSuccess(ret, xhr) {
          var onSuccess = _this2.props.onSuccess;
          onSuccess === null || onSuccess === void 0 || onSuccess(ret, parsedFile, xhr);
          delete _this2.reqs[uid];
        },
        onError: function onError(err, ret) {
          var onError = _this2.props.onError;
          onError === null || onError === void 0 || onError(err, ret, parsedFile);
          delete _this2.reqs[uid];
        }
      };
      onStart(origin);
      this.reqs[uid] = request(requestOption);
    }
  }, {
    key: "reset",
    value: function reset() {
      this.setState({
        uid: getUid()
      });
    }
  }, {
    key: "abort",
    value: function abort(file) {
      var reqs = this.reqs;
      if (file) {
        var uid = file.uid ? file.uid : file;
        if (reqs[uid] && reqs[uid].abort) {
          reqs[uid].abort();
        }
        delete reqs[uid];
      } else {
        Object.keys(reqs).forEach(function (uid) {
          if (reqs[uid] && reqs[uid].abort) {
            reqs[uid].abort();
          }
          delete reqs[uid];
        });
      }
    }
  }, {
    key: "render",
    value: function render() {
      var _this$props4 = this.props,
        Tag = _this$props4.component,
        prefixCls = _this$props4.prefixCls,
        className = _this$props4.className,
        _this$props4$classNam = _this$props4.classNames,
        classNames = _this$props4$classNam === void 0 ? {} : _this$props4$classNam,
        disabled = _this$props4.disabled,
        id = _this$props4.id,
        name = _this$props4.name,
        style = _this$props4.style,
        _this$props4$styles = _this$props4.styles,
        styles = _this$props4$styles === void 0 ? {} : _this$props4$styles,
        multiple = _this$props4.multiple,
        accept = _this$props4.accept,
        capture = _this$props4.capture,
        children = _this$props4.children,
        directory = _this$props4.directory,
        openFileDialogOnClick = _this$props4.openFileDialogOnClick,
        onMouseEnter = _this$props4.onMouseEnter,
        onMouseLeave = _this$props4.onMouseLeave,
        hasControlInside = _this$props4.hasControlInside,
        otherProps = _objectWithoutProperties(_this$props4, _excluded);
      var cls = clsx(_defineProperty(_defineProperty(_defineProperty({}, prefixCls, true), "".concat(prefixCls, "-disabled"), disabled), className, className));
      // because input don't have directory/webkitdirectory type declaration
      var dirProps = directory ? {
        directory: 'directory',
        webkitdirectory: 'webkitdirectory'
      } : {};
      var events = disabled ? {} : {
        onClick: openFileDialogOnClick ? this.onClick : function () {},
        onKeyDown: openFileDialogOnClick ? this.onKeyDown : function () {},
        onMouseEnter: onMouseEnter,
        onMouseLeave: onMouseLeave,
        onDrop: this.onFileDrop,
        onDragOver: this.onFileDragOver,
        tabIndex: hasControlInside ? undefined : '0'
      };
      return /*#__PURE__*/React.createElement(Tag, _extends({}, events, {
        className: cls,
        role: hasControlInside ? undefined : 'button',
        style: style
      }), /*#__PURE__*/React.createElement("input", _extends({}, pickAttrs(otherProps, {
        aria: true,
        data: true
      }), {
        id: id
        /**
         * https://github.com/ant-design/ant-design/issues/50643,
         * https://github.com/react-component/upload/pull/575#issuecomment-2320646552
         */,
        name: name,
        disabled: disabled,
        type: "file",
        ref: this.saveFileInput,
        onClick: function onClick(e) {
          return e.stopPropagation();
        } // https://github.com/ant-design/ant-design/issues/19948
        ,
        key: this.state.uid,
        style: _objectSpread({
          display: 'none'
        }, styles.input),
        className: classNames.input,
        accept: accept
      }, dirProps, {
        multiple: multiple,
        onChange: this.onChange
      }, capture != null ? {
        capture: capture
      } : {})), children);
    }
  }]);
  return AjaxUploader;
}(Component);
export default AjaxUploader;