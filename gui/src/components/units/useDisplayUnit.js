import {useErrors} from "../errors"
import {useMemo} from "react"
import {Unit} from "./Unit"
import {useUnitContext} from "./UnitContext"
import {getFieldProps} from "../editQuantity/StringEditQuantity"
import { DType, getDatatype } from "../../utils"

/**
 * Used to retrieve the unit to use for displaying a quantity. Primarily uses the display
 * unit annotations, defaults to returning a display unit according to the currently set
 * unit system. If the quantity is not of a numeric type, returns undefined.
 *
 * @param {*} quantityDef Definition for the quantity
 * @param {*} returnExplicit Whether to return an object containing the display unit and a
 * boolean indicating whether this display unit was explicitly set
 * @returns {Unit} The unit to use for displaying the quantity.
 */
export function useDisplayUnit(quantityDef, returnExplicit = false) {
  const {units} = useUnitContext()
  const {raiseError} = useErrors()
  const {defaultDisplayUnit: deprecatedDefaultDisplayUnit} = getFieldProps(quantityDef)
  const defaultDisplayUnit = quantityDef?.m_annotations?.display?.[0]?.unit || deprecatedDefaultDisplayUnit

  // Get the storage unit if present
  const defaultUnit = useMemo(() => {
    const dtype = getDatatype(quantityDef)
    return (dtype === DType.Int || dtype === DType.Float)
      ? new Unit(quantityDef.unit || 'dimensionless')
      : undefined
  }, [quantityDef])

  // Get the display unit. Primarily uses the display unit annotation, but falls back to
  // the global unit system if not present.
  const displayUnitObj = useMemo(() => {
    if (!defaultUnit) return undefined
    let defaultDisplayUnitObj
    if (defaultDisplayUnit) {
      try {
        defaultDisplayUnitObj = new Unit(defaultDisplayUnit)
      } catch (e) {
        raiseError(`The provided defaultDisplayUnit for ${quantityDef.name} field is not valid.`)
      }
      if (defaultDisplayUnitObj.dimension(true) !== defaultUnit.dimension(true)) {
        raiseError(`The provided defaultDisplayUnit for ${quantityDef.name} has incorrect dimensionality for this field.`)
      }
    } else {
      defaultDisplayUnitObj = new Unit(defaultUnit).toSystem(units)
    }

    return defaultDisplayUnitObj
  }, [defaultDisplayUnit, defaultUnit, quantityDef, raiseError, units])

  if (returnExplicit) return {displayUnit: displayUnitObj, explicit: !!defaultDisplayUnit}
  return displayUnitObj
}
