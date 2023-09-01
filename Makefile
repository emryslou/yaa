help:
	@echo "================================================" 
	@echo "|tests            - test all cases             |"
	@echo "|test name=xxx    - test tests/test_xxx.py     |"
	@echo "================================================"
tests:
	@export PYTHONPATH=`pwd`
	python -m pytest .

test:
	@export PYTHONPATH=`pwd`
	python -m pytest tests/test_$(name).py -s -vv