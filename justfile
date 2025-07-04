npm-build:
    npm run build

build: clean npm-build
    podman run \
        --net=none \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \
        ghcr.io/gohugoio/hugo:latest \
        build \
        --ignoreCache

deploy: build
    rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

podman-pull:
    podman pull ghcr.io/gohugoio/hugo:latest

serve: clean npm-build
    podman run \
        --net=host \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD" \
        --workdir "/mnt/$PWD" \
        --userns keep-id \
        --group-add keep-groups \
        --log-driver none \
        ghcr.io/gohugoio/hugo:latest \
        server \
        --ignoreCache \
        --noHTTPCache  

clean:
    rm -rf public

update-db:
    ./scripts/dump-db-sql.py > assets/db/db.json

format-trachtnet:
    #!/usr/bin/env bash

    for f in "$PWD/static/trachtnet-dump"/**/*.json; do
        jq < "$f" > "$f".pretty
        mv "$f".pretty "$f"
    done

update-trachtnet: && format-trachtnet
    ./scripts/dump-trachtnet.py --year $(date +%Y) --outdir static/trachtnet-dump
    
update-trachtnet-chosen:
    ./scripts/gen-trachtnet.py --chosen-evaluations
    mv -f *.svg static/trachtnet/
