'use strict';

const node_path = require('node:path');
const node_url = require('node:url');
const node_fs = require('node:fs');
const vite = require('vite');
const pluginutils = require('@rolldown/pluginutils');

var _documentCurrentScript = typeof document !== 'undefined' ? document.currentScript : null;
function _interopNamespaceCompat(e) {
  if (e && typeof e === 'object' && 'default' in e) return e;
  const n = Object.create(null);
  if (e) {
    for (const k in e) {
      n[k] = e[k];
    }
  }
  n.default = e;
  return n;
}

const vite__namespace = /*#__PURE__*/_interopNamespaceCompat(vite);

const runtimePublicPath = "/@react-refresh";
const reactCompRE = /extends\s+(?:React\.)?(?:Pure)?Component/;
const refreshContentRE = /\$RefreshReg\$\(/;
const preambleCode = `import { injectIntoGlobalHook } from "__BASE__${runtimePublicPath.slice(
  1
)}";
injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {};
window.$RefreshSig$ = () => (type) => type;`;
const getPreambleCode = (base) => preambleCode.replace("__BASE__", base);
const avoidSourceMapOption = Symbol();
function addRefreshWrapper(code, map, pluginName, id, reactRefreshHost = "") {
  const hasRefresh = refreshContentRE.test(code);
  const onlyReactComp = !hasRefresh && reactCompRE.test(code);
  const normalizedMap = map === avoidSourceMapOption ? null : map;
  if (!hasRefresh && !onlyReactComp) return { code, map: normalizedMap };
  const avoidSourceMap = map === avoidSourceMapOption;
  const newMap = typeof normalizedMap === "string" ? JSON.parse(normalizedMap) : normalizedMap;
  let newCode = code;
  if (hasRefresh) {
    const refreshHead = removeLineBreaksIfNeeded(
      `let prevRefreshReg;
let prevRefreshSig;

if (import.meta.hot && !inWebWorker) {
  if (!window.$RefreshReg$) {
    throw new Error(
      "${pluginName} can't detect preamble. Something is wrong."
    );
  }

  prevRefreshReg = window.$RefreshReg$;
  prevRefreshSig = window.$RefreshSig$;
  window.$RefreshReg$ = RefreshRuntime.getRefreshReg(${JSON.stringify(id)});
  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;
}

`,
      avoidSourceMap
    );
    newCode = `${refreshHead}${newCode}

if (import.meta.hot && !inWebWorker) {
  window.$RefreshReg$ = prevRefreshReg;
  window.$RefreshSig$ = prevRefreshSig;
}
`;
    if (newMap) {
      newMap.mappings = ";".repeat(16) + newMap.mappings;
    }
  }
  const sharedHead = removeLineBreaksIfNeeded(
    `import * as RefreshRuntime from "${reactRefreshHost}${runtimePublicPath}";
const inWebWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;

`,
    avoidSourceMap
  );
  newCode = `${sharedHead}${newCode}

if (import.meta.hot && !inWebWorker) {
  RefreshRuntime.__hmr_import(import.meta.url).then((currentExports) => {
    RefreshRuntime.registerExportsForReactRefresh(${JSON.stringify(
    id
  )}, currentExports);
    import.meta.hot.accept((nextExports) => {
      if (!nextExports) return;
      const invalidateMessage = RefreshRuntime.validateRefreshBoundaryAndEnqueueUpdate(${JSON.stringify(
    id
  )}, currentExports, nextExports);
      if (invalidateMessage) import.meta.hot.invalidate(invalidateMessage);
    });
  });
}
`;
  if (newMap) {
    newMap.mappings = ";;;" + newMap.mappings;
  }
  return { code: newCode, map: newMap };
}
function removeLineBreaksIfNeeded(code, enabled) {
  return enabled ? code.replace(/\n/g, "") : code;
}

const silenceUseClientWarning = (userConfig) => ({
  rollupOptions: {
    onwarn(warning, defaultHandler) {
      if (warning.code === "MODULE_LEVEL_DIRECTIVE" && (warning.message.includes("use client") || warning.message.includes("use server"))) {
        return;
      }
      if (warning.code === "SOURCEMAP_ERROR" && warning.message.includes("resolve original location") && warning.pos === 0) {
        return;
      }
      if (userConfig.build?.rollupOptions?.onwarn) {
        userConfig.build.rollupOptions.onwarn(warning, defaultHandler);
      } else {
        defaultHandler(warning);
      }
    }
  }
});

const _dirname = node_path.dirname(node_url.fileURLToPath((typeof document === 'undefined' ? require('u' + 'rl').pathToFileURL(__filename).href : (_documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === 'SCRIPT' && _documentCurrentScript.src || new URL('index.cjs', document.baseURI).href))));
const refreshRuntimePath = node_path.join(_dirname, "refresh-runtime.js") ;
let babel;
async function loadBabel() {
  if (!babel) {
    babel = await import('@babel/core');
  }
  return babel;
}
const defaultIncludeRE = /\.[tj]sx?$/;
const tsRE = /\.tsx?$/;
function viteReact(opts = {}) {
  const include = opts.include ?? defaultIncludeRE;
  const exclude = opts.exclude;
  const filter = vite.createFilter(include, exclude);
  const jsxImportSource = opts.jsxImportSource ?? "react";
  const jsxImportRuntime = `${jsxImportSource}/jsx-runtime`;
  const jsxImportDevRuntime = `${jsxImportSource}/jsx-dev-runtime`;
  let runningInVite = false;
  let isProduction = true;
  let projectRoot = process.cwd();
  let skipFastRefresh = true;
  let runPluginOverrides;
  let staticBabelOptions;
  const importReactRE = /\bimport\s+(?:\*\s+as\s+)?React\b/;
  const viteBabel = {
    name: "vite:react-babel",
    enforce: "pre",
    config() {
      if (opts.jsxRuntime === "classic") {
        if ("rolldownVersion" in vite__namespace) {
          return {
            oxc: {
              jsx: {
                runtime: "classic",
                // disable __self and __source injection even in dev
                // as this plugin injects them by babel and oxc will throw
                // if development is enabled and those properties are already present
                development: false
              }
            }
          };
        } else {
          return {
            esbuild: {
              jsx: "transform"
            }
          };
        }
      } else {
        return {
          esbuild: {
            jsx: "automatic",
            jsxImportSource: opts.jsxImportSource
          },
          optimizeDeps: "rolldownVersion" in vite__namespace ? { rollupOptions: { jsx: { mode: "automatic" } } } : { esbuildOptions: { jsx: "automatic" } }
        };
      }
    },
    configResolved(config) {
      runningInVite = true;
      projectRoot = config.root;
      isProduction = config.isProduction;
      skipFastRefresh = isProduction || config.command === "build" || config.server.hmr === false;
      if ("jsxPure" in opts) {
        config.logger.warnOnce(
          "[@vitejs/plugin-react] jsxPure was removed. You can configure esbuild.jsxSideEffects directly."
        );
      }
      const hooks = config.plugins.map((plugin) => plugin.api?.reactBabel).filter(defined);
      if ("rolldownVersion" in vite__namespace && !opts.babel && !hooks.length && !opts.disableOxcRecommendation) {
        config.logger.warn(
          "[vite:react-babel] We recommend switching to `@vitejs/plugin-react-oxc` for improved performance. More information at https://vite.dev/rolldown"
        );
      }
      if (hooks.length > 0) {
        runPluginOverrides = (babelOptions, context) => {
          hooks.forEach((hook) => hook(babelOptions, context, config));
        };
      } else if (typeof opts.babel !== "function") {
        staticBabelOptions = createBabelOptions(opts.babel);
        if (canSkipBabel(staticBabelOptions.plugins, staticBabelOptions) && skipFastRefresh && (opts.jsxRuntime === "classic" ? isProduction : true)) {
          delete viteBabel.transform;
        }
      }
    },
    options(options) {
      if (!runningInVite) {
        options.jsx = {
          mode: opts.jsxRuntime,
          importSource: opts.jsxImportSource
        };
        return options;
      }
    },
    transform: {
      filter: {
        id: {
          include: pluginutils.makeIdFiltersToMatchWithQuery(include),
          exclude: [
            ...exclude ? pluginutils.makeIdFiltersToMatchWithQuery(ensureArray(exclude)) : [],
            /\/node_modules\//
          ]
        }
      },
      async handler(code, id, options) {
        if (id.includes("/node_modules/")) return;
        const [filepath] = id.split("?");
        if (!filter(filepath)) return;
        const ssr = options?.ssr === true;
        const babelOptions = (() => {
          if (staticBabelOptions) return staticBabelOptions;
          const newBabelOptions = createBabelOptions(
            typeof opts.babel === "function" ? opts.babel(id, { ssr }) : opts.babel
          );
          runPluginOverrides?.(newBabelOptions, { id, ssr });
          return newBabelOptions;
        })();
        const plugins = [...babelOptions.plugins];
        const isJSX = filepath.endsWith("x");
        const useFastRefresh = !skipFastRefresh && !ssr && (isJSX || (opts.jsxRuntime === "classic" ? importReactRE.test(code) : code.includes(jsxImportDevRuntime) || code.includes(jsxImportRuntime)));
        if (useFastRefresh) {
          plugins.push([
            await loadPlugin("react-refresh/babel"),
            { skipEnvCheck: true }
          ]);
        }
        if (opts.jsxRuntime === "classic" && isJSX) {
          if (!isProduction) {
            plugins.push(
              await loadPlugin("@babel/plugin-transform-react-jsx-self"),
              await loadPlugin("@babel/plugin-transform-react-jsx-source")
            );
          }
        }
        if (canSkipBabel(plugins, babelOptions)) {
          return;
        }
        const parserPlugins = [...babelOptions.parserOpts.plugins];
        if (!filepath.endsWith(".ts")) {
          parserPlugins.push("jsx");
        }
        if (tsRE.test(filepath)) {
          parserPlugins.push("typescript");
        }
        const babel2 = await loadBabel();
        const result = await babel2.transformAsync(code, {
          ...babelOptions,
          root: projectRoot,
          filename: id,
          sourceFileName: filepath,
          // Required for esbuild.jsxDev to provide correct line numbers
          // This creates issues the react compiler because the re-order is too important
          // People should use @babel/plugin-transform-react-jsx-development to get back good line numbers
          retainLines: getReactCompilerPlugin(plugins) != null ? false : !isProduction && isJSX && opts.jsxRuntime !== "classic",
          parserOpts: {
            ...babelOptions.parserOpts,
            sourceType: "module",
            allowAwaitOutsideFunction: true,
            plugins: parserPlugins
          },
          generatorOpts: {
            ...babelOptions.generatorOpts,
            // import attributes parsing available without plugin since 7.26
            importAttributesKeyword: "with",
            decoratorsBeforeExport: true
          },
          plugins,
          sourceMaps: true
        });
        if (result) {
          if (!useFastRefresh) {
            return { code: result.code, map: result.map };
          }
          return addRefreshWrapper(
            result.code,
            result.map,
            "@vitejs/plugin-react",
            id,
            opts.reactRefreshHost
          );
        }
      }
    }
  };
  const dependencies = [
    "react",
    "react-dom",
    jsxImportDevRuntime,
    jsxImportRuntime
  ];
  const staticBabelPlugins = typeof opts.babel === "object" ? opts.babel?.plugins ?? [] : [];
  const reactCompilerPlugin = getReactCompilerPlugin(staticBabelPlugins);
  if (reactCompilerPlugin != null) {
    const reactCompilerRuntimeModule = getReactCompilerRuntimeModule(reactCompilerPlugin);
    dependencies.push(reactCompilerRuntimeModule);
  }
  const viteReactRefresh = {
    name: "vite:react-refresh",
    enforce: "pre",
    config: (userConfig) => ({
      build: silenceUseClientWarning(userConfig),
      optimizeDeps: {
        include: dependencies
      },
      resolve: {
        dedupe: ["react", "react-dom"]
      }
    }),
    resolveId: {
      filter: { id: pluginutils.exactRegex(runtimePublicPath) },
      handler(id) {
        if (id === runtimePublicPath) {
          return id;
        }
      }
    },
    load: {
      filter: { id: pluginutils.exactRegex(runtimePublicPath) },
      handler(id) {
        if (id === runtimePublicPath) {
          return node_fs.readFileSync(refreshRuntimePath, "utf-8").replace(
            /__README_URL__/g,
            "https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react"
          );
        }
      }
    },
    transformIndexHtml(_, config) {
      if (!skipFastRefresh)
        return [
          {
            tag: "script",
            attrs: { type: "module" },
            children: getPreambleCode(config.server.config.base)
          }
        ];
    }
  };
  return [viteBabel, viteReactRefresh];
}
viteReact.preambleCode = preambleCode;
function canSkipBabel(plugins, babelOptions) {
  return !(plugins.length || babelOptions.presets.length || babelOptions.configFile || babelOptions.babelrc);
}
const loadedPlugin = /* @__PURE__ */ new Map();
function loadPlugin(path) {
  const cached = loadedPlugin.get(path);
  if (cached) return cached;
  const promise = import(path).then((module) => {
    const value = module.default || module;
    loadedPlugin.set(path, value);
    return value;
  });
  loadedPlugin.set(path, promise);
  return promise;
}
function createBabelOptions(rawOptions) {
  const babelOptions = {
    babelrc: false,
    configFile: false,
    ...rawOptions
  };
  babelOptions.plugins ||= [];
  babelOptions.presets ||= [];
  babelOptions.overrides ||= [];
  babelOptions.parserOpts ||= {};
  babelOptions.parserOpts.plugins ||= [];
  return babelOptions;
}
function defined(value) {
  return value !== void 0;
}
function getReactCompilerPlugin(plugins) {
  return plugins.find(
    (p) => p === "babel-plugin-react-compiler" || Array.isArray(p) && p[0] === "babel-plugin-react-compiler"
  );
}
function getReactCompilerRuntimeModule(plugin) {
  let moduleName = "react/compiler-runtime";
  if (Array.isArray(plugin)) {
    if (plugin[1]?.target === "17" || plugin[1]?.target === "18") {
      moduleName = "react-compiler-runtime";
    } else if (typeof plugin[1]?.runtimeModule === "string") {
      moduleName = plugin[1]?.runtimeModule;
    }
  }
  return moduleName;
}
function ensureArray(value) {
  return Array.isArray(value) ? value : [value];
}

module.exports = viteReact;
module.exports.default = viteReact;
