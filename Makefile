.PHONY: setup \
        clean_cache_temp_files \
        lint code_check \
		test \
        pipeline all

.DEFAULT_GOAL := pipeline

PATH_RESEARCH ?= degiro_tools
PATH_TESTS ?= tests
PATH_PROJECT_ROOT ?= .

setup:
	@echo "Installing dependencies..."
	@uv sync --all-groups
	@echo "✅ Dependencies installed."

clean_cache_temp_files:
	@echo "Cleaning cache and temporary files..."
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type d -name .pytest_cache -exec rm -rf {} +
	@find . -type d -name .mypy_cache -exec rm -rf {} +
	@find . -type d -name .complexipy_cache -exec rm -rf {} +
	@find . -type d -name .ruff_cache -exec rm -rf {} +
	@find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	@echo "✅ Clean complete."

lint:
	@echo "Running lint checks..."
	@uv run ruff format $(PATH_PROJECT_ROOT)
	@uv run ruff check --fix $(PATH_PROJECT_ROOT)
	@echo "✅ Linting complete."

code_check:
	@echo "Running static code checks..."
	@uv run complexipy -f $(PATH_PROJECT_ROOT)
	@uv run mypy $(PATH_RESEARCH)
	@echo "✅ Code checks complete."

test:
	@echo "Running tests..."
	@uv run pytest ${PATH_TESTS} --maxfail=1 --durations=0
	@echo "✅ Tests complete."

pipeline: setup clean_cache_temp_files lint code_check
	@echo "✅ Pipeline complete."

all: pipeline test
	@echo "✅ All tasks complete."
