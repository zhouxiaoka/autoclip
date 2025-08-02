import _regeneratorRuntime from "@babel/runtime/helpers/esm/regeneratorRuntime";
import _toConsumableArray from "@babel/runtime/helpers/esm/toConsumableArray";
import _asyncToGenerator from "@babel/runtime/helpers/esm/asyncToGenerator";
// https://github.com/ant-design/ant-design/issues/50080
var traverseFileTree = /*#__PURE__*/function () {
  var _ref = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee4(files, isAccepted) {
    var flattenFileList, progressFileList, readDirectory, _readDirectory, readFile, _readFile, _traverseFileTree, wipIndex;
    return _regeneratorRuntime().wrap(function _callee4$(_context4) {
      while (1) switch (_context4.prev = _context4.next) {
        case 0:
          _readFile = function _readFile3() {
            _readFile = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee3(item) {
              return _regeneratorRuntime().wrap(function _callee3$(_context3) {
                while (1) switch (_context3.prev = _context3.next) {
                  case 0:
                    return _context3.abrupt("return", new Promise(function (reslove) {
                      item.file(function (file) {
                        if (isAccepted(file)) {
                          // https://github.com/ant-design/ant-design/issues/16426
                          if (item.fullPath && !file.webkitRelativePath) {
                            Object.defineProperties(file, {
                              webkitRelativePath: {
                                writable: true
                              }
                            });
                            // eslint-disable-next-line no-param-reassign
                            file.webkitRelativePath = item.fullPath.replace(/^\//, '');
                            Object.defineProperties(file, {
                              webkitRelativePath: {
                                writable: false
                              }
                            });
                          }
                          reslove(file);
                        } else {
                          reslove(null);
                        }
                      });
                    }));
                  case 1:
                  case "end":
                    return _context3.stop();
                }
              }, _callee3);
            }));
            return _readFile.apply(this, arguments);
          };
          readFile = function _readFile2(_x4) {
            return _readFile.apply(this, arguments);
          };
          _readDirectory = function _readDirectory3() {
            _readDirectory = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee2(directory) {
              var dirReader, entries, results, n, i;
              return _regeneratorRuntime().wrap(function _callee2$(_context2) {
                while (1) switch (_context2.prev = _context2.next) {
                  case 0:
                    dirReader = directory.createReader();
                    entries = [];
                  case 2:
                    if (!true) {
                      _context2.next = 12;
                      break;
                    }
                    _context2.next = 5;
                    return new Promise(function (resolve) {
                      dirReader.readEntries(resolve, function () {
                        return resolve([]);
                      });
                    });
                  case 5:
                    results = _context2.sent;
                    n = results.length;
                    if (n) {
                      _context2.next = 9;
                      break;
                    }
                    return _context2.abrupt("break", 12);
                  case 9:
                    for (i = 0; i < n; i++) {
                      entries.push(results[i]);
                    }
                    _context2.next = 2;
                    break;
                  case 12:
                    return _context2.abrupt("return", entries);
                  case 13:
                  case "end":
                    return _context2.stop();
                }
              }, _callee2);
            }));
            return _readDirectory.apply(this, arguments);
          };
          readDirectory = function _readDirectory2(_x3) {
            return _readDirectory.apply(this, arguments);
          };
          flattenFileList = [];
          progressFileList = [];
          files.forEach(function (file) {
            return progressFileList.push(file.webkitGetAsEntry());
          });

          // eslint-disable-next-line @typescript-eslint/naming-convention
          _traverseFileTree = /*#__PURE__*/function () {
            var _ref2 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee(item, path) {
              var _file, entries;
              return _regeneratorRuntime().wrap(function _callee$(_context) {
                while (1) switch (_context.prev = _context.next) {
                  case 0:
                    if (item) {
                      _context.next = 2;
                      break;
                    }
                    return _context.abrupt("return");
                  case 2:
                    // eslint-disable-next-line no-param-reassign
                    item.path = path || '';
                    if (!item.isFile) {
                      _context.next = 10;
                      break;
                    }
                    _context.next = 6;
                    return readFile(item);
                  case 6:
                    _file = _context.sent;
                    if (_file) {
                      flattenFileList.push(_file);
                    }
                    _context.next = 15;
                    break;
                  case 10:
                    if (!item.isDirectory) {
                      _context.next = 15;
                      break;
                    }
                    _context.next = 13;
                    return readDirectory(item);
                  case 13:
                    entries = _context.sent;
                    progressFileList.push.apply(progressFileList, _toConsumableArray(entries));
                  case 15:
                  case "end":
                    return _context.stop();
                }
              }, _callee);
            }));
            return function _traverseFileTree(_x5, _x6) {
              return _ref2.apply(this, arguments);
            };
          }();
          wipIndex = 0;
        case 9:
          if (!(wipIndex < progressFileList.length)) {
            _context4.next = 15;
            break;
          }
          _context4.next = 12;
          return _traverseFileTree(progressFileList[wipIndex]);
        case 12:
          wipIndex++;
          _context4.next = 9;
          break;
        case 15:
          return _context4.abrupt("return", flattenFileList);
        case 16:
        case "end":
          return _context4.stop();
      }
    }, _callee4);
  }));
  return function traverseFileTree(_x, _x2) {
    return _ref.apply(this, arguments);
  };
}();
export default traverseFileTree;