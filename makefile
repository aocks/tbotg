
SHELL = /bin/bash

.PHONY: help test test_fails trouble clean help_venv check_env reqs

PROJECT=tbotg

.EXPORT_ALL_VARIABLES:


################################################################
#                                                              #
#  PYTEST_IGNORE gets added to for stuff tester should ignore. #
#  Note that we need := for assignment to keep appending       #
PYTEST_IGONRE = 

# Ignore setup.py
PYTEST_IGNORE := ${PYTEST_IGNORE} --ignore=setup.py

# Ignore venv
PYTEST_IGNORE := ${PYTEST_IGNORE} --ignore=venv_${PROJECT} --ignore=venv

# End PYTEST_IGNORE section                                    #
#                                                              #
################################################################

PYTEST_TARGET = ${PROJECT} tests


PYTEST_FLAGS = -vvv --doctest-modules --doctest-glob='*.md'
PYTEST_EXTRA_FLAGS = 

help:
	@echo "This is a makefile for basic operations."
	@echo ""
	@echo "reqs:           Update requirements (make sure to activate venv)"
	@echo "test:           Run regression tests via pytest."
	@echo "test_fails:     Run tests that failed previous run."
	@echo "help_venv:      Help on using virtual environments"

reqs:
	if which pip | grep venv_ ; then echo "updating" ; else \
            echo "suspicious pip does not look like venv; exit" && exit 1; fi
	pip install -r requirements.txt

clean:
	rm -rf .pytype
	find . -name \*_flymake.py -print -exec rm {} \;
	find . -name '*~' -print -exec rm {} \;
	find ${PROJECT} -name '*.pyc' -print -exec rm {} \;
	find . -name '*.pyi' -print -exec rm {} \;
	find . -name archived_logs -print -exec rm -fr {} \;
	find . -name latest_logs -print -exec rm -fr {} \;
	@echo "done cleaning"

# Note that we set pipefail on the command since `tee` always returns status 0
# so we need pipefail if we want this command to fail on test failure.
test:
	set -o pipefail && \
          py.test ${PYTEST_FLAGS} ${PYTEST_IGNORE} \
            ${PYTEST_EXTRA_FLAGS} ${PYTEST_TARGET} 2>&1 | tee ./test_log.txt

lint:
	flake8 ${PYTEST_TARGET} --exclude=${LINT_IGNORE}
	pylint --rcfile=.pylintrc --jobs=4 --reports=n ${PYTEST_TARGET} \
           --ignore=${LINT_IGNOR}

pytype:
	pytype ${PYTEST_TARGET}

check:
	${MAKE} lint
	${MAKE} pytype
	${MAKE} test

test_fails:
	${MAKE} \
            PYTEST_EXTRA_FLAGS="${PYTEST_EXTRA_FLAGS} --last-failed" test

help_venv:
	@echo "Do 'python -m venv venv_${PROJECT}' to activate virtual env"

pypi: README.rst check
	 python3 setup.py sdist upload -r pypi

README.rst: README.org
	pandoc --from=org --to=rst --output=README.rst README.org
