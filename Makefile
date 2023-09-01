help:
	@echo "================================================" 
	@echo "|help info:                                    |"
	@echo "| tests            - test all cases            |"
	@echo "|    hint: if make test is for up to date,     |"
	@echo "|          use <make tests -B>                 |"
	@echo "| test name=xxx    - test tests/test_xxx.py    |"
	@echo "================================================"


tests:
	@echo "test all cases, may takes some minutes ..."
	@export PYTHONPATH=`pwd`
	python -m pytest tests/*

test:
	@export PYTHONPATH=`pwd`
	python -m pytest tests/test_$(name).py -s -vv