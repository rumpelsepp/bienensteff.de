npm-build:
    npm run build

build: clean npm-build
    podman run \
        --net=none \
        --rm \
        --interactive \
        --tty \
        --volume "$PWD:/mnt/$PWD:z" \
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
        --volume "$PWD:/mnt/$PWD:z" \
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
    uv run --project scripts dump-db | jq > assets/db/db.json

format-trachtnet:
    #!/usr/bin/env bash

    for f in "$PWD/static/trachtnet-dump"/**/*.json; do
        jq < "$f" > "$f".pretty
        mv "$f".pretty "$f"
    done

update-pricelist:
    uv run --project scripts gen-pricelist > data/preisliste.json

update-trachtnet: && format-trachtnet
    uv run --project scripts dump-trachtnet --year $(date +%Y) --outdir static/trachtnet-dump

update-klima:
    uv run --project scripts dump-dwd --station-id 03379 static/klima/03387_hourly.json static/klima/03379_daily.json
