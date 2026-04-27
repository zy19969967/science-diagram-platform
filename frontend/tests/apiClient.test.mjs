import assert from "node:assert/strict";

import {
  apiPath,
  buildApiHeaders,
  normalizeApiBaseUrl,
} from "../src/apiClient.js";

assert.equal(normalizeApiBaseUrl("http://localhost:19080/"), "http://localhost:19080");
assert.equal(normalizeApiBaseUrl(""), "");
assert.equal(apiPath("/api/health", "http://localhost:19080/"), "http://localhost:19080/api/health");
assert.equal(apiPath("/api/health", ""), "/api/health");

const authHeaders = buildApiHeaders({
  token: "secret-token",
  headers: { "Content-Type": "application/json" },
});
assert.equal(authHeaders["Content-Type"], "application/json");
assert.equal(authHeaders.Authorization, "Bearer secret-token");

const existingAuth = buildApiHeaders({
  token: "secret-token",
  headers: { Authorization: "Bearer caller-token" },
});
assert.equal(existingAuth.Authorization, "Bearer caller-token");

const noTokenHeaders = buildApiHeaders({
  token: "",
  headers: { Accept: "application/json" },
});
assert.deepEqual(noTokenHeaders, { Accept: "application/json" });
