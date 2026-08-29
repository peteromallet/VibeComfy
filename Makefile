PYTHON ?= .venv/bin/python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
NODE ?= node
COMFY_INDEX_URL ?= https://nodes.appmana.com/simple/
COVERAGE_FAIL_UNDER ?= 70

FAST_PYTEST := \
	tests/test_cli_loader.py \
	tests/test_scratchpad_loader.py \
	tests/test_virtual_wire_round_trip.py \
	tests/test_strict_ready.py \
	tests/test_strict_ready_gate.py \
	tests/test_porting_workbench.py \
	tests/test_porting_inventory.py \
	tests/test_cli_misc.py \
	tests/test_cli_sources_workflows_nodes.py \
	tests/test_porting_convert.py \
	tests/test_plugin_discovery.py \
	tests/test_agent_acceptance.py \
	tests/test_comfy_nodes_agent_backend_spine.py \
	tests/test_porting_edit_apply.py \
	tests/test_porting_edit_ops.py \
	tests/test_porting_edit_corpus.py \
	tests/test_porting_ui_materialize.py

STRICT_READY_PYTEST := \
	tests/test_strict_ready.py \
	tests/test_strict_ready_gate.py \
	tests/test_porting_workbench.py \
	tests/test_porting_inventory.py \
	tests/test_cli_misc.py \
	tests/test_cli_sources_workflows_nodes.py \
	tests/test_porting_convert.py \
	tests/test_plugin_discovery.py \
	tests/test_agent_acceptance.py

BROWSER_CONTRACT_TESTS := \
	tests/browser/ownership_contract.test.mjs \
	tests/browser/lifecycle_ownership_static.test.mjs \
	tests/browser/preview_overlay_ownership_static.test.mjs \
	tests/browser/frontend_ownership_regression.test.mjs \
	tests/browser/payload_contracts.test.mjs \
	tests/browser/agent_edit_response_contract.test.mjs \
	tests/browser/canonical_delta.test.mjs \
	tests/browser/m1_contracts.test.mjs \
	tests/browser/intent_graph_adapter.test.mjs \
	tests/browser/intent_graph_adapter_ownership_static.test.mjs \
	tests/browser/agent_lifecycle_commit.test.mjs \
	tests/browser/agent_lifecycle_parity.test.mjs \
	tests/browser/legacy_authority_migration.test.mjs \
	tests/browser/frontend_browser_boundary.test.mjs \
	tests/browser/render_section_safety.test.mjs

E2E_PREVIEW_SPECS := \
	tests/e2e/specs/agent_panel_overlay.spec.mjs

CORRECTIVE_GATE_INVENTORY ?= tests/corrective_gate_inventory.json
CORRECTIVE_GATE_ARTIFACTS ?= test-results/corrective-trust-gate

ROOT_ALLOWLIST := \
	.env.example \
	.gitattributes \
	.github \
	.gitignore \
	.megaplan \
	.oracle \
	.importlinter \
	.pre-commit-config.yaml \
	.vscode \
	LICENSE \
	Makefile \
	README.md \
	cloud.yaml \
	custom_nodes.lock \
	docs \
	pyproject.toml \
	ready_templates \
	research \
	scripts \
	template_index.json \
	tests \
	tools \
	uv.lock \
	vibecomfy

ROOT_BANNED := \
	AGENTS.md \
	CLAUDE.md \
	agentic \
	agents \
	artifacts \
	asset_manifest.json \
	custom_nodes \
	finalize.json \
	input \
	models \
	output \
	plan_v2.md \
	recipes \
	revised_plan.md \
	user \
	vendor \
	version_matrix.json \
	workflow_corpus

B02_MINI_CORPUS := tests/fixtures/b02_corpus_mini

.PHONY: all check ci install-dev install-ci prune-empty-runtime-root root-clean post-root-clean docs template-index templates strict-ready fast broad-pytest broad-pytest-collect full-pytest snapshots oracle b02-corpus-mini b02-corpus-full browser-contracts browser-smoke parity e2e-browser e2e-preview corrective-trust-gate-preflight corrective-trust-gate ir-boundary clean clean-artifacts

all: check

check: root-clean docs template-index templates strict-ready fast snapshots oracle b02-corpus-mini browser-smoke parity ir-boundary post-root-clean

ci: check

install-dev:
	$(PIP) install -e ".[dev]"

install-ci:
	$(PIP) install --extra-index-url "$(COMFY_INDEX_URL)" -e ".[dev,runpod-launch,comfy]"
	$(PIP) install "lazy-object-proxy>=1.10" "frozendict>=2.4" "pillow>=10" "ConfigArgParse>=1.7.1"

prune-empty-runtime-root:
	@for path in input output models user vendor custom_nodes; do \
		if [ -d "$$path" ] && [ -z "$$(find "$$path" \( -type f -o -type l \) -print -quit)" ]; then \
			rm -rf "$$path"; \
		fi; \
	done

root-clean: prune-empty-runtime-root
	@actual="$$(git ls-files --cached --others --exclude-standard | awk -F/ '{print $$1}' | sort -u)"; \
	expected="$$(printf '%s\n' $(ROOT_ALLOWLIST) | sort)"; \
	if [ "$$actual" != "$$expected" ]; then \
		echo "Tracked repository root does not match the Makefile allowlist."; \
		echo "Expected:"; echo "$$expected"; \
		echo "Actual:"; echo "$$actual"; \
		exit 1; \
	fi
	@for path in $(ROOT_BANNED); do \
		if [ -e "$$path" ]; then \
			echo "Root path '$$path' does not earn its place here; move it under an owned parent or delete it."; \
			exit 1; \
		fi; \
	done

post-root-clean:
	$(MAKE) --no-print-directory root-clean

docs:
	$(PYTHON) -m tools.check_markdown_links

template-index:
	$(PYTHON) -m tools.refresh_template_index --check

templates: template-index
	$(PYTHON) -m tools.validate_templates_against_packs --all
	$(PYTHON) -m tools.validate_template_traceability --strict

strict-ready: template-index
	$(PYTHON) -m tools.check_strict_ready_templates --json

fast:
	@echo "FAST Python gate: bounded maintained selector ($(words $(FAST_PYTEST)) files); not the repository-wide denominator."
	$(PYTEST) -q --tb=short $(FAST_PYTEST) \
		--cov=vibecomfy \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-fail-under=$(COVERAGE_FAIL_UNDER)

# Broad Python gate: every test under tests (GPU excluded by pyproject's
# default addopts), parallelized across 8 xdist workers. It is deliberately a
# separate target so callers cannot mistake the bounded fast selector for the
# repository-wide denominator.
broad-pytest:
	@echo "BROAD Python gate: all tests under tests; this is the repository-wide denominator."
	PYTHONHASHSEED=0 $(PYTEST) -n 8 -q -p no:cacheprovider tests

# Collection-only broad check for diagnosing selection/import drift without
# executing the suite. Kept explicit because the current broad suite includes
# environment-dependent modules that are not part of the fast gate.
broad-pytest-collect:
	@echo "BROAD Python collection: all tests under tests."
	PYTHONHASHSEED=0 $(PYTEST) --collect-only -q -p no:cacheprovider tests

# Backwards-compatible spelling retained for existing local callers.
full-pytest: broad-pytest

snapshots:
	$(PYTHON) -m tools.regenerate_snapshots --check

oracle:
	VIBECOMFY_COMFY_SMOKE=1 $(PYTEST) -q --tb=short \
		tests/test_porting_ui_emitter.py::test_layer3_corpus_wide_convert_ui_to_api_gate

ir-boundary:
	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_ir_boundary.py

b02-corpus-mini:
	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
		--corpus-dir "$(B02_MINI_CORPUS)" --expected-count 3

b02-corpus-full:
	@if [ -z "$(CORPUS_DIR)" ]; then \
		echo "CORPUS_DIR is required (no default full-corpus path)."; \
		exit 2; \
	fi
	PYTHONPATH="$(CURDIR)" $(PYTHON) scripts/check_b02_rich_preservation.py \
		--corpus-dir "$(CORPUS_DIR)" --expected-count 2825

browser-smoke:
	VIBECOMFY_PYTHON="$(PYTHON)" $(NODE) --test tests/browser/*.mjs

# Standalone subset of browser-smoke; pure Node/browser-contract coverage without Playwright or ComfyUI prerequisites (browser-smoke already runs all tests/browser/*.mjs).
browser-contracts:
	VIBECOMFY_PYTHON="$(PYTHON)" $(NODE) --test $(BROWSER_CONTRACT_TESTS)

parity:
	$(PYTHON) -m tools.check_canonical_parity --all

e2e-browser:
	cd tests/e2e && npm install
	PYBIN="$(PYTHON)" $(NODE) tests/e2e/run.mjs

# Keep preview e2e explicit because it assumes the heavier browser + ComfyUI test environment.
e2e-preview:
	@if ! command -v comfyui >/dev/null 2>&1 && [ ! -x "$(dir $(PYTHON))comfyui" ]; then \
		$(PYTHON) -m pip install --extra-index-url https://nodes.appmana.com/simple/ 'comfyui==0.26.0'; \
	fi
	@if [ ! -d tests/e2e/node_modules/@playwright/test ]; then \
		cd tests/e2e && npm install && npx playwright install chromium; \
	fi
	PYBIN="$(PYTHON)" $(NODE) tests/e2e/run.mjs -- --config tests/e2e/playwright.config.mjs $(E2E_PREVIEW_SPECS)

corrective-trust-gate-preflight:
	@if ! command -v comfyui >/dev/null 2>&1 && [ ! -x "$(dir $(PYTHON))comfyui" ]; then \
		$(PYTHON) -m pip install --extra-index-url https://nodes.appmana.com/simple/ 'comfyui==0.26.0'; \
	fi
	@if [ ! -d tests/e2e/node_modules/@playwright/test ]; then \
		cd tests/e2e && npm install && npx playwright install chromium; \
	fi

corrective-trust-gate: corrective-trust-gate-preflight
	PYBIN="$(PYTHON)" $(PYTHON) -m tools.run_corrective_gate \
		--inventory "$(CORRECTIVE_GATE_INVENTORY)" \
		--artifact-dir "$(CORRECTIVE_GATE_ARTIFACTS)"

clean-artifacts:
	rm -rf .coverage coverage.xml .pytest_cache .hypothesis out temp test-results
	find . -path '*/__pycache__' -type d -prune -exec rm -rf {} +

clean: clean-artifacts
