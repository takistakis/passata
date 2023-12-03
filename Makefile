PREFIX = /usr/local

install:
	install -d $(PREFIX)/bin
	install -C -m 755 passata.py $(PREFIX)/bin/passata
	install -d $(PREFIX)/share/zsh/site-functions
	install -C -m 644 _passata $(PREFIX)/share/zsh/site-functions/

uninstall:
	rm -f $(PREFIX)/bin/passata
	rm -f $(PREFIX)/share/zsh/site-functions/_passata

test:
	flake8 passata.py tests/
	isort passata.py tests/
	coverage run -m pytest
	coverage report

.PHONY: install uninstall test
