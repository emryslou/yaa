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
	@echo "| precommit    - test all cases                |"
	@echo "|    hint: if make test is for up to date,     |"
	@echo "|          use <make tests -B>                 |"
	@echo "| test         - test tests/test_xxx.py        |"
	@echo "|    name=xxx                                  |"
	@echo "| demo         - run demo server               |"
	@echo "| dist         - make dist package             |"
	@echo "| doc          - make docs                     |"
	@echo "| docsvr       - run docs server               |"
	@echo "| gadd         - code lint && test && git add  |"
	@echo "================================================"

precommit:
	@export PYTHONPATH=`pwd`
	./scripts/lint
	python -m flake8 --ignore=E501,E203,W503,W504 yast/
	python -m coverage run -m pytest .
	python -m coverage html -d demo/code_coverage --precision=4 --skip-covered
	python -m coverage report -m --precision=4 --skip-covered --sort=cover

test:
	@export PYTHONPATH=`pwd`
	python -m coverage run -m pytest $(pytest_params) $(pytest_fn) -s -vv

http:
	python -m uvicorn demo.main:app --port 5505 --lifespan on --reload

http2:
	python -m hypercorn --keyfile demo/key.pem --certfile demo/cert.pem demo.main:app --bind 0.0.0.0:5505 --reload

dist:
	python setup.py sdist bdist_wheel

doc:
	python -m mkdocs build -f mkdocs.yml -d demo/docs

docsvr:
	python -m mkdocs serve

gadd: precommit
	git add `pwd`/