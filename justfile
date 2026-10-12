# The recipes every site shares (npm-build, build, serve, clean,
# podman-pull, check-links); a recipe below under the same name replaces
# the theme's.
import 'themes/bienensteff/justfile'

# For the recipes here that replace one of the theme's.
set allow-duplicate-recipes

# List all recipes
default:
    @just --list --unsorted

build: npm-build
    {{ hugo }} build --cleanDestinationDir

deploy: build
    rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

update-db:
    uv run --project scripts dump-db > assets/db/db.json

update-trachtnet:
    uv run --project scripts dump-trachtnet --outdir static/trachtnet-dump

update-klima:
    uv run --project scripts dump-dwd --station-id 03379 --meta static/klima/03379_meta.json static/klima/03379_hourly.json static/klima/03379_daily.json
