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

all : CR/generated/index.body $(DATES) $(THREADS)

CR/generated/index.body : hello.py scripts/genindexbody.sh
	mkdir -p CR/generated
	bash scripts/genindexbody.sh  > CR/generated/index.body

$(DATES) $(THREADS) &: hello.py scripts/gen-bodies.sh \
	scripts/generate_date_index.py scripts/generate_thread_index.py \
	$(REFDB)
	mkdir -p $(GENDIRS)
	bash scripts/gen-bodies.sh

debug : FORCE
	@echo $(MAKE_VERSION)
	@echo $(MONTHS)
	@echo $(GENDIRS)
	@echo $(DATES)
	@echo $(THREADS)
	@echo $(REFDB)
	ls -l $(REFDB) CR/2002-10/generated/threads.body

$(REFDB).new : FORCE
	python scripts/makerefsdb -v -d $(REFDB).new CR
	@echo "Replace $(REFDB) with $(REFDB).new when ready"

FORCE :

.PHONY : FORCE all debug
