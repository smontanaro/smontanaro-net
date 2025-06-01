# The static generation bits

# Requires GNU Make 4.3 or greater!
V43 = $(shell test $(shell echo $(MAKE_VERSION) | sed -e 's/[.]//') -ge 43 && echo "yes" || echo no)
ifeq ($(V43), no)
    $(error "GNU Make >= 4.3 is required")
endif

MONTHS = $(sort $(wildcard shell CR/20??-??))
GENDIRS = $(foreach dir,$(MONTHS),$(dir)/generated)
DATES = $(foreach dir,$(GENDIRS),$(dir)/dates.body)
THREADS = $(foreach dir,$(GENDIRS),$(dir)/threads.body)
REFDB = references.db
VIEWS = smontanaro/smontanaro/views.py
APP_SRC = $(wildcard smontanaro/smontanaro/*.py) $(wildcard scripts/*.py)
TST_SRC = $(wildcard smontanaro/tests/*.py)

export CRDIR = $(PWD)
export PYTHONPATH = $(PWD)/smontanaro

all : CR/generated/index.body CR/sitemap.xml $(DATES) $(THREADS)

CR/generated/index.body : $(VIEWS) scripts/genindexbody.sh
	mkdir -p CR/generated
	bash scripts/genindexbody.sh  > CR/generated/index.body

CR/sitemap.xml : scripts/makesitemap.py $(DATES) $(THREADS)
	python scripts/makesitemap.py

$(DATES) $(THREADS) &: $(VIEWS) scripts/gen-bodies.sh \
	scripts/generate_date_index.py scripts/generate_thread_index.py \
	$(REFDB)
	mkdir -p $(GENDIRS)
	bash scripts/gen-bodies.sh

smontanaro.net : smontanaro.net.in crawler-block.txt
	m4 smontanaro.net.in > smontanaro.net

$(REFDB).new : FORCE
	coverage run -a --rcfile=.coveragerc scripts/makerefsdb.py -d $(REFDB).new CR
	@echo "Replace $(REFDB) with $(REFDB).new when ready"

lint : mypy bandit pylint

mypy : FORCE
	-MYPYPATH=typeshed mypy --install-types $(APP_SRC)

bandit : FORCE
	-TERM=dumb bandit $(APP_SRC)

pylint : FORCE
	-pylint --rcfile=.pylintrc $(APP_SRC)

test : FORCE
	bash scripts/test.sh

clean : FORCE
	rm -rf search_cache dist htmlcov
	find . -name __pycache__ | xargs -r rm -rf

FORCE :

.PHONY : FORCE all lint mypy bandit pylint test clean
