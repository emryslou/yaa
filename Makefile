DIRTESTS=`pwd`/tests
TESTPREFIX=test_

ifndef $(name)
	name=*
endif
pytest_params=$(DIRTESTS)/$(TESTPREFIX)$(name).py

ifneq ($(strip $(fn)),)
	pytest_params=$(DIRTESTS)/$(TESTPREFIX)$(name).py -k '$(fn)' -s -vv
endif


help:
	@echo "================================================" 
	@echo "|help info:                                    |"
	@echo "| tests            - test all cases            |"
	@echo "|    hint: if make test is for up to date,     |"
	@echo "|          use <make tests -B>                 |"
	@echo "| test name=xxx    - test tests/test_xxx.py    |"
	@echo "================================================"


test:
	@export PYTHONPATH=`pwd`
	python -m pytest $(pytest_params) $(pytest_fn)


run:
	python -m uvicorn demo.main:app --port 5505 --lifespan on --reload