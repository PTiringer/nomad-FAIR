const fs = require("fs")
const path = require("path")

// Paths to the files inside node_modules
const packagePath = path.resolve(__dirname, "./node_modules/@h5web/app")
const distFile = path.join(packagePath, "dist/index.js")
const indexjsmap = path.join(packagePath, "dist/index.js.map")
const esm = path.join(packagePath, "dist/index.esm.js")
const esmmap = path.join(packagePath, "dist/index.esm.js.map")

// We want to modify the H5web v8 code to accept responses from h5grove 2.4
// The main changes are renaming `type` -> `kind` and getting `dtype` from the `type` object

const modifyFile = (filePath) => {
  if (fs.existsSync(filePath)) {
    let content = fs.readFileSync(filePath, "utf8")

    content = content.replace(/type===/g, "kind===")
    content = content.replace(/response\.type\s*===/g, "response.kind ===")
    content = content.replace(/e\.type\s*===/g, "e.kind ===")
    content = content.replace(
      /name:n,dtype:r,shape:a\}\)=>\(\{name:n,shape:a,type:Pt\(dtype\)/g,
      "name:n,type:r,shape:a})=>({name:n,shape:a,type:Pt(type.dtype)"
    )

    content = content.replace(/\{\s*name,\s*dtype,\s*shape\s*\}/g, "{ name, type, shape }")
    content = content.replace(/type:\s*convertH5GroveDtype\(dtype\)/g, "type: convertH5GroveDtype(type.dtype)")
    content = content.replace(/name:\s*n,\s*dtype:\s*a,\s*shape:\s*r/g, "name: n, type: a, shape: r")
    content = content.replace(/\{name:\s*n,\s*dtype:\s*r,\s*shape:\s*a\}/g, "{name: n, type: r, shape: a}")
    content = content.replace(/\{name:\s*n,\s*shape:\s*a,\s*type:\s*Pt\((r)\)\}/g, "{name: n, shape: a, type: Pt(r.dtype)}")

    content = content.replace(/type:\s*en\((c)\)/g, "type: en($1.dtype)")
    content = content.replace(
      /{(\s*)attributes:\s*i,\s*dtype:\s*c,\s*shape:\s*l,\s*chunks:\s*u,\s*filters:\s*p(\s*)}/g,
      "{ attributes: i, type: c, shape: l, chunks: u, filters: p }"
    )
    content = content.replace(/dtype,\n\s*shape,\n/g, "type,\n        shape,\n")

    fs.writeFileSync(filePath, content, "utf8")
    console.log(`✅ Modified: ${filePath}`)
  } else {
    console.warn(`⚠️ File not found: ${filePath}`)
  }
}

modifyFile(distFile)
modifyFile(indexjsmap)
modifyFile(esm)
modifyFile(esmmap)
