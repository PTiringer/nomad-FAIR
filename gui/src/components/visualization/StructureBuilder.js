/*
 * Copyright The NOMAD Authors.
 *
 * This file is part of NOMAD. See https://nomad-lab.eu for further info.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * This class is used for building the required NGL stores (atomStore,
 * residueStore, chainStore, modelStore) for a Structure. The blueprint for this
 * class comes from the NGL package (ngl/src/structure/structure-builder.ts)
 * which is not not exported from the minified package.
 */
class StructureBuilder {
  constructor(structure) {
    this.currentModelindex = null
    this.currentChainid = null
    this.currentResname = null
    this.currentResno = null
    this.currentInscode = undefined
    this.currentHetero = null

    this.previousResname = ''
    this.previousHetero = null

    this.ai = -1
    this.ri = -1
    this.ci = -1
    this.mi = -1
    this.structure = structure
  }

  addResidueType(ri) {
    const atomStore = this.structure.atomStore
    const residueStore = this.structure.residueStore
    const residueMap = this.structure.residueMap
    const cc = this.structure.chemCompMap?.dict[this.previousResname]

    const count = residueStore.atomCount[ri]
    const offset = residueStore.atomOffset[ri]
    const atomTypeIdList = new Array(count)
    for (let i = 0; i < count; ++i) {
      atomTypeIdList[i] = atomStore.atomTypeId[offset + i]
    }
    const chemCompType = cc?.chemCompType
    const bonds = cc ? this.structure.chemCompMap?.getBonds(this.previousResname, atomTypeIdList) : undefined
    residueStore.residueTypeId[ri] = residueMap.add(
      this.previousResname, atomTypeIdList, this.previousHetero, chemCompType, bonds
    )
  }

  addAtom(modelindex, chainname, chainid, resname, resno, hetero, sstruc, inscode) {
    const atomStore = this.structure.atomStore
    const residueStore = this.structure.residueStore
    const chainStore = this.structure.chainStore
    const modelStore = this.structure.modelStore

    let addModel = false
    let addChain = false
    let addResidue = false

    if (this.currentModelindex !== modelindex) {
      addModel = true
      addChain = true
      addResidue = true
      this.mi += 1
      this.ci += 1
      this.ri += 1
    } else if (this.currentChainid !== chainid) {
      addChain = true
      addResidue = true
      this.ci += 1
      this.ri += 1
    } else if (this.currentResno !== resno || this.currentResname !== resname || this.currentInscode !== inscode) {
      addResidue = true
      this.ri += 1
    }
    this.ai += 1

    if (addModel) {
      modelStore.growIfFull()
      modelStore.chainOffset[this.mi] = this.ci
      modelStore.chainCount[this.mi] = 0
      modelStore.count += 1
      chainStore.modelIndex[this.ci] = this.mi
    }

    if (addChain) {
      chainStore.growIfFull()
      chainStore.setChainname(this.ci, chainname)
      chainStore.setChainid(this.ci, chainid)
      chainStore.residueOffset[this.ci] = this.ri
      chainStore.residueCount[this.ci] = 0
      chainStore.count += 1
      chainStore.modelIndex[this.ci] = this.mi
      modelStore.chainCount[this.mi] += 1
      residueStore.chainIndex[this.ri] = this.ci
    }

    if (addResidue) {
      this.previousResname = this.currentResname
      this.previousHetero = this.currentHetero
      if (this.ri > 0) this.addResidueType(this.ri - 1)
      residueStore.growIfFull()
      residueStore.resno[this.ri] = resno
      if (sstruc !== undefined) {
        residueStore.sstruc[this.ri] = sstruc.charCodeAt(0)
      }
      if (inscode !== undefined) {
        residueStore.inscode[this.ri] = inscode.charCodeAt(0)
      }
      residueStore.atomOffset[this.ri] = this.ai
      residueStore.atomCount[this.ri] = 0
      residueStore.count += 1
      residueStore.chainIndex[this.ri] = this.ci
      chainStore.residueCount[this.ci] += 1
    }

    atomStore.count += 1
    atomStore.residueIndex[this.ai] = this.ri
    residueStore.atomCount[this.ri] += 1

    this.currentModelindex = modelindex
    this.currentChainid = chainid
    this.currentResname = resname
    this.currentResno = resno
    this.currentInscode = inscode
    this.currentHetero = hetero
  }

  finalize() {
    this.previousResname = this.currentResname
    this.previousHetero = this.currentHetero
    if (this.ri > -1) this.addResidueType(this.ri)
  }
}

export default StructureBuilder
