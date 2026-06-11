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
		echo "normalizing via qpdf/pikepdf (linearized) for GitHub rendering"; \
		$(PYTHON) -c "import pikepdf;p=pikepdf.open('$(PAPER).pdf',allow_overwriting_input=True);p.save('$(PAPER).pdf',linearize=True)" \
		  || echo "  (skipped: pip install pikepdf to normalize tectonic output for GitHub)"; \
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
