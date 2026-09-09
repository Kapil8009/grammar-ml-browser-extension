.PHONY: install install-train run test package-extension docker-build

install:
	python -m pip install -e '.[ml,test]'

install-train:
	python -m pip install -e '.[train,test]'

run:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest

package-extension:
	bash scripts/package_extension.sh

docker-build:
	docker build -t grammar-ml .
