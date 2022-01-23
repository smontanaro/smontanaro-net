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

export CRDIR = $(PWD)
export PYTHONPATH = $(PWD)/smontanaro

all : CR/generated/index.body $(DATES) $(THREADS)

CR/generated/index.body : $(VIEWS) scripts/genindexbody.sh
	mkdir -p CR/generated
	bash scripts/genindexbody.sh  > CR/generated/index.body

$(DATES) $(THREADS) &: $(VIEWS) scripts/gen-bodies.sh \
	scripts/generate_date_index.py scripts/generate_thread_index.py \
	$(REFDB)
	mkdir -p $(GENDIRS)
	bash scripts/gen-bodies.sh

$(REFDB).new : FORCE
	python scripts/makerefsdb.py -v -d $(REFDB).new CR
	@echo "Replace $(REFDB) with $(REFDB).new when ready"

lint : FORCE
	pylint smontanaro/smontanaro/*.py scripts/*.py \
	| sed -e '/duplicate-code/,/^--------------------/d'

test : FORCE
	bash test.sh

FORCE :

.PHONY : FORCE all debug
