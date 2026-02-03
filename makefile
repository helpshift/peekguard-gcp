PYTHON_VERSION=3.12.9
VENV_ROOT=./.venv
HSFT_CONF_ENV?=localhost
PYENV_ROOT = $(HOME)/.pyenv

build: venv
	rm -rf ./dist/
	"$(VENV_ROOT)/bin/pip" install --upgrade build
	"$(VENV_ROOT)/bin/python" -m build

check:
	$(VENV_ROOT)/bin/pip install dependency-check
	$(VENV_ROOT)/bin/dependency-check --disableAssembly -s .  --project "peekguard" --exclude ".git/**" --exclude ".venv/**" --exclude "**/__pycache__/**" --exclude ".tox/**" --format "ALL"

clean:
	find . -name '*.pyc' -delete
	find . -type d -name __pycache__ -exec rm -r {} \+
	rm -rf .reports
	rm -rf .coverage coverage.xml pylint.txt dependency-check-report.*

coverage: clean dev
	$(VENV_ROOT)/bin/pip install coverage
	$(VENV_ROOT)/bin/coverage run -m pytest tests
	$(VENV_ROOT)/bin/coverage xml

dev: venv
	"$(VENV_ROOT)/bin/pip" install -e .

pylint:
	$(VENV_ROOT)/bin/pip install pylint
	$(VENV_ROOT)/bin/pylint --exit-zero peekguard/ tests/  -r n --msg-template="{path}:{line}:[{msg_id}({symbol}), {obj}] {msg}" | tee pylint.txt

run:
	"$(VENV_ROOT)/bin/python" -m 'peekguard.main'

safety: clean dev
	$(VENV_ROOT)/bin/pip install safety
	$(VVENV_ROOT)/bin/safety check
	$(VENV_ROOT)/bin/safety scan

sonar: coverage check pylint

test: dev
	"$(VENV_ROOT)/bin/pytest" -vvv

venv:
	find . -type d -name '*__pycache__*' | xargs rm -rf
	$(PYENV_ROOT)/bin/pyenv install --skip-existing "$(PYTHON_VERSION)"
	$(PYENV_ROOT)/bin/pyenv local "$(PYTHON_VERSION)"
	$(PYENV_ROOT)/bin/pyenv exec python -m venv --clear --upgrade-deps "$(VENV_ROOT)"
	$(PYENV_ROOT)/bin/pyenv local --unset