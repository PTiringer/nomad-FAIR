/**
 * Function for generating a Plotly template based on the current theme. These
 * templates are based on plotly_dark and plotly_light templates as exported
 * from Plotly.js v2.35.3 using the attribute _fullLayout.template.
 *
 * @returns
 * template
 */
export function getPlotlyTemplate() {
  return require('./light.json')
}
