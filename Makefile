DIRTESTS=`pwd`/tests
TESTPREFIX=test_

pytest_params=.
ifneq ($(strip $(name)),)
	pytest_params=$(DIRTESTS)/$(name)
endif

ifneq ($(strip $(fn)),)
	ifneq ($(strip $(name)),)
		path=`echo $(name) | awk -F'.' '{pint}'`
		pytest_params=$(DIRTESTS)/$(name) -k '$(fn)'
	else
		pytest_params=. -k '$(fn)'
	endif
endif


help:
	@echo "================================================" 
	@echo "|help info:                                    |"
	@echo "| tests            - test all cases            |"
	@echo "|    hint: if make test is for up to date,     |"
	@echo "|          use <make tests -B>                 |"
	@echo "| test name=xxx    - test tests/test_xxx.py    |"
	@echo "================================================"

precommit:
	@export PYTHONPATH=`pwd`
	./scripts/lint
	python -m flake8 --ignore=E501,E203,W503,W504 yast/
	python -m coverage run -m pytest .
	python -m coverage html -d demo/code_coverage
	python -m coverage report -m

test:
	@export PYTHONPATH=`pwd`
	python -m coverage run -m pytest $(pytest_params) $(pytest_fn) -s -vv

demo:
	python -m uvicorn demo.main:app --port 5505 --lifespan on --reload

dist:
	python setup.py sdist bdist_wheel

doc:
	python -m mkdocs build -f mkdocs.yml -d demo/docs
docsvr:
	python -m mkdocs serve

gadd:
	./scripts/lint
	make tests -B
	git add `pwd`/