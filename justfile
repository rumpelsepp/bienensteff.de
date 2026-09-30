hugo := "./scripts/hugo"

npm-build:
    npm run build

build: npm-build
    {{ hugo }} build --cleanDestinationDir

serve: npm-build
    {{ hugo }} server --buildDrafts

deploy: build
    rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

podman-pull:
    podman pull ghcr.io/gohugoio/hugo:latest

clean:
    rm -rf public

update-db:
    uv run --project scripts dump-db > assets/db/db.json

update-pricelist:
    uv run --project scripts gen-pricelist > data/preisliste.json

update-trachtnet:
    uv run --project scripts dump-trachtnet --outdir static/trachtnet-dump

update-klima:
    uv run --project scripts dump-dwd --station-id 03379 static/klima/03379_hourly.json static/klima/03379_daily.json
