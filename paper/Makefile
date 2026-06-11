PAPER = observability

.PHONY: all clean distclean view

all: $(PAPER).pdf

# Prefer tectonic (single self-contained binary, no root; auto-fetches packages).
# Fall back to TeX Live pdflatex (the engine the companion paper was built with:
# pdfTeX / TeX Live). observability.tex uses an inline thebibliography, so no bibtex pass.
PYTHON = ../.venv/bin/python

$(PAPER).pdf: $(PAPER).tex
	@if command -v tectonic >/dev/null 2>&1; then \
		echo "building with tectonic"; tectonic $(PAPER).tex; \
		echo "normalizing xref (classic table) for GitHub rendering"; \
		$(PYTHON) -c "from pypdf import PdfReader,PdfWriter;r=PdfReader('$(PAPER).pdf');w=PdfWriter();[w.add_page(p) for p in r.pages];w.write(open('$(PAPER).pdf','wb'))" \
		  || echo "  (skipped: install pypdf to normalize; tectonic xref streams do not render on GitHub)"; \
	else \
		echo "building with pdflatex (classic xref)"; pdflatex $(PAPER) && pdflatex $(PAPER); \
	fi

clean:
	rm -f $(PAPER).aux $(PAPER).log $(PAPER).out $(PAPER).toc \
	       $(PAPER).bbl $(PAPER).blg $(PAPER).synctex.gz

distclean: clean
	rm -f $(PAPER).pdf

view: $(PAPER).pdf
	xdg-open $(PAPER).pdf 2>/dev/null || open $(PAPER).pdf 2>/dev/null || true
