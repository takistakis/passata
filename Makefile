PREFIX = /usr/local

test:
	flake8 *.py
	pytest

coverage:
	coverage run -m pytest --strict
	coverage report
	coverage html

install:
	install -d $(PREFIX)/bin
	install -C -m 755 passata.py $(PREFIX)/bin/passata
	install -d $(PREFIX)/share/zsh/site-functions
	install -C -m 644 _passata $(PREFIX)/share/zsh/site-functions/

uninstall:
	rm -f $(PREFIX)/bin/passata
	rm -f $(PREFIX)/share/zsh/site-functions/_passata

.PHONY: test coverage install uninstall
