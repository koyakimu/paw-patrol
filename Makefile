.PHONY: fetch-canada fetch-tvtokyo fetch-unext fetch-all build

fetch-canada:
	python3 scripts/fetch_canada.py

fetch-tvtokyo:
	python3 scripts/fetch_tvtokyo.py

fetch-unext:
	python3 scripts/fetch_unext.py

fetch-all: fetch-canada fetch-tvtokyo fetch-unext

build:
	python3 scripts/build_database.py
