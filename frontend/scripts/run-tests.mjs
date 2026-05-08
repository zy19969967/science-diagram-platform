import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const testDir = fileURLToPath(new URL("../tests/", import.meta.url));
const testFiles = readdirSync(testDir)
  .filter((name) => name.endsWith(".mjs"))
  .sort();

for (const file of testFiles) {
  console.log(`== ${file} ==`);
  const result = spawnSync(process.execPath, [join(testDir, file)], {
    stdio: "inherit",
    shell: false,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

console.log(`Ran ${testFiles.length} frontend test files.`);
