const CracoWorkboxPlugin = require('craco-workbox')

module.exports = {
  plugins: [{
    plugin: CracoWorkboxPlugin
  }],
  webpack: {
    configure: (webpackConfig, { env, paths }) => {
      webpackConfig.resolve.alias = {
        ...(webpackConfig.resolve.alias || {}),
        'fraction.js$': require.resolve('fraction.js')
      }

      const cjsRule = {
        test: /\.cjs$/,
        include: /node_modules/,
        type: 'javascript/auto'
      }
      const oneOfRule = webpackConfig.module.rules.find((rule) => Array.isArray(rule.oneOf))
      if (oneOfRule) {
        oneOfRule.oneOf.unshift(cjsRule)
      } else {
        webpackConfig.module.rules.push(cjsRule)
      }

      // Add a rule to handle .mjs files
      webpackConfig.module.rules.push({
        test: /\.mjs$/,
        include: /node_modules/,
        type: 'javascript/auto'
      })

      return webpackConfig
    }
  }
}
