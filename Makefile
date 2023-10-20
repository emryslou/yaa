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

test_temp:
	@mkdir -p .temp/pytest
	@chmod -R 777 .temp/pytest
	@rm -rf .temp/pytest

mypy:
	# https://mypy.readthedocs.io/en/stable/
	python -m mypy yaa

test: test_temp
	@export PYTHONPATH=`pwd`
	python -m coverage run -m pytest $(pytest_params) $(pytest_fn) -s -vv

bandit:
	python -m bandit -r yaa --severity-level high

precommit: test_temp
	@export PYTHONPATH=`pwd`
	./scripts/lint

	python -m ruff check --fix yaa/
	python -m coverage run -m pytest .
	python -m coverage html -d .temp/code_coverage --precision=4 --skip-covered
	python -m coverage report -m --precision=4 --skip-covered --sort=cover

http:
	python -m uvicorn demo.main:app --port 5505 --lifespan on --reload

http2:
	python -m hypercorn --keyfile demo/key.pem --certfile demo/cert.pem demo.main:app --bind 0.0.0.0:5505 --reload

requirements:
	python -m pip install -r ./requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

dist:
	python setup.py sdist bdist_wheel

doc:
	python -m mkdocs build -f mkdocs.yml -d demo/docs

docsvr:
	python -m mkdocs serve

gadd: precommit
	git add `pwd`/
