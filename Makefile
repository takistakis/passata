PREFIX = /usr/local

install:
	install -d $(PREFIX)/bin
	install -C -m 755 passata.py $(PREFIX)/bin/passata
	install -d $(PREFIX)/share/passata
	install -C -m 644 wordlists/*.txt $(PREFIX)/share/passata/
	install -d $(PREFIX)/share/zsh/site-functions
	install -C -m 644 _passata $(PREFIX)/share/zsh/site-functions/

uninstall:
	rm -f $(PREFIX)/bin/passata
	rm -rf $(PREFIX)/share/passata
	rm -f $(PREFIX)/share/zsh/site-functions/_passata

test:
	ruff format *.py tests
	ruff check --fix *.py tests
	pyupgrade --py310-plus passata.py tests/*.py
	coverage run -m pytest
	coverage report
	coverage html
	mypy passata.py tests/ --disallow-untyped-defs

.PHONY: install uninstall test
