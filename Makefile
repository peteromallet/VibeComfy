PYTHON ?= .venv/bin/python
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
NODE ?= node
COMFY_INDEX_URL ?= https://nodes.appmana.com/simple/

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
	tests/test_porting_edit_projection.py \
	tests/test_porting_edit_ledger.py \
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

ROOT_ALLOWLIST := \
	.env.example \
	.github \
	.gitignore \
	.megaplan \
	.importlinter \
	.pre-commit-config.yaml \
	LICENSE \
	Makefile \
	README.md \
	cloud.yaml \
	custom_nodes.lock \
	docs \
	pyproject.toml \
	ready_templates \
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

.PHONY: all check ci install-dev install-ci prune-empty-runtime-root root-clean post-root-clean docs template-index templates strict-ready fast snapshots oracle browser-smoke parity e2e-browser clean clean-artifacts

all: check

check: root-clean docs template-index templates strict-ready fast snapshots oracle browser-smoke parity post-root-clean

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
	$(PYTEST) -q $(STRICT_READY_PYTEST)

fast:
	$(PYTEST) -q --tb=short $(FAST_PYTEST) \
		--cov=vibecomfy \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-fail-under=0

snapshots:
	$(PYTHON) -m tools.regenerate_snapshots --check

oracle:
	VIBECOMFY_COMFY_SMOKE=1 $(PYTEST) -q --tb=short \
		tests/test_porting_ui_emitter.py::test_layer3_corpus_wide_convert_ui_to_api_gate

browser-smoke:
	$(NODE) --test tests/browser/*.mjs

parity:
	$(PYTHON) -m tools.check_canonical_parity --all

e2e-browser:
	cd tests/e2e && npm install
	$(NODE) tests/e2e/run.mjs

clean-artifacts:
	rm -rf .coverage coverage.xml .pytest_cache .hypothesis out temp test-results
	find . -path '*/__pycache__' -type d -prune -exec rm -rf {} +

clean: clean-artifacts
