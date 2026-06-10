const fs = require("fs");
const path = require("path");
const vm = require("vm");

const projectRoot = path.resolve(__dirname, "..");
const dataJsPath = path.join(projectRoot, "static", "js", "data.js");
const outputDir = path.join(projectRoot, "static", "data");
const outputPath = path.join(outputDir, "seed_data.json");

if (!fs.existsSync(dataJsPath)) {
  console.error(`Could not find data.js at: ${dataJsPath}`);
  process.exit(1);
}

const dataJs = fs.readFileSync(dataJsPath, "utf8");

const sandbox = {
  window: {},
  console,
};

vm.createContext(sandbox);
vm.runInContext(dataJs, sandbox, {
  filename: "data.js",
});

if (!sandbox.window.AOM_DATA) {
  console.error("window.AOM_DATA was not found after running data.js.");
  process.exit(1);
}

fs.mkdirSync(outputDir, { recursive: true });

fs.writeFileSync(
  outputPath,
  JSON.stringify(sandbox.window.AOM_DATA, null, 2),
  "utf8"
);

console.log(`Exported seed data to: ${outputPath}`);