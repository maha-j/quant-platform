# Raccourcis de développement de la Quant Platform.
# Usage : make <cible>
export PYTHONPATH := $(CURDIR)/python:$(CURDIR)

.PHONY: help run run-once stack test lint cpp clean

help:            ## Liste les cibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

run:             ## Démarre service + pont + démo, reste actif (Ctrl-C pour arrêter)
	./scripts/run_all.sh

run-once:        ## Démarre la pile, joue la démo, puis arrête tout
	./scripts/run_all.sh --once

stack:           ## Démarre service + pont sans la démo
	./scripts/run_all.sh --no-demo

test:            ## Tests unitaires Python
	pytest tests/unit -q

lint:            ## Lint (ruff)
	ruff check python ml backtests

cpp:             ## Build + tests C++ (CMake + GoogleTest)
	cmake -S cpp -B build -DCMAKE_BUILD_TYPE=Release -DQUANT_BUILD_TESTS=ON
	cmake --build build -j
	ctest --test-dir build --output-on-failure

clean:           ## Nettoie les artefacts de build/couverture
	rm -rf build .coverage coverage.xml htmlcov
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
