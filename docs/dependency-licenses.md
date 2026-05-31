# Third-Party Dependency Licenses

This document inventories the licenses of every third-party dependency resolved
by Spelix, to confirm there are no conflicts with distributing this repository
under the [Business Source License 1.1](../LICENSE) (which converts to Apache
License 2.0 on the Change Date).

**Generated:** 2026-05-30

**Important scoping note.** This repository does **not** vendor third-party
dependency source. It ships dependency *manifests and lockfiles*
(`backend/pyproject.toml` + `uv.lock`, `frontend/package.json` +
`package-lock.json`); the actual packages are fetched at install time and each
retains its own upstream license. The BSL applies to Spelix's first-party
source only. This inventory is therefore a due-diligence record, not a
redistribution-of-bundled-code statement.

**Method:**
- **Backend (Python):** enumerated via `importlib.metadata` over the resolved
  `uv` environment (runtime + dev/test dependencies); license taken from each
  distribution's `License-Expression` / `License` / `License ::` classifier
  metadata. Regenerate: `uv run python backend/_gen_licenses.py` (script not
  committed — see git history).
- **Frontend (npm):** walked `node_modules` (including scoped packages) and read
  each package's `package.json` `license` field.
- Spelix's own first-party packages are excluded.

## Compatibility summary

The dependency trees are **overwhelmingly permissive** (MIT, BSD 0-/2-/3-Clause,
Apache-2.0, ISC, PSF, CC0, BlueOak-1.0.0, MIT-0). Backend: 245 distributions.
Frontend: 350 packages.

**No strong copyleft (GPL / AGPL) infects Spelix.** The non-permissive entries
below are all either weak/file-level copyleft used as *unmodified, separately
installed* libraries, or packages whose PyPI/npm metadata is non-standard but
whose upstream license is permissive. All are compatible with distributing
Spelix under BSL-1.1 → Apache-2.0.

### Weak / file-level copyleft (all compatible — unmodified, not vendored)

| Package | Tree | Declared license | Why it's fine |
| --- | --- | --- | --- |
| psycopg | backend | LGPL-3.0-only | LGPL is weak copyleft; used as an unmodified, pip-installed library (dynamic import, not statically vendored). No obligation to relicense Spelix. |
| psycopg-pool | backend | LGPL-3.0-only | Same as `psycopg`. |
| crontab (parse-crontab) | backend | LGPL (v2/v3) | Weak copyleft, unmodified library import. |
| pyphen | backend | GPLv2+ / LGPLv2+ / MPL-1.1 (tri-license) | Tri-licensed — the LGPL or MPL option is elected, so the GPL arm does not apply. WeasyPrint hyphenation dependency, unmodified. |
| certifi | backend | MPL-2.0 | File-level copyleft; CA bundle used unmodified — no source-disclosure trigger. |
| orjson | backend | MPL-2.0 AND (Apache-2.0 OR MIT) | File-level copyleft, unmodified. |
| tqdm | backend | MPL-2.0 AND MIT | File-level copyleft, unmodified. |
| lightningcss (+ win32 binary) | frontend | MPL-2.0 | Build-time CSS tool (Tailwind v4); file-level copyleft, unmodified. |
| dompurify | frontend | MPL-2.0 OR Apache-2.0 | Dual-licensed — Apache-2.0 option elected. |

### Non-standard metadata (upstream license is permissive)

| Package | Tree | Metadata says | Actual upstream license |
| --- | --- | --- | --- |
| namex | backend | UNKNOWN | Apache-2.0 (Keras namespace helper) |
| rtmlib | backend | UNKNOWN | Apache-2.0 |
| combine-errors | frontend | UNKNOWN | MIT |
| posthog-js | frontend | SEE LICENSE IN LICENSE | MIT |

---

## Backend (Python) — 245 distributions

| Package | Version | License |
| --- | --- | --- |
| protobuf | 6.33.6 | 3-Clause BSD License |
| transformers | 5.8.0 | Apache 2.0 License |
| keras | 3.14.1 | Apache License 2.0 |
| multidict | 6.7.1 | Apache License 2.0 |
| accelerate | 1.13.0 | Apache Software License |
| aiosignal | 1.4.0 | Apache Software License |
| deprecation | 2.1.0 | Apache Software License |
| distro | 1.9.0 | Apache Software License |
| flatbuffers | 25.12.19 | Apache Software License |
| google-pasta | 0.2.0 | Apache Software License |
| googleapis-common-protos | 1.74.0 | Apache Software License |
| huggingface_hub | 1.10.1 | Apache Software License |
| libclang | 18.1.1 | Apache Software License |
| mediapipe | 0.10.33 | Apache Software License |
| openai | 2.30.0 | Apache Software License |
| opencv-contrib-python | 4.13.0.92 | Apache Software License |
| opencv-python | 4.13.0.92 | Apache Software License |
| opencv-python-headless | 4.13.0.92 | Apache Software License |
| propcache | 0.4.1 | Apache Software License |
| qdrant-client | 1.17.1 | Apache Software License |
| requests | 2.33.1 | Apache Software License |
| requests-toolbelt | 1.0.0 | Apache Software License |
| rsa | 4.9.1 | Apache Software License |
| safetensors | 0.7.0 | Apache Software License |
| tenacity | 9.1.4 | Apache Software License |
| tensorflow | 2.21.0 | Apache Software License |
| tensorflow-hub | 0.16.1 | Apache Software License |
| tf_keras | 2.21.0 | Apache Software License |
| tokenizers | 0.22.2 | Apache Software License |
| zopfli | 0.4.1 | Apache Software License |
| packaging | 24.2 | Apache Software License | BSD License |
| absl-py | 2.4.0 | Apache-2.0 |
| asyncpg | 0.31.0 | Apache-2.0 |
| coverage | 7.13.5 | Apache-2.0 |
| frozenlist | 1.8.0 | Apache-2.0 |
| grpcio | 1.80.0 | Apache-2.0 |
| hf-xet | 1.4.3 | Apache-2.0 |
| importlib_metadata | 8.7.1 | Apache-2.0 |
| ml_dtypes | 0.5.4 | Apache-2.0 |
| opentelemetry-api | 1.41.0 | Apache-2.0 |
| opentelemetry-exporter-otlp-proto-common | 1.41.0 | Apache-2.0 |
| opentelemetry-exporter-otlp-proto-http | 1.41.0 | Apache-2.0 |
| opentelemetry-proto | 1.41.0 | Apache-2.0 |
| opentelemetry-sdk | 1.41.0 | Apache-2.0 |
| opentelemetry-semantic-conventions | 0.62b0 | Apache-2.0 |
| optree | 0.19.1 | Apache-2.0 |
| pyiceberg | 0.11.1 | Apache-2.0 |
| pytest-asyncio | 1.3.0 | Apache-2.0 |
| python-multipart | 0.0.24 | Apache-2.0 |
| rapidocr | 3.8.1 | Apache-2.0 |
| types-requests | 2.33.0.20260408 | Apache-2.0 |
| tzdata | 2026.2 | Apache-2.0 |
| yarl | 1.23.0 | Apache-2.0 |
| regex | 2026.5.9 | Apache-2.0 AND CNRI-Python |
| aiohttp | 3.13.5 | Apache-2.0 AND MIT |
| cryptography | 46.0.7 | Apache-2.0 OR BSD-3-Clause |
| ormsgpack | 1.12.2 | Apache-2.0 OR MIT |
| antlr4-python3-runtime | 4.9.3 | BSD |
| torchvision | 0.26.0 | BSD |
| astunparse | 1.6.3 | BSD License |
| colorama | 0.4.6 | BSD License |
| contourpy | 1.3.3 | BSD License |
| cssselect2 | 0.9.0 | BSD License |
| cycler | 0.12.1 | BSD License |
| dill | 0.4.1 | BSD License |
| gast | 0.7.0 | BSD License |
| httpx | 0.28.1 | BSD License |
| Jinja2 | 3.1.6 | BSD License |
| jsonlines | 4.0.0 | BSD License |
| jsonpatch | 1.33 | BSD License |
| jsonpointer | 3.1.1 | BSD License |
| kiwisolver | 1.5.0 | BSD License |
| mpmath | 1.3.0 | BSD License |
| multiprocess | 0.70.19 | BSD License |
| nodeenv | 1.10.0 | BSD License |
| omegaconf | 2.3.0 | BSD License |
| pandas | 3.0.3 | BSD License |
| pydyf | 0.12.1 | BSD License |
| scipy | 1.17.1 | BSD License |
| sentry-sdk | 2.57.0 | BSD License |
| shapely | 2.1.2 | BSD License |
| sympy | 1.14.0 | BSD License |
| tinycss2 | 1.5.1 | BSD License |
| weasyprint | 68.1 | BSD License |
| webencodings | 0.5.1 | BSD License |
| websockets | 15.0.1 | BSD License |
| wrapt | 1.17.3 | BSD License |
| xlsxwriter | 3.2.9 | BSD License |
| python-dateutil | 2.9.0.post0 | BSD License | Apache Software License |
| pyasn1 | 0.6.3 | BSD-2-Clause |
| Pygments | 2.20.0 | BSD-2-Clause |
| click | 8.3.2 | BSD-3-Clause |
| fsspec | 2026.3.0 | BSD-3-Clause |
| h5py | 3.14.0 | BSD-3-Clause |
| httpcore | 1.0.9 | BSD-3-Clause |
| idna | 3.11 | BSD-3-Clause |
| lxml | 6.1.0 | BSD-3-Clause |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| networkx | 3.6.1 | BSD-3-Clause |
| portalocker | 3.2.0 | BSD-3-Clause |
| psutil | 7.2.2 | BSD-3-Clause |
| pycparser | 3.0 | BSD-3-Clause |
| python-dotenv | 1.2.2 | BSD-3-Clause |
| starlette | 1.0.0 | BSD-3-Clause |
| torch | 2.11.0 | BSD-3-Clause |
| uvicorn | 0.44.0 | BSD-3-Clause |
| zstandard | 0.25.0 | BSD-3-Clause |
| numpy | 2.4.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| pypdfium2 | 5.8.0 | BSD-3-Clause, Apache-2.0, dependency licenses |
| pyphen | 0.17.2 | GNU General Public License v2 or later (GPLv2+) | GNU Lesser General Public License v2 or later (LGPLv2+) | Mozilla Public License 1.1 (MPL 1.1) |
| crontab | 1.0.5 | GNU Library or Lesser General Public License (LGPL) | GNU Lesser General Public License v2 (LGPLv2) | GNU Lesser General Public License v3 (LGPLv3) |
| dnspython | 2.8.0 | ISC License (ISCL) |
| shellingham | 1.5.4 | ISC License (ISCL) |
| psycopg | 3.3.4 | LGPL-3.0-only |
| psycopg-pool | 3.3.1 | LGPL-3.0-only |
| alembic | 1.18.4 | MIT |
| annotated-doc | 0.0.4 | MIT |
| anyio | 4.13.0 | MIT |
| attrs | 26.1.0 | MIT |
| brotli | 1.2.0 | MIT |
| cachetools | 6.2.6 | MIT |
| cffi | 2.0.0 | MIT |
| charset-normalizer | 3.4.7 | MIT |
| coredis | 6.6.1 | MIT |
| docling | 2.93.0 | MIT |
| docling-core | 2.74.1 | MIT |
| docling-ibm-models | 3.13.2 | MIT |
| docling-parse | 5.11.0 | MIT |
| docling-slim | 2.93.0 | MIT |
| ecdsa | 0.19.2 | MIT |
| fastapi | 0.135.3 | MIT |
| fastavro | 1.12.1 | MIT |
| filelock | 3.25.2 | MIT |
| fonttools | 4.62.1 | MIT |
| httptools | 0.7.1 | MIT |
| iniconfig | 2.3.0 | MIT |
| instructor | 1.15.1 | MIT |
| jsonref | 1.1.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| langchain-core | 0.3.63 | MIT |
| langfuse | 4.2.0 | MIT |
| langgraph-checkpoint | 2.1.2 | MIT |
| langgraph-checkpoint-postgres | 2.0.25 | MIT |
| langgraph-sdk | 0.1.74 | MIT |
| latex2mathml | 3.81.0 | MIT |
| limits | 5.8.0 | MIT |
| marko | 2.2.2 | MIT |
| opt_einsum | 3.4.0 | MIT |
| postgrest | 2.28.3 | MIT |
| pydantic | 2.12.5 | MIT |
| pydantic-settings | 2.14.1 | MIT |
| pydantic_core | 2.41.5 | MIT |
| PyJWT | 2.12.1 | MIT |
| pyparsing | 3.3.2 | MIT |
| pyright | 1.1.408 | MIT |
| pytest | 9.0.3 | MIT |
| pytest-cov | 7.1.0 | MIT |
| realtime | 2.28.3 | MIT |
| referencing | 0.37.0 | MIT |
| rpds-py | 0.30.0 | MIT |
| rtree | 1.4.1 | MIT |
| ruff | 0.15.9 | MIT |
| setuptools | 81.0.0 | MIT |
| sounddevice | 0.5.5 | MIT |
| soupsieve | 2.8.3 | MIT |
| SQLAlchemy | 2.0.49 | MIT |
| storage3 | 2.28.3 | MIT |
| supabase | 2.28.3 | MIT |
| supabase-auth | 2.28.3 | MIT |
| supabase-functions | 2.28.3 | MIT |
| tabulate | 0.10.0 | MIT |
| termcolor | 3.3.0 | MIT |
| tree-sitter-javascript | 0.25.0 | MIT |
| tree-sitter-python | 0.25.0 | MIT |
| typer | 0.21.2 | MIT |
| typing-inspection | 0.4.2 | MIT |
| urllib3 | 2.6.3 | MIT |
| wheel | 0.47.0 | MIT |
| zipp | 3.23.0 | MIT |
| greenlet | 3.3.2 | MIT AND PSF-2.0 |
| annotated-types | 0.7.0 | MIT License |
| anthropic | 0.91.0 | MIT License |
| backoff | 2.2.1 | MIT License |
| beartype | 0.22.9 | MIT License |
| beautifulsoup4 | 4.14.3 | MIT License |
| cohere | 6.1.0 | MIT License |
| colorlog | 6.10.1 | MIT License |
| Deprecated | 1.3.1 | MIT License |
| docstring_parser | 0.17.0 | MIT License |
| et_xmlfile | 2.0.0 | MIT License |
| exceptiongroup | 1.3.1 | MIT License |
| Faker | 40.15.0 | MIT License |
| filetype | 1.2.0 | MIT License |
| h11 | 0.16.0 | MIT License |
| h2 | 4.3.0 | MIT License |
| hpack | 4.1.0 | MIT License |
| hyperframe | 6.1.0 | MIT License |
| jiter | 0.13.0 | MIT License |
| langchain-anthropic | 0.2.4 | MIT License |
| langgraph | 0.2.76 | MIT License |
| langsmith | 0.1.147 | MIT License |
| Mako | 1.3.10 | MIT License |
| markdown-it-py | 4.0.0 | MIT License |
| mdurl | 0.1.2 | MIT License |
| mmh3 | 5.2.1 | MIT License |
| mpire | 2.10.2 | MIT License |
| onnxruntime | 1.26.0 | MIT License |
| openpyxl | 3.1.5 | MIT License |
| pluggy | 1.6.0 | MIT License |
| polyfactory | 3.3.0 | MIT License |
| pylatexenc | 2.10 | MIT License |
| pyroaring | 1.0.4 | MIT License |
| python-docx | 1.2.0 | MIT License |
| python-jose | 3.5.0 | MIT License |
| python-pptx | 1.0.2 | MIT License |
| PyYAML | 6.0.3 | MIT License |
| redis | 5.3.1 | MIT License |
| rich | 14.3.3 | MIT License |
| semchunk | 3.2.5 | MIT License |
| six | 1.17.0 | MIT License |
| slowapi | 0.1.9 | MIT License |
| streaq | 6.4.0 | MIT License |
| StrEnum | 0.4.15 | MIT License |
| strictyaml | 1.7.3 | MIT License |
| tinyhtml5 | 2.1.0 | MIT License |
| tree-sitter | 0.25.2 | MIT License |
| tree-sitter-c | 0.24.2 | MIT License |
| tree-sitter-typescript | 0.23.2 | MIT License |
| watchfiles | 1.1.1 | MIT License |
| sniffio | 1.3.1 | MIT License | Apache Software License |
| pillow | 12.2.0 | MIT-CMU |
| certifi | 2026.2.25 | Mozilla Public License 2.0 (MPL 2.0) |
| orjson | 3.11.8 | MPL-2.0 AND (Apache-2.0 OR MIT) |
| tqdm | 4.67.3 | MPL-2.0 AND MIT |
| pyclipper | 1.4.0 | OSI Approved | MIT License |
| typing_extensions | 4.15.0 | PSF-2.0 |
| aiohappyeyeballs | 2.6.1 | Python Software Foundation License |
| defusedxml | 0.7.1 | Python Software Foundation License |
| matplotlib | 3.10.8 | Python Software Foundation License |
| pywin32 | 311 | Python Software Foundation License |
| email-validator | 2.3.0 | The Unlicense (Unlicense) |
| namex | 0.1.0 | UNKNOWN |
| rtmlib | 0.0.15 | UNKNOWN |
| yt-dlp | 2026.3.17 | Unlicense |

---

## Frontend (npm) - 350 packages

| Package | Version | License |
| --- | --- | --- |
| dompurify | 3.4.0 | (MPL-2.0 OR Apache-2.0) |
| tslib | 2.8.1 | 0BSD |
| @opentelemetry/api | 1.9.1 | Apache-2.0 |
| @opentelemetry/api-logs | 0.208.0 | Apache-2.0 |
| @opentelemetry/core | 2.2.0 | Apache-2.0 |
| @opentelemetry/exporter-logs-otlp-http | 0.208.0 | Apache-2.0 |
| @opentelemetry/otlp-exporter-base | 0.208.0 | Apache-2.0 |
| @opentelemetry/otlp-transformer | 0.208.0 | Apache-2.0 |
| @opentelemetry/resources | 2.6.1 | Apache-2.0 |
| @opentelemetry/sdk-logs | 0.208.0 | Apache-2.0 |
| @opentelemetry/sdk-metrics | 2.2.0 | Apache-2.0 |
| @opentelemetry/sdk-trace-base | 2.2.0 | Apache-2.0 |
| @opentelemetry/semantic-conventions | 1.40.0 | Apache-2.0 |
| aria-query | 5.3.0 | Apache-2.0 |
| detect-libc | 2.1.2 | Apache-2.0 |
| expect-type | 1.3.0 | Apache-2.0 |
| long | 5.3.2 | Apache-2.0 |
| typescript | 6.0.2 | Apache-2.0 |
| web-vitals | 5.2.0 | Apache-2.0 |
| xml-name-validator | 5.0.0 | Apache-2.0 |
| lru-cache | 11.3.2 | BlueOak-1.0.0 |
| entities | 6.0.1 | BSD-2-Clause |
| webidl-conversions | 8.0.1 | BSD-2-Clause |
| @protobufjs/aspromise | 1.1.2 | BSD-3-Clause |
| @protobufjs/base64 | 1.1.2 | BSD-3-Clause |
| @protobufjs/codegen | 2.0.4 | BSD-3-Clause |
| @protobufjs/eventemitter | 1.1.0 | BSD-3-Clause |
| @protobufjs/fetch | 1.1.0 | BSD-3-Clause |
| @protobufjs/float | 1.0.2 | BSD-3-Clause |
| @protobufjs/inquire | 1.1.0 | BSD-3-Clause |
| @protobufjs/path | 1.1.2 | BSD-3-Clause |
| @protobufjs/pool | 1.1.0 | BSD-3-Clause |
| @protobufjs/utf8 | 1.1.0 | BSD-3-Clause |
| d3-ease | 3.0.1 | BSD-3-Clause |
| istanbul-lib-coverage | 3.2.2 | BSD-3-Clause |
| istanbul-lib-report | 3.0.1 | BSD-3-Clause |
| istanbul-reports | 3.2.0 | BSD-3-Clause |
| js-base64 | 3.7.8 | BSD-3-Clause |
| protobufjs | 7.5.4 | BSD-3-Clause |
| source-map-js | 1.2.1 | BSD-3-Clause |
| tough-cookie | 6.0.1 | BSD-3-Clause |
| mdn-data | 2.27.1 | CC0-1.0 |
| @ungap/structured-clone | 1.3.0 | ISC |
| custom-error-instance | 2.1.1 | ISC |
| d3-array | 3.2.4 | ISC |
| d3-color | 3.1.0 | ISC |
| d3-dispatch | 3.0.1 | ISC |
| d3-drag | 3.0.0 | ISC |
| d3-format | 3.1.2 | ISC |
| d3-interpolate | 3.0.1 | ISC |
| d3-path | 3.1.0 | ISC |
| d3-scale | 4.0.2 | ISC |
| d3-selection | 3.0.0 | ISC |
| d3-shape | 3.2.0 | ISC |
| d3-time | 3.1.0 | ISC |
| d3-time-format | 4.1.0 | ISC |
| d3-timer | 3.0.1 | ISC |
| d3-transition | 3.0.1 | ISC |
| d3-zoom | 3.0.0 | ISC |
| graceful-fs | 4.2.11 | ISC |
| internmap | 2.0.3 | ISC |
| picocolors | 1.1.1 | ISC |
| saxes | 6.0.0 | ISC |
| semver | 7.7.4 | ISC |
| siginfo | 2.0.0 | ISC |
| signal-exit | 3.0.7 | ISC |
| @adobe/css-tools | 4.4.4 | MIT |
| @asamuzakjp/css-color | 5.1.8 | MIT |
| @asamuzakjp/dom-selector | 7.0.8 | MIT |
| @asamuzakjp/nwsapi | 2.3.9 | MIT |
| @babel/code-frame | 7.29.0 | MIT |
| @babel/helper-string-parser | 7.27.1 | MIT |
| @babel/helper-validator-identifier | 7.28.5 | MIT |
| @babel/parser | 7.29.2 | MIT |
| @babel/runtime | 7.29.2 | MIT |
| @babel/types | 7.29.0 | MIT |
| @bcoe/v8-coverage | 1.0.2 | MIT |
| @bramus/specificity | 2.4.2 | MIT |
| @csstools/css-calc | 3.1.1 | MIT |
| @csstools/css-color-parser | 4.0.2 | MIT |
| @csstools/css-parser-algorithms | 4.0.0 | MIT |
| @csstools/css-tokenizer | 4.0.0 | MIT |
| @emnapi/core | 1.9.1 | MIT |
| @emnapi/runtime | 1.9.1 | MIT |
| @emnapi/wasi-threads | 1.2.0 | MIT |
| @exodus/bytes | 1.15.0 | MIT |
| @jridgewell/gen-mapping | 0.3.13 | MIT |
| @jridgewell/remapping | 2.3.5 | MIT |
| @jridgewell/resolve-uri | 3.1.2 | MIT |
| @jridgewell/sourcemap-codec | 1.5.5 | MIT |
| @jridgewell/trace-mapping | 0.3.31 | MIT |
| @napi-rs/wasm-runtime | 1.1.2 | MIT |
| @oxc-project/types | 0.123.0 | MIT |
| @posthog/core | 1.25.2 | MIT |
| @posthog/types | 1.369.0 | MIT |
| @reduxjs/toolkit | 2.11.2 | MIT |
| @rolldown/binding-win32-x64-msvc | 1.0.0-rc.13 | MIT |
| @rolldown/pluginutils | 1.0.0-rc.13 | MIT |
| @sentry-internal/browser-utils | 10.47.0 | MIT |
| @sentry-internal/feedback | 10.47.0 | MIT |
| @sentry-internal/replay | 10.47.0 | MIT |
| @sentry-internal/replay-canvas | 10.47.0 | MIT |
| @sentry/browser | 10.47.0 | MIT |
| @sentry/core | 10.47.0 | MIT |
| @sentry/react | 10.47.0 | MIT |
| @standard-schema/spec | 1.1.0 | MIT |
| @standard-schema/utils | 0.3.0 | MIT |
| @supabase/auth-js | 2.102.1 | MIT |
| @supabase/functions-js | 2.102.1 | MIT |
| @supabase/phoenix | 0.4.0 | MIT |
| @supabase/postgrest-js | 2.102.1 | MIT |
| @supabase/realtime-js | 2.102.1 | MIT |
| @supabase/storage-js | 2.102.1 | MIT |
| @supabase/supabase-js | 2.102.1 | MIT |
| @tailwindcss/node | 4.2.2 | MIT |
| @tailwindcss/oxide | 4.2.2 | MIT |
| @tailwindcss/oxide-win32-x64-msvc | 4.2.2 | MIT |
| @tailwindcss/vite | 4.2.2 | MIT |
| @testing-library/dom | 10.4.1 | MIT |
| @testing-library/jest-dom | 6.9.1 | MIT |
| @testing-library/react | 16.3.2 | MIT |
| @testing-library/user-event | 14.6.1 | MIT |
| @tybys/wasm-util | 0.10.1 | MIT |
| @types/aria-query | 5.0.4 | MIT |
| @types/chai | 5.2.3 | MIT |
| @types/d3-array | 3.2.2 | MIT |
| @types/d3-color | 3.1.3 | MIT |
| @types/d3-drag | 3.0.7 | MIT |
| @types/d3-ease | 3.0.2 | MIT |
| @types/d3-interpolate | 3.0.4 | MIT |
| @types/d3-path | 3.1.1 | MIT |
| @types/d3-scale | 4.0.9 | MIT |
| @types/d3-selection | 3.0.11 | MIT |
| @types/d3-shape | 3.1.8 | MIT |
| @types/d3-time | 3.0.4 | MIT |
| @types/d3-timer | 3.0.2 | MIT |
| @types/d3-transition | 3.0.9 | MIT |
| @types/d3-zoom | 3.0.8 | MIT |
| @types/debug | 4.1.13 | MIT |
| @types/deep-eql | 4.0.2 | MIT |
| @types/estree | 1.0.8 | MIT |
| @types/estree-jsx | 1.0.5 | MIT |
| @types/hast | 3.0.4 | MIT |
| @types/mdast | 4.0.4 | MIT |
| @types/ms | 2.1.0 | MIT |
| @types/node | 25.5.2 | MIT |
| @types/react | 19.2.14 | MIT |
| @types/react-dom | 19.2.3 | MIT |
| @types/trusted-types | 2.0.7 | MIT |
| @types/tus-js-client | 1.8.0 | MIT |
| @types/unist | 3.0.3 | MIT |
| @types/use-sync-external-store | 0.0.6 | MIT |
| @types/ws | 8.18.1 | MIT |
| @vitejs/plugin-react | 6.0.1 | MIT |
| @vitest/coverage-v8 | 4.1.3 | MIT |
| @vitest/expect | 4.1.3 | MIT |
| @vitest/mocker | 4.1.3 | MIT |
| @vitest/pretty-format | 4.1.3 | MIT |
| @vitest/runner | 4.1.3 | MIT |
| @vitest/snapshot | 4.1.3 | MIT |
| @vitest/spy | 4.1.3 | MIT |
| @vitest/utils | 4.1.3 | MIT |
| @xyflow/react | 12.10.2 | MIT |
| @xyflow/system | 0.0.76 | MIT |
| ansi-regex | 5.0.1 | MIT |
| ansi-styles | 5.2.0 | MIT |
| assertion-error | 2.0.1 | MIT |
| ast-v8-to-istanbul | 1.0.0 | MIT |
| bail | 2.0.2 | MIT |
| bidi-js | 1.0.3 | MIT |
| buffer-from | 1.1.2 | MIT |
| ccount | 2.0.1 | MIT |
| chai | 6.2.2 | MIT |
| character-entities | 2.0.2 | MIT |
| character-entities-html4 | 2.1.0 | MIT |
| character-entities-legacy | 3.0.0 | MIT |
| character-reference-invalid | 2.0.1 | MIT |
| classcat | 5.0.5 | MIT |
| clsx | 2.1.1 | MIT |
| comma-separated-tokens | 2.0.3 | MIT |
| convert-source-map | 2.0.0 | MIT |
| cookie | 1.1.1 | MIT |
| core-js | 3.49.0 | MIT |
| css-tree | 3.2.1 | MIT |
| css.escape | 1.5.1 | MIT |
| csstype | 3.2.3 | MIT |
| data-urls | 7.0.0 | MIT |
| debug | 4.4.3 | MIT |
| decimal.js | 10.6.0 | MIT |
| decimal.js-light | 2.5.1 | MIT |
| decode-named-character-reference | 1.3.0 | MIT |
| dequal | 2.0.3 | MIT |
| devlop | 1.1.0 | MIT |
| dom-accessibility-api | 0.5.16 | MIT |
| enhanced-resolve | 5.20.1 | MIT |
| es-module-lexer | 2.0.0 | MIT |
| es-toolkit | 1.45.1 | MIT |
| estree-util-is-identifier-name | 3.0.0 | MIT |
| estree-walker | 3.0.3 | MIT |
| eventemitter3 | 5.0.4 | MIT |
| extend | 3.0.2 | MIT |
| fdir | 6.5.0 | MIT |
| fflate | 0.4.8 | MIT |
| has-flag | 4.0.0 | MIT |
| hast-util-to-jsx-runtime | 2.3.6 | MIT |
| hast-util-whitespace | 3.0.0 | MIT |
| html-encoding-sniffer | 6.0.0 | MIT |
| html-escaper | 2.0.2 | MIT |
| html-url-attributes | 3.0.1 | MIT |
| iceberg-js | 0.8.1 | MIT |
| immer | 10.2.0 | MIT |
| indent-string | 4.0.0 | MIT |
| inline-style-parser | 0.2.7 | MIT |
| is-alphabetical | 2.0.1 | MIT |
| is-alphanumerical | 2.0.1 | MIT |
| is-decimal | 2.0.1 | MIT |
| is-hexadecimal | 2.0.1 | MIT |
| is-plain-obj | 4.1.0 | MIT |
| is-potential-custom-element-name | 1.0.1 | MIT |
| is-stream | 2.0.1 | MIT |
| jiti | 2.6.1 | MIT |
| js-tokens | 4.0.0 | MIT |
| jsdom | 29.0.2 | MIT |
| lodash._baseiteratee | 4.7.0 | MIT |
| lodash._basetostring | 4.12.0 | MIT |
| lodash._baseuniq | 4.6.0 | MIT |
| lodash._createset | 4.0.3 | MIT |
| lodash._root | 3.0.1 | MIT |
| lodash._stringtopath | 4.8.0 | MIT |
| lodash.throttle | 4.1.1 | MIT |
| lodash.uniqby | 4.5.0 | MIT |
| longest-streak | 3.1.0 | MIT |
| lz-string | 1.5.0 | MIT |
| magic-string | 0.30.21 | MIT |
| magicast | 0.5.2 | MIT |
| make-dir | 4.0.0 | MIT |
| mdast-util-from-markdown | 2.0.3 | MIT |
| mdast-util-mdx-expression | 2.0.1 | MIT |
| mdast-util-mdx-jsx | 3.2.0 | MIT |
| mdast-util-mdxjs-esm | 2.0.1 | MIT |
| mdast-util-phrasing | 4.1.0 | MIT |
| mdast-util-to-hast | 13.2.1 | MIT |
| mdast-util-to-markdown | 2.1.2 | MIT |
| mdast-util-to-string | 4.0.0 | MIT |
| micromark | 4.0.2 | MIT |
| micromark-core-commonmark | 2.0.3 | MIT |
| micromark-factory-destination | 2.0.1 | MIT |
| micromark-factory-label | 2.0.1 | MIT |
| micromark-factory-space | 2.0.1 | MIT |
| micromark-factory-title | 2.0.1 | MIT |
| micromark-factory-whitespace | 2.0.1 | MIT |
| micromark-util-character | 2.1.1 | MIT |
| micromark-util-chunked | 2.0.1 | MIT |
| micromark-util-classify-character | 2.0.1 | MIT |
| micromark-util-combine-extensions | 2.0.1 | MIT |
| micromark-util-decode-numeric-character-reference | 2.0.2 | MIT |
| micromark-util-decode-string | 2.0.1 | MIT |
| micromark-util-encode | 2.0.1 | MIT |
| micromark-util-html-tag-name | 2.0.1 | MIT |
| micromark-util-normalize-identifier | 2.0.1 | MIT |
| micromark-util-resolve-all | 2.0.1 | MIT |
| micromark-util-sanitize-uri | 2.0.1 | MIT |
| micromark-util-subtokenize | 2.1.0 | MIT |
| micromark-util-symbol | 2.0.1 | MIT |
| micromark-util-types | 2.0.2 | MIT |
| min-indent | 1.0.1 | MIT |
| ms | 2.1.3 | MIT |
| nanoid | 3.3.11 | MIT |
| obug | 2.1.1 | MIT |
| parse-entities | 4.0.2 | MIT |
| parse5 | 8.0.0 | MIT |
| pathe | 2.0.3 | MIT |
| picomatch | 4.0.4 | MIT |
| postcss | 8.5.9 | MIT |
| preact | 10.29.1 | MIT |
| pretty-format | 27.5.1 | MIT |
| proper-lockfile | 4.1.2 | MIT |
| property-information | 7.1.0 | MIT |
| punycode | 2.3.1 | MIT |
| query-selector-shadow-dom | 1.0.1 | MIT |
| querystringify | 2.2.0 | MIT |
| react | 19.2.4 | MIT |
| react-dom | 19.2.4 | MIT |
| react-is | 17.0.2 | MIT |
| react-markdown | 9.1.0 | MIT |
| react-redux | 9.2.0 | MIT |
| react-router | 7.14.0 | MIT |
| recharts | 3.8.1 | MIT |
| redent | 3.0.0 | MIT |
| redux | 5.0.1 | MIT |
| redux-thunk | 3.1.0 | MIT |
| remark-parse | 11.0.0 | MIT |
| remark-rehype | 11.1.2 | MIT |
| require-from-string | 2.0.2 | MIT |
| requires-port | 1.0.0 | MIT |
| reselect | 5.1.1 | MIT |
| retry | 0.12.0 | MIT |
| rolldown | 1.0.0-rc.13 | MIT |
| scheduler | 0.27.0 | MIT |
| set-cookie-parser | 2.7.2 | MIT |
| space-separated-tokens | 2.0.2 | MIT |
| stackback | 0.0.2 | MIT |
| std-env | 4.0.0 | MIT |
| stringify-entities | 4.0.4 | MIT |
| strip-indent | 3.0.0 | MIT |
| style-to-js | 1.1.21 | MIT |
| style-to-object | 1.0.14 | MIT |
| symbol-tree | 3.2.4 | MIT |
| tailwindcss | 4.2.2 | MIT |
| tapable | 2.3.2 | MIT |
| tiny-invariant | 1.3.3 | MIT |
| tinybench | 2.9.0 | MIT |
| tinyexec | 1.1.1 | MIT |
| tinyglobby | 0.2.16 | MIT |
| tinyrainbow | 3.1.0 | MIT |
| tldts | 7.0.28 | MIT |
| tldts-core | 7.0.28 | MIT |
| tr46 | 6.0.0 | MIT |
| trim-lines | 3.0.1 | MIT |
| trough | 2.2.0 | MIT |
| tus-js-client | 4.3.1 | MIT |
| undici | 7.24.7 | MIT |
| undici-types | 7.18.2 | MIT |
| unified | 11.0.5 | MIT |
| unist-util-is | 6.0.1 | MIT |
| unist-util-position | 5.0.0 | MIT |
| unist-util-stringify-position | 4.0.0 | MIT |
| unist-util-visit | 5.1.0 | MIT |
| unist-util-visit-parents | 6.0.2 | MIT |
| url-parse | 1.5.10 | MIT |
| use-sync-external-store | 1.6.0 | MIT |
| vfile | 6.0.3 | MIT |
| vfile-message | 4.0.3 | MIT |
| vite | 8.0.7 | MIT |
| vitest | 4.1.3 | MIT |
| w3c-xmlserializer | 5.0.0 | MIT |
| whatwg-mimetype | 5.0.0 | MIT |
| whatwg-url | 16.0.1 | MIT |
| why-is-node-running | 2.3.0 | MIT |
| ws | 8.20.0 | MIT |
| xmlchars | 2.2.0 | MIT |
| zustand | 4.5.7 | MIT |
| zwitch | 2.0.4 | MIT |
| victory-vendor | 37.3.6 | MIT AND ISC |
| @csstools/color-helpers | 6.0.2 | MIT-0 |
| @csstools/css-syntax-patches-for-csstree | 1.1.2 | MIT-0 |
| lightningcss | 1.32.0 | MPL-2.0 |
| lightningcss-win32-x64-msvc | 1.32.0 | MPL-2.0 |
| posthog-js | 1.369.0 | SEE LICENSE IN LICENSE |
| combine-errors | 3.0.3 | UNKNOWN |
