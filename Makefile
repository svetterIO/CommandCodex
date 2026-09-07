SHELL := /bin/sh
PODMAN ?= podman
IMAGE ?= commandcodex

.PHONY: build serve clean

build:
	@test -n "$(PASSWORD)" || (echo >&2 "ERROR: set PASSWORD for the encrypted build (for the bundled demo: make build PASSWORD=passw0rd)"; exit 2)
	$(PODMAN) build --no-cache \
		--build-arg "CONTENT_PASSWORD=$(PASSWORD)" \
		-t $(IMAGE) .

serve:
	$(PODMAN) run --rm -it -p 127.0.0.1:8000:80 $(IMAGE)

clean:
	rm -rf site
