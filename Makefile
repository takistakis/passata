PREFIX = /usr/local

install: install-data
	install -d $(PREFIX)/bin
	install -C -m 755 passata.py $(PREFIX)/bin/passata

install-rust: install-data
	cargo build --release --locked --manifest-path passata-rs/Cargo.toml --target-dir passata-rs/target
	install -d $(PREFIX)/bin
	install -C -m 755 passata-rs/target/release/passata-rs $(PREFIX)/bin/passata

install-data:
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
	coverage run -m pytest
	coverage report
	coverage html
	mypy passata.py tests/ --disallow-untyped-defs

.PHONY: install install-rust install-data uninstall test
