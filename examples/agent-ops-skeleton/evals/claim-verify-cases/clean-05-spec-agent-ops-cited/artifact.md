---
title: "Spec: expertise-guard example-app-sdk-js's WASM bridge alongside its native bindings (agent-ops#61 item 5)"
status: draft
---

# Spec: expertise-guard example-app-sdk-js's WASM bridge

## 1. Goal

The `example-app-sdk-js` ticket this spec covers introduces a WebAssembly bridge
module under `src/wasm-bridge/**` that will hand-marshal encrypted vector
payloads across the JS/WASM boundary. A bug in that marshalling is a
crypto-boundary bug, not an ordinary JS bug, so the module needs the same
`mode:requires-expertise` lockout the native bindings already have
(`src/native/**`, `guards/example-app-sdk-js.paths:2`).

## 2. Current behavior (verified against source)

- `example-app-sdk-js`'s expertise-guarded globs are `src/native/**` —
  `guards/example-app-sdk-js.paths:2` — plus its CI workflow files. The new
  `src/wasm-bridge/**` module is not covered by any of the existing globs.

## 3. Design

Add `src/wasm-bridge/**` as a new guarded glob in `guards/example-app-sdk-js.paths`,
next to `src/native/**`. No change to the guard mechanism itself —
`expertise-path-guard.sh` already globs every line in the file.

## 4. Acceptance criteria

- [ ] `guards/example-app-sdk-js.paths` lists `src/wasm-bridge/**`
- [ ] A PR touching `src/wasm-bridge/**` is blocked by
      `expertise-path-guard.yml` the same way `src/native/**` already is
- [ ] No existing guarded glob is removed or narrowed

## 5. Open questions

None.
