import {useErrors} from "../errors"
import {useMemo} from "react"
import {Unit} from "./Unit"
import {useUnitContext} from "./UnitContext"
import {getFieldProps} from "../editQuantity/StringEditQuantity"

/**
 * Used to retrieve the unit to use for displaying a quantity. Primarily uses the display
 * unit annotations, defaults to returning a display unit according to the currently set
 * unit system.
 *
 * @param {*} quantityDef Definition for the quantity
 * @param {*} returnExplicit Whether to return an object containing the display unit and a
 * boolean indicating whether this display unit was explicitly set
 * @returns {Unit} The unit to use for displaying the quantity.
 */
export function useDisplayUnit(quantityDef, returnExplicit = false) {
  const {units} = useUnitContext()
  const {raiseError} = useErrors()
  const defaultUnit = useMemo(() => new Unit(quantityDef.unit || 'dimensionless'), [quantityDef])
  const {defaultDisplayUnit: deprecatedDefaultDisplayUnit} = getFieldProps(quantityDef)
  const defaultDisplayUnit = quantityDef?.m_annotations?.display?.[0]?.unit || deprecatedDefaultDisplayUnit

  const displayUnitObj = useMemo(() => {
    let defaultDisplayUnitObj

    // If a default display unit has been defined, use it instead
    if (defaultDisplayUnit) {
      try {
        defaultDisplayUnitObj = new Unit(defaultDisplayUnit)
      } catch (e) {
        raiseError(`The provided defaultDisplayUnit for ${quantityDef.name} field is not valid.`)
      }
      if (defaultDisplayUnitObj.dimension(true) !== defaultUnit.dimension(true)) {
        raiseError(`The provided defaultDisplayUnit for ${quantityDef.name} has incorrect dimensionality for this field.`)
      }
    // Use the global unit system defined in the schema
    } else {
      defaultDisplayUnitObj = new Unit(defaultUnit).toSystem(units)
    }

    return defaultDisplayUnitObj
  }, [defaultDisplayUnit, defaultUnit, quantityDef, raiseError, units])

  if (returnExplicit) return {displayUnit: displayUnitObj, explicit: !!defaultDisplayUnit}
  return displayUnitObj
}
